"""
sensor_simulator.py — Simulierter Sensor (läuft auf jedem PC)

Erzeugt realistische Messwerte mit Tagesverlauf und gelegentlichen Anomalien.
Wird später auf dem Pi durch sensor_bme280.py ersetzt.
"""

import math
import random
from sensor import SensorBase, SensorReading

# Basislinie der simulierten Messwerte
_BASE_TEMP_C = 22.0
_BASE_HUMIDITY_PCT = 55.0
_BASE_PRESSURE_HPA = 1013.25  # Standardatmosphäre

# Tagesverlauf: Wie stark schwanken Werte über den Tag (Sinus-Kurve)
_DAILY_CYCLE_FREQUENCY = 0.01   # Tick-Einheiten pro Radianten
_DAILY_CYCLE_AMPLITUDE = 0.5    # Skalierungsfaktor des Sinus
_TEMP_DAILY_RANGE_C = 5         # Max. Temperaturschwankung durch Tagesverlauf
_HUMIDITY_DAILY_RANGE_PCT = 8   # Max. Feuchtigkeitsschwankung durch Tagesverlauf

# Gausssches Rauschen (Standardabweichung)
_TEMP_NOISE_STD = 0.3
_HUMIDITY_NOISE_STD = 0.5
_PRESSURE_NOISE_STD = 0.8

# Anomalie-Simulation
_ANOMALY_PROBABILITY = 0.03          # 3% Wahrscheinlichkeit pro Messung
_ANOMALY_OFFSETS_C = [-8, 12]        # Mögliche Temperatursprünge bei Anomalie


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
        hour_factor = math.sin(self._tick * _DAILY_CYCLE_FREQUENCY) * _DAILY_CYCLE_AMPLITUDE

        temp = _BASE_TEMP_C + hour_factor * _TEMP_DAILY_RANGE_C + random.gauss(0, _TEMP_NOISE_STD)
        humidity = _BASE_HUMIDITY_PCT - hour_factor * _HUMIDITY_DAILY_RANGE_PCT + random.gauss(0, _HUMIDITY_NOISE_STD)
        pressure = _BASE_PRESSURE_HPA + random.gauss(0, _PRESSURE_NOISE_STD)

        # Anomalie simulieren
        anomaly = False
        if self._simulate_anomalies and random.random() < _ANOMALY_PROBABILITY:
            temp += random.choice(_ANOMALY_OFFSETS_C)
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
