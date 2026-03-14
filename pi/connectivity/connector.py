"""
connectivity/connector.py — Connectivity Application Prozess

Verantwortlich für:
  1. Unix Domain Socket Server (empfängt Payloads vom Data Collector)
  2. TLS-gesicherte MQTT-Verbindung zu Azure IoT Hub (Port 8883)
  3. HTTPS-Fallback bei MQTT-Ausfall (Port 443)
  4. Automatischer Reconnect mit exponentiellem Backoff
  5. Lokaler Puffer bei Verbindungsausfall (Ring-Buffer)

Läuft als systemd Service: iot-connector.service
"""

import os
import sys
import ssl
import json
import time
import socket
import struct
import logging
import signal
import threading
from collections import deque
from pathlib import Path
from typing import Optional

import paho.mqtt.client as mqtt
import requests

# Shared Protokoll
sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))
from protocol import (
    SensorPayload, SOCKET_PATH,
    decode_message, MSG_HEADER_SIZE, MAX_MSG_SIZE,
)

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CONNECTOR] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("connector")

# ──────────────────────────────────────────────
# Konfiguration (via Umgebungsvariablen)
# ──────────────────────────────────────────────
IOT_HUB_HOST   = os.environ["IOT_HUB_HOST"]           # z.B. myhub.azure-devices.net
DEVICE_ID      = os.environ["IOT_DEVICE_ID"]           # z.B. pi-sensor-01
CERT_FILE      = os.environ["IOT_CERT_FILE"]           # /etc/iot/device.pem
KEY_FILE       = os.environ["IOT_KEY_FILE"]            # /etc/iot/device.key
CA_FILE        = os.environ.get("IOT_CA_FILE", "/etc/ssl/certs/ca-certificates.crt")

MQTT_PORT      = 8883
HTTPS_FALLBACK = os.getenv("IOT_HTTPS_FALLBACK", "true").lower() == "true"
BUFFER_SIZE    = int(os.getenv("IOT_BUFFER_SIZE", "100"))   # Max gepufferte Nachrichten

MQTT_TOPIC     = f"devices/{DEVICE_ID}/messages/events/"
HTTPS_URL      = f"https://{IOT_HUB_HOST}/devices/{DEVICE_ID}/messages/events?api-version=2021-04-12"


