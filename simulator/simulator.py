"""
simulator.py — Hauptprogramm: Sensor → Azure IoT Hub

Jetzt mit sauberer Sensor-Abstraktion:
  Simulator-Modus:  USE_REAL_SENSOR = False  (Standard, läuft auf jedem PC)
  Pi-Modus:         USE_REAL_SENSOR = True   (auf dem Raspberry Pi mit BME280)
"""

import time
import json
import logging
from datetime import datetime, timezone
from azure.iot.device import IoTHubDeviceClient, Message
from azure.iot.device.exceptions import ConnectionFailedError, ConnectionDroppedError

from sensor import SensorBase, SensorReading

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# KONFIGURATION
# ──────────────────────────────────────────────

# Azure IoT Hub → Geräte → sensor-01 → Primäre Verbindungszeichenfolge
CONNECTION_STRING = "HIER_DEINE_CONNECTION_STRING_EINFÜGEN"  # ← Azure Portal → IoT Hub → Geräte → sensor-01 → Primäre Verbindungszeichenfolge

DEVICE_ID = "sensor-01"
SEND_INTERVAL_SECONDS = 5

# ┌─────────────────────────────────────────────┐
# │  SENSOR AUSWAHL                             │
# │  False = Simulator (PC)                     │
# │  True  = Echter BME280 (Raspberry Pi)       │
# └─────────────────────────────────────────────┘
USE_REAL_SENSOR = False

_PLACEHOLDER_CONNECTION_STRING = "HIER_DEINE_CONNECTION_STRING_EINFÜGEN"
_MAX_SEND_RETRIES = 3


# ──────────────────────────────────────────────
# Sensor initialisieren
# ──────────────────────────────────────────────
def create_sensor() -> SensorBase:
    """Erstellt und gibt den konfigurierten Sensor zurück.

    Returns:
        SensorBase: SimulatedSensor (PC) oder BME280Sensor (Raspberry Pi),
                    abhängig von USE_REAL_SENSOR.
    Raises:
        RuntimeError: Wenn der BME280-Sensor nicht initialisiert werden kann.
    """
    if USE_REAL_SENSOR:
        from sensor_bme280 import BME280Sensor
        return BME280Sensor()
    else:
        from sensor_simulator import SimulatedSensor
        return SimulatedSensor(simulate_anomalies=True)


def _build_payload(reading: SensorReading) -> dict:
    """Erstellt das JSON-Payload für eine Sensormessung.

    Args:
        reading: Aktueller Messwert vom Sensor.
    Returns:
        dict: Payload mit deviceId, timestamp und Messwerten.
    """
    return {
        "deviceId": DEVICE_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature": reading.temperature,
        "humidity": reading.humidity,
        "pressure": reading.pressure,
    }


def _build_message(payload: dict) -> Message:
    """Verpackt ein Payload-Dict als IoT Hub Message mit JSON Content-Type.

    Args:
        payload: Messwert-Dict.
    Returns:
        Message: Azure IoT Hub Nachricht.
    """
    message = Message(json.dumps(payload))
    message.content_type = "application/json"
    message.content_encoding = "utf-8"
    return message


def _print_startup_info() -> None:
    """Gibt Startinformationen (Modus, Gerät, Intervall) auf der Konsole aus."""
    mode = "🍓 Raspberry Pi + BME280" if USE_REAL_SENSOR else "💻 Simulator"
    logger.info(f"🚀 IoT Client startet — Modus: {mode}")
    logger.info(f"   Gerät:     {DEVICE_ID}")
    logger.info(f"   Intervall: {SEND_INTERVAL_SECONDS}s")


def _print_reading(payload: dict, reading: SensorReading) -> None:
    """Gibt einen einzelnen Messwert formatiert auf der Konsole aus.

    Args:
        payload: Gesendetes Payload (enthält den timestamp).
        reading: Messwert-Objekt für die formatierten Werte.
    """
    logger.info(
        f"✅ [{payload['timestamp'][11:19]}] "
        f"Temp: {reading.temperature:6.2f}°C | "
        f"Feuchte: {reading.humidity:5.1f}% | "
        f"Druck: {reading.pressure:7.2f} hPa"
    )


def _send_with_retry(client: IoTHubDeviceClient, message: Message) -> None:
    """Sendet eine Nachricht mit bis zu _MAX_SEND_RETRIES Versuchen.

    Args:
        client: Verbundener IoTHubDeviceClient.
        message: Zu sendende Nachricht.
    Raises:
        ConnectionFailedError: Wenn alle Wiederholungsversuche fehlschlagen.
    """
    for attempt in range(1, _MAX_SEND_RETRIES + 1):
        try:
            client.send_message(message)
            return
        except (ConnectionFailedError, ConnectionDroppedError) as exc:
            logger.warning(f"Sendefehler (Versuch {attempt}/{_MAX_SEND_RETRIES}): {exc}")
            if attempt == _MAX_SEND_RETRIES:
                raise
            time.sleep(2 ** attempt)  # Exponentielles Backoff: 2s, 4s


def _send_loop(sensor: SensorBase, client: IoTHubDeviceClient) -> None:
    """Hauptschleife: liest Sensor und sendet Nachrichten bis KeyboardInterrupt.

    Args:
        sensor: Initialisierter Sensor (simuliert oder echt).
        client: Verbundener IoTHubDeviceClient.
    """
    try:
        while True:
            reading = sensor.read()
            payload = _build_payload(reading)
            _send_with_retry(client, _build_message(payload))
            _print_reading(payload, reading)
            time.sleep(SEND_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        logger.info("\n⏹  Gestoppt.")
    finally:
        sensor.close()
        client.disconnect()


# ──────────────────────────────────────────────
# Hauptprogramm
# ──────────────────────────────────────────────
def main() -> None:
    """Einstiegspunkt: prüft Konfiguration, initialisiert Sensor und Client,
    startet die Sendeschleife."""
    _print_startup_info()

    if CONNECTION_STRING == _PLACEHOLDER_CONNECTION_STRING:
        logger.error("❌ Bitte CONNECTION_STRING eintragen!")
        logger.error("   Azure Portal → IoT Hub → Geräte → sensor-01")
        logger.error("   → Primäre Verbindungszeichenfolge kopieren")
        return

    sensor = create_sensor()
    client = IoTHubDeviceClient.create_from_connection_string(CONNECTION_STRING)
    _send_loop(sensor, client)


if __name__ == "__main__":
    main()
