"""
sensor.py — Sensor-Schnittstelle

Diese Datei definiert die gemeinsame Schnittstelle für ALLE Sensoren.
Simulator und echter BME280 liefern exakt dasselbe Format.

Später auf dem Pi: nur sensor_bme280.py aktivieren, sensor_simulator.py deaktivieren.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SensorReading:
    """Ein einzelner Messwert — identisch ob simuliert oder echt."""
    temperature: float   # °C
    humidity: float      # %
    pressure: float      # hPa


class SensorBase(ABC):
    """Abstrakte Basisklasse — jeder Sensor muss read() implementieren."""

    @abstractmethod
    def read(self) -> SensorReading:
        """Liest aktuelle Messwerte vom Sensor."""
        ...

    def close(self):
        """Optionale Aufräum-Logik (z.B. GPIO cleanup auf dem Pi)."""
        pass
