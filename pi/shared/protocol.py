"""
shared/protocol.py — Gemeinsames Datenprotokoll zwischen Data Collector und Connectivity App

Definiert:
  - SensorPayload: der Datensatz der zwischen den Prozessen übertragen wird
  - Serialisierung via MessagePack (binär, kompakt, schnell)

Beide Prozesse importieren NUR dieses Modul — keine direkte Abhängigkeit untereinander.
"""

from __future__ import annotations
import time
from dataclasses import dataclass, asdict
from typing import Optional
import msgpack


# ──────────────────────────────────────────────
# Protokoll-Version — bei Breaking Changes erhöhen
# ──────────────────────────────────────────────
PROTOCOL_VERSION = 1


@dataclass
class SensorPayload:
    """
    Vollständiger Messdatensatz — Sensordaten + System-Metriken.
    Wird vom Data Collector erzeugt und von der Connectivity App gesendet.
    """

    # Metadaten
    device_id: str
    timestamp: float          # Unix timestamp (UTC)
    protocol_version: int = PROTOCOL_VERSION

    # BME280 Sensordaten
    temperature: float = 0.0  # °C
    humidity: float = 0.0     # %
    pressure: float = 0.0     # hPa

    # System-Metriken (Raspberry Pi)
    cpu_percent: float = 0.0       # %
    ram_percent: float = 0.0       # %
    cpu_temp: float = 0.0          # °C (Pi-intern)
    net_bytes_sent: int = 0        # Bytes seit letztem Intervall
    net_bytes_recv: int = 0        # Bytes seit letztem Intervall
    uptime_seconds: int = 0        # Sekunden seit Boot

    # Qualitätssignal
    sensor_ok: bool = True         # False wenn Sensor-Lesefehler

    def pack(self) -> bytes:
        """Serialisiert zu MessagePack (binär)."""
        return msgpack.packb(asdict(self), use_bin_type=True)

    @classmethod
    def unpack(cls, data: bytes) -> SensorPayload:
        """Deserialisiert aus MessagePack."""
        d = msgpack.unpackb(data, raw=False)
        return cls(**d)

    def to_azure_dict(self) -> dict:
        """
        Format für Azure IoT Hub — JSON-kompatibel.
        Timestamp wird zu ISO-8601 konvertiert.
        """
        from datetime import datetime, timezone
        ts = datetime.fromtimestamp(self.timestamp, tz=timezone.utc).isoformat()
        return {
            "deviceId": self.device_id,
            "timestamp": ts,
            "sensors": {
                "temperature": round(self.temperature, 2),
                "humidity": round(self.humidity, 2),
                "pressure": round(self.pressure, 2),
            },
            "system": {
                "cpuPercent": round(self.cpu_percent, 1),
                "ramPercent": round(self.ram_percent, 1),
                "cpuTemp": round(self.cpu_temp, 1),
                "netBytesSent": self.net_bytes_sent,
                "netBytesRecv": self.net_bytes_recv,
                "uptimeSeconds": self.uptime_seconds,
            },
            "meta": {
                "sensorOk": self.sensor_ok,
                "protocolVersion": self.protocol_version,
            }
        }


# Unix Domain Socket Pfad — beide Prozesse müssen denselben Pfad nutzen
SOCKET_PATH = "/tmp/iot_collector.sock"

# Nachrichtenlängen-Header: 4 Byte Big-Endian uint32
# Protokoll: [4 Byte Länge][N Byte MessagePack-Payload]
MSG_HEADER_SIZE = 4
MAX_MSG_SIZE = 64 * 1024  # 64 KB Limit


def encode_message(payload: SensorPayload) -> bytes:
    """Verpackt Payload mit Längen-Header für Socket-Übertragung."""
    data = payload.pack()
    length = len(data).to_bytes(MSG_HEADER_SIZE, byteorder="big")
    return length + data


def decode_message(data: bytes) -> SensorPayload:
    """Entpackt Payload nach Socket-Empfang."""
    return SensorPayload.unpack(data)
