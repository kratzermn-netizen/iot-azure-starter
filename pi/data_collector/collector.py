"""
data_collector/collector.py — Data Collector Prozess

Verantwortlich für:
  1. BME280-Sensor auslesen (I2C)
  2. System-Metriken sammeln (CPU, RAM, Temp, Netzwerk, Uptime)
  3. SensorPayload zusammenbauen
  4. Per Unix Domain Socket an Connectivity App senden

Läuft als systemd Service: iot-collector.service
"""

import os
import sys
import time
import socket
import logging
import signal
from pathlib import Path

import psutil

# Shared Protokoll (liegt eine Ebene höher)
sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))
from protocol import SensorPayload, SOCKET_PATH, encode_message, MSG_HEADER_SIZE

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [COLLECTOR] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("collector")

# ──────────────────────────────────────────────
# Konfiguration (via Umgebungsvariablen oder Defaults)
# ──────────────────────────────────────────────
DEVICE_ID = os.getenv("IOT_DEVICE_ID", "pi-sensor-01")
COLLECT_INTERVAL = float(os.getenv("COLLECT_INTERVAL_SEC", "5"))
BME280_I2C_ADDRESS = int(os.getenv("BME280_I2C_ADDR", "0x76"), 16)


# ──────────────────────────────────────────────
# BME280 Sensor
# ──────────────────────────────────────────────
class BME280Reader:
    """Liest Temperatur, Luftfeuchtigkeit und Luftdruck vom BME280."""

    def __init__(self, i2c_address: int):
        try:
            import board
            import adafruit_bme280.basic as adafruit_bme280
            i2c = board.I2C()
            self._bme = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=i2c_address)
            self._bme.overscan_temperature = adafruit_bme280.OVERSCAN_X8
            self._bme.overscan_humidity = adafruit_bme280.OVERSCAN_X4
            self._bme.overscan_pressure = adafruit_bme280.OVERSCAN_X4
            self._available = True
            log.info(f"BME280 initialisiert (I2C: {hex(i2c_address)})")
        except Exception as e:
            self._available = False
            log.warning(f"BME280 nicht verfügbar: {e} — verwende Fallback-Werte")

    def read(self) -> tuple[float, float, float, bool]:
        """Gibt (temperature, humidity, pressure, ok) zurück."""
        if not self._available:
            return 0.0, 0.0, 0.0, False
        try:
            return (
                round(self._bme.temperature, 2),
                round(self._bme.humidity, 2),
                round(self._bme.pressure, 2),
                True,
            )
        except Exception as e:
            log.error(f"BME280 Lesefehler: {e}")
            return 0.0, 0.0, 0.0, False


# ──────────────────────────────────────────────
# System-Metriken
# ──────────────────────────────────────────────
class SystemMetrics:
    """Sammelt Linux-Systemmetriken via psutil."""

    def __init__(self):
        # Initialmessung für Netzwerk-Delta
        net = psutil.net_io_counters()
        self._last_net_sent = net.bytes_sent
        self._last_net_recv = net.bytes_recv
        self._boot_time = psutil.boot_time()

    def _read_cpu_temp(self) -> float:
        """Liest Pi-CPU-Temperatur aus /sys (zuverlässiger als psutil auf Pi)."""
        try:
            temp_str = Path("/sys/class/thermal/thermal_zone0/temp").read_text()
            return round(int(temp_str.strip()) / 1000.0, 1)
        except Exception:
            # psutil Fallback
            temps = psutil.sensors_temperatures()
            for key in ("cpu_thermal", "cpu-thermal", "coretemp"):
                if key in temps and temps[key]:
                    return round(temps[key][0].current, 1)
            return 0.0

    def read(self) -> dict:
        """Gibt aktuelle System-Metriken zurück."""
        # CPU (1s Blocking-Intervall absichtlich kurz)
        cpu_pct = psutil.cpu_percent(interval=0.5)

        # RAM
        ram = psutil.virtual_memory()
        ram_pct = ram.percent

        # CPU Temperatur
        cpu_temp = self._read_cpu_temp()

        # Netzwerk-Delta seit letztem Aufruf
        net = psutil.net_io_counters()
        net_sent = net.bytes_sent - self._last_net_sent
        net_recv = net.bytes_recv - self._last_net_recv
        self._last_net_sent = net.bytes_sent
        self._last_net_recv = net.bytes_recv

        # Uptime
        uptime = int(time.time() - self._boot_time)

        return {
            "cpu_percent": round(cpu_pct, 1),
            "ram_percent": round(ram_pct, 1),
            "cpu_temp": cpu_temp,
            "net_bytes_sent": max(0, net_sent),
            "net_bytes_recv": max(0, net_recv),
            "uptime_seconds": uptime,
        }