# ──────────────────────────────────────────────
# TLS-Kontext
# ──────────────────────────────────────────────
def build_tls_context() -> ssl.SSLContext:
    """Erstellt einen TLS 1.2+ Kontext mit Client-Zertifikat."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
    ctx.load_verify_locations(CA_FILE)
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.check_hostname = True
    log.info(f"TLS-Kontext erstellt (Cert: {CERT_FILE})")
    return ctx


# ──────────────────────────────────────────────
# MQTT Client
# ──────────────────────────────────────────────
class MQTTTransport:
    """
    MQTT-Verbindung zu Azure IoT Hub über Port 8883 (TLS).
    Azure IoT Hub MQTT-Spezifikation:
      Username: {hub}/{deviceId}/?api-version=2021-04-12
      Password: leer (bei X.509-Zertifikats-Auth)
      ClientId: {deviceId}
    """

    def __init__(self, tls_ctx: ssl.SSLContext):
        self._connected = False
        self._tls_ctx = tls_ctx
        self._client = self._build_client()

    def _build_client(self) -> mqtt.Client:
        client = mqtt.Client(
            client_id=DEVICE_ID,
            protocol=mqtt.MQTTv311,
            clean_session=True,
        )
        client.username_pw_set(
            username=f"{IOT_HUB_HOST}/{DEVICE_ID}/?api-version=2021-04-12",
            password="",
        )
        client.tls_set_context(self._tls_ctx)
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_publish = self._on_publish
        return client

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            log.info(f"MQTT verbunden mit {IOT_HUB_HOST}:{MQTT_PORT}")
        else:
            log.error(f"MQTT Verbindungsfehler: rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        if rc != 0:
            log.warning(f"MQTT unerwartet getrennt (rc={rc})")

    def _on_publish(self, client, userdata, mid):
        log.debug(f"MQTT Nachricht bestätigt (mid={mid})")

    def connect(self) -> bool:
        try:
            self._client.connect(IOT_HUB_HOST, MQTT_PORT, keepalive=60)
            self._client.loop_start()
            # Kurz warten auf Verbindungsbestätigung
            for _ in range(20):
                if self._connected:
                    return True
                time.sleep(0.2)
            log.error("MQTT Verbindungs-Timeout")
            return False
        except Exception as e:
            log.error(f"MQTT connect Fehler: {e}")
            return False

    def publish(self, payload: SensorPayload) -> bool:
        if not self._connected:
            return False
        try:
            data = json.dumps(payload.to_azure_dict())
            result = self._client.publish(
                topic=MQTT_TOPIC,
                payload=data,
                qos=1,
            )
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            log.error(f"MQTT publish Fehler: {e}")
            return False

    def disconnect(self):
        self._client.loop_stop()
        self._client.disconnect()
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected


# ──────────────────────────────────────────────
# HTTPS Fallback
# ──────────────────────────────────────────────
class HTTPSTransport:
    """HTTPS-Fallback wenn MQTT nicht verfügbar ist."""

    def __init__(self, tls_ctx: ssl.SSLContext):
        self._session = requests.Session()
        self._session.cert = (CERT_FILE, KEY_FILE)
        self._session.verify = CA_FILE

    def publish(self, payload: SensorPayload) -> bool:
        try:
            data = json.dumps(payload.to_azure_dict())
            resp = self._session.post(
                HTTPS_URL,
                data=data,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            if resp.status_code in (200, 204):
                log.info("HTTPS Fallback: Nachricht gesendet")
                return True
            log.error(f"HTTPS Fehler: {resp.status_code} {resp.text[:100]}")
            return False
        except Exception as e:
            log.error(f"HTTPS Fehler: {e}")
            return False


# ──────────────────────────────────────────────
# Unix Domain Socket Server
# ──────────────────────────────────────────────
class SocketServer:
    """
    Empfängt SensorPayload vom Data Collector per Unix Domain Socket.
    Läuft in eigenem Thread, legt Payloads in eine Queue.
    """

    def __init__(self, socket_path: str, queue: deque):
        self._path = socket_path
        self._queue = queue
        self._running = True

        # Alten Socket aufräumen
        try:
            os.unlink(socket_path)
        except FileNotFoundError:
            pass

    def _handle_client(self, conn: socket.socket):
        """Liest vollständige Nachrichten mit Längen-Header."""
        with conn:
            while self._running:
                try:
                    # 4-Byte Längen-Header lesen
                    header = self._recv_exact(conn, MSG_HEADER_SIZE)
                    if not header:
                        break
                    msg_len = int.from_bytes(header, byteorder="big")

                    if msg_len > MAX_MSG_SIZE:
                        log.error(f"Nachricht zu groß: {msg_len} Bytes")
                        break

                    # Payload lesen
                    data = self._recv_exact(conn, msg_len)
                    if not data:
                        break

                    payload = decode_message(data)
                    self._queue.append(payload)

                except Exception as e:
                    log.warning(f"Socket-Client Fehler: {e}")
                    break

    def _recv_exact(self, conn: socket.socket, n: int) -> Optional[bytes]:
        """Liest exakt n Bytes aus dem Socket."""
        buf = bytearray()
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                return None
            buf.extend(chunk)
        return bytes(buf)

    def run(self):
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(self._path)
        server.listen(1)
        server.settimeout(1.0)
        log.info(f"Socket Server lauscht auf {self._path}")

        while self._running:
            try:
                conn, _ = server.accept()
                t = threading.Thread(
                    target=self._handle_client,
                    args=(conn,),
                    daemon=True,
                )
                t.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    log.error(f"Socket Server Fehler: {e}")

        server.close()
        try:
            os.unlink(self._path)
        except FileNotFoundError:
            pass

    def stop(self):
        self._running = False


# ──────────────────────────────────────────────
# Hauptprozess
# ──────────────────────────────────────────────
class ConnectivityApp:

    def __init__(self):
        self._running = True
        self._queue: deque[SensorPayload] = deque(maxlen=BUFFER_SIZE)

        tls_ctx = build_tls_context()
        self._mqtt = MQTTTransport(tls_ctx)
        self._https = HTTPSTransport(tls_ctx) if HTTPS_FALLBACK else None
        self._socket_server = SocketServer(SOCKET_PATH, self._queue)

        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum, frame):
        log.info(f"Signal {signum} — fahre herunter...")
        self._running = False
        self._socket_server.stop()

    def _send_with_fallback(self, payload: SensorPayload) -> bool:
        """Versucht MQTT, fällt auf HTTPS zurück wenn nötig."""
        if self._mqtt.is_connected:
            if self._mqtt.publish(payload):
                return True
            log.warning("MQTT publish fehlgeschlagen — versuche HTTPS Fallback")

        if self._https:
            return self._https.publish(payload)

        log.error("Alle Transporte fehlgeschlagen — Nachricht verworfen")
        return False

    def _connect_mqtt_with_backoff(self):
        """Verbindet MQTT mit exponentiellem Backoff."""
        delay = 5
        while self._running and not self._mqtt.is_connected:
            log.info(f"Verbinde MQTT (nächster Versuch in {delay}s)...")
            if self._mqtt.connect():
                return
            time.sleep(delay)
            delay = min(delay * 2, 300)  # Max 5 Minuten

    def run(self):
        log.info(f"Connectivity App gestartet (Hub: {IOT_HUB_HOST}, Device: {DEVICE_ID})")

        # Socket Server in eigenem Thread
        socket_thread = threading.Thread(
            target=self._socket_server.run, daemon=True
        )
        socket_thread.start()

        # MQTT verbinden
        self._connect_mqtt_with_backoff()

        # Hauptschleife: Queue verarbeiten
        while self._running:
            # MQTT Reconnect wenn nötig
            if not self._mqtt.is_connected:
                log.warning("MQTT getrennt — reconnecting...")
                self._connect_mqtt_with_backoff()

            # Alle gepufferten Nachrichten senden
            while self._queue and self._running:
                payload = self._queue.popleft()
                ok = self._send_with_fallback(payload)
                log.info(
                    f"{'✓ MQTT' if ok and self._mqtt.is_connected else '✓ HTTPS' if ok else '✗ FEHLER'} "
                    f"device={payload.device_id} "
                    f"temp={payload.temperature:.1f}°C "
                    f"cpu={payload.cpu_percent:.1f}% "
                    f"buffer={len(self._queue)}"
                )

            time.sleep(0.1)

        self._mqtt.disconnect()
        log.info("Connectivity App beendet.")


if __name__ == "__main__":
    ConnectivityApp().run()
