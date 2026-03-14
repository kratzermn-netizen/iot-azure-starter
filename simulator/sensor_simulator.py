"""
sensor_simulator.py — Simulierter Sensor (läuft auf jedem PC)

Erzeugt realistische Messwerte mit Tagesverlauf und gelegentlichen Anomalien.
Wird später auf dem Pi durch sensor_bme280.py ersetzt.
"""

import math
import random
from sensor import SensorBase, SensorReading


class SimulatedSensor(SensorBase):
    """
    Simuliert einen BME280-Sensor mit realistischem Verhalten:
    - Tagesverlauf (Sinus-Kurve)
    - Gausssches Rauschen
    - Gelegentliche Anomalien (3% Wahrscheinlichkeit)
    """

    def __init__(self, simulate_anomalies: bool = True):
        self._tick = 0
        self._simulate_anomalies = simulate_anomalies

    def read(self) -> SensorReading:
        # Tagesverlauf simulieren
        hour_factor = math.sin(self._tick * 0.01) * 0.5

        temp = 22.0 + hour_factor * 5 + random.gauss(0, 0.3)
        humidity = 55.0 - hour_factor * 8 + random.gauss(0, 0.5)
        pressure = 1013.25 + random.gauss(0, 0.8)

        # Anomalie simulieren
        anomaly = False
        if self._simulate_anomalies and random.random() < 0.03:
            temp += random.choice([-8, 12])
            anomaly = True

        self._tick += 1

        reading = SensorReading(
            temperature=round(temp, 2),
            humidity=round(max(0.0, min(100.0, humidity)), 2),
            pressure=round(pressure, 2),
        )

        if anomaly:
            print(f"  ⚠️  Anomalie simuliert! Temperatur: {reading.temperature}°C")

        return reading