# ──────────────────────────────────────────────
# Socket Client
# ──────────────────────────────────────────────
class ConnectorClient:
    """
    Sendet SensorPayload per Unix Domain Socket an die Connectivity App.
    Baut die Verbindung bei Bedarf neu auf (Reconnect-Logik).
    """

    def __init__(self, socket_path: str):
        self._path = socket_path
        self._sock: socket.socket | None = None

    def _connect(self):
        """Verbindet zum Unix Domain Socket der Connectivity App."""
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.connect(self._path)
        log.info(f"Verbunden mit Connectivity App ({self._path})")

    def send(self, payload: SensorPayload) -> bool:
        """Sendet Payload — gibt True bei Erfolg zurück."""
        for attempt in range(3):
            try:
                if self._sock is None:
                    self._connect()
                msg = encode_message(payload)
                self._sock.sendall(msg)
                return True
            except (ConnectionRefusedError, BrokenPipeError, OSError) as e:
                log.warning(f"Socket-Fehler (Versuch {attempt + 1}/3): {e}")
                self._sock = None
                time.sleep(2 ** attempt)  # Exponentieller Backoff: 1s, 2s, 4s
        log.error("Connectivity App nicht erreichbar — Messwert verworfen")
        return False

    def close(self):
        if self._sock:
            self._sock.close()
            self._sock = None


# ──────────────────────────────────────────────
# Hauptprozess
# ──────────────────────────────────────────────
class DataCollector:

    def __init__(self):
        self._running = True
        self._bme = BME280Reader(BME280_I2C_ADDRESS)
        self._sys = SystemMetrics()
        self._connector = ConnectorClient(SOCKET_PATH)

        # Graceful Shutdown via systemd SIGTERM
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum, frame):
        log.info(f"Signal {signum} empfangen — fahre herunter...")
        self._running = False

    def run(self):
        log.info(f"Data Collector gestartet (Device: {DEVICE_ID}, Intervall: {COLLECT_INTERVAL}s)")

        while self._running:
            start = time.monotonic()

            try:
                # 1. Sensordaten lesen
                temp, hum, pres, sensor_ok = self._bme.read()

                # 2. Systemmetriken lesen
                sys_metrics = self._sys.read()

                # 3. Payload zusammenbauen
                payload = SensorPayload(
                    device_id=DEVICE_ID,
                    timestamp=time.time(),
                    temperature=temp,
                    humidity=hum,
                    pressure=pres,
                    sensor_ok=sensor_ok,
                    **sys_metrics,
                )

                # 4. An Connectivity App senden
                ok = self._connector.send(payload)

                log.info(
                    f"{'✓' if ok else '✗'} "
                    f"Temp={temp:.1f}°C Feuchte={hum:.1f}% Druck={pres:.1f}hPa | "
                    f"CPU={sys_metrics['cpu_percent']:.1f}% "
                    f"RAM={sys_metrics['ram_percent']:.1f}% "
                    f"CPUTemp={sys_metrics['cpu_temp']:.1f}°C"
                )

            except Exception as e:
                log.error(f"Unerwarteter Fehler: {e}", exc_info=True)

            # Präzises Timing: Messzeit abziehen
            elapsed = time.monotonic() - start
            sleep_time = max(0.0, COLLECT_INTERVAL - elapsed)
            time.sleep(sleep_time)

        self._connector.close()
        log.info("Data Collector beendet.")


if __name__ == "__main__":
    DataCollector().run()
