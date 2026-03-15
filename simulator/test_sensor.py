"""
pytest tests for simulator/sensor.py and simulator/sensor_simulator.py
Run with: pytest simulator/test_sensor.py -v
"""
import math
import sys
import os
import pytest

# Make the simulator directory importable when running pytest from repo root
sys.path.insert(0, os.path.dirname(__file__))

from sensor import SensorBase, SensorReading
from sensor_simulator import SimulatedSensor


# ---------------------------------------------------------------------------
# SensorReading dataclass
# ---------------------------------------------------------------------------

class TestSensorReading:
    def test_fields_exist(self):
        reading = SensorReading(temperature=22.5, humidity=55.0, pressure=1013.25)
        assert hasattr(reading, "temperature")
        assert hasattr(reading, "humidity")
        assert hasattr(reading, "pressure")

    def test_field_values_stored_correctly(self):
        reading = SensorReading(temperature=22.5, humidity=55.0, pressure=1013.25)
        assert reading.temperature == 22.5
        assert reading.humidity == 55.0
        assert reading.pressure == 1013.25

    def test_field_types_are_float(self):
        reading = SensorReading(temperature=20.1, humidity=60.2, pressure=1010.3)
        assert isinstance(reading.temperature, float)
        assert isinstance(reading.humidity, float)
        assert isinstance(reading.pressure, float)

    def test_negative_temperature_allowed(self):
        reading = SensorReading(temperature=-5.0, humidity=80.0, pressure=1000.0)
        assert reading.temperature == -5.0

    def test_equality(self):
        r1 = SensorReading(temperature=22.5, humidity=55.0, pressure=1013.25)
        r2 = SensorReading(temperature=22.5, humidity=55.0, pressure=1013.25)
        assert r1 == r2

    def test_inequality(self):
        r1 = SensorReading(temperature=22.5, humidity=55.0, pressure=1013.25)
        r2 = SensorReading(temperature=30.0, humidity=55.0, pressure=1013.25)
        assert r1 != r2


# ---------------------------------------------------------------------------
# SensorBase abstract class
# ---------------------------------------------------------------------------

class TestSensorBase:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            SensorBase()

    def test_subclass_without_read_is_abstract(self):
        class IncompletesSensor(SensorBase):
            pass

        with pytest.raises(TypeError):
            IncompletesSensor()

    def test_subclass_with_read_can_be_instantiated(self):
        class ConcreteSensor(SensorBase):
            def read(self) -> SensorReading:
                return SensorReading(temperature=20.0, humidity=50.0, pressure=1013.0)

        sensor = ConcreteSensor()
        assert sensor is not None

    def test_default_close_does_not_raise(self):
        class ConcreteSensor(SensorBase):
            def read(self) -> SensorReading:
                return SensorReading(temperature=20.0, humidity=50.0, pressure=1013.0)

        sensor = ConcreteSensor()
        # close() has a default no-op implementation — must not raise
        sensor.close()


# ---------------------------------------------------------------------------
# SimulatedSensor
# ---------------------------------------------------------------------------

class TestSimulatedSensorRead:
    def test_returns_sensor_reading_instance(self):
        sensor = SimulatedSensor()
        result = sensor.read()
        assert isinstance(result, SensorReading)

    def test_temperature_is_float(self):
        sensor = SimulatedSensor()
        result = sensor.read()
        assert isinstance(result.temperature, float)

    def test_humidity_is_float(self):
        sensor = SimulatedSensor()
        result = sensor.read()
        assert isinstance(result.humidity, float)

    def test_pressure_is_float(self):
        sensor = SimulatedSensor()
        result = sensor.read()
        assert isinstance(result.pressure, float)

    def test_humidity_within_bounds_single_read(self):
        sensor = SimulatedSensor()
        result = sensor.read()
        assert 0.0 <= result.humidity <= 100.0

    def test_humidity_always_within_0_to_100(self):
        """Run many reads and verify humidity never leaves [0, 100]."""
        sensor = SimulatedSensor(simulate_anomalies=True)
        for _ in range(500):
            result = sensor.read()
            assert 0.0 <= result.humidity <= 100.0, (
                f"Humidity out of range: {result.humidity}"
            )

    def test_tick_increments_on_each_read(self):
        sensor = SimulatedSensor()
        assert sensor._tick == 0
        sensor.read()
        assert sensor._tick == 1
        sensor.read()
        assert sensor._tick == 2
        sensor.read()
        assert sensor._tick == 3

    def test_temperature_rounded_to_2_decimals(self):
        sensor = SimulatedSensor()
        result = sensor.read()
        # round(x, 2) means at most 2 decimal places
        assert result.temperature == round(result.temperature, 2)

    def test_humidity_rounded_to_2_decimals(self):
        sensor = SimulatedSensor()
        result = sensor.read()
        assert result.humidity == round(result.humidity, 2)

    def test_pressure_rounded_to_2_decimals(self):
        sensor = SimulatedSensor()
        result = sensor.read()
        assert result.pressure == round(result.pressure, 2)

    def test_pressure_near_standard_atmosphere(self):
        """Without anomalies pressure stays within a reasonable band of 1013.25 hPa."""
        sensor = SimulatedSensor(simulate_anomalies=False)
        for _ in range(200):
            result = sensor.read()
            # gauss(0, 0.8) — 6-sigma band is ~5 hPa
            assert 1008.0 <= result.pressure <= 1020.0, (
                f"Pressure unexpectedly far from standard: {result.pressure}"
            )


class TestSimulatedSensorAnomalies:
    def test_no_anomalies_temperature_stays_in_range(self):
        """With simulate_anomalies=False, temperature must not contain anomaly spikes."""
        sensor = SimulatedSensor(simulate_anomalies=False)
        for _ in range(1000):
            result = sensor.read()
            # Normal range: 22 ± 2.5 (sin factor) ± ~1 (3*gauss sigma)
            # Anomaly adds ±8 or +12. A generous safe band is [-5, 40] without anomalies.
            assert -5.0 <= result.temperature <= 40.0, (
                f"Temperature out of expected normal range: {result.temperature}"
            )

    def test_no_anomalies_flag_disables_large_spikes(self):
        """Verify that without anomalies the temperature spread is tight."""
        sensor = SimulatedSensor(simulate_anomalies=False)
        readings = [sensor.read().temperature for _ in range(1000)]
        # Normal band is roughly [17, 27] with small gaussian noise
        assert max(readings) < 35.0, f"Max temperature too high: {max(readings)}"
        assert min(readings) > 10.0, f"Min temperature too low: {min(readings)}"

    def test_anomalies_enabled_by_default(self):
        sensor = SimulatedSensor()
        assert sensor._simulate_anomalies is True

    def test_anomalies_disabled_via_constructor(self):
        sensor = SimulatedSensor(simulate_anomalies=False)
        assert sensor._simulate_anomalies is False

    def test_anomalies_enabled_can_produce_spikes(self):
        """Over many reads with anomalies enabled we should see at least one spike."""
        import random
        random.seed(42)
        sensor = SimulatedSensor(simulate_anomalies=True)
        temps = [sensor.read().temperature for _ in range(2000)]
        # At 3% anomaly rate and 2000 reads we expect ~60 anomalies
        has_spike = any(t > 32.0 or t < 12.0 for t in temps)
        assert has_spike, "Expected at least one anomaly spike in 2000 reads"


class TestSimulatedSensorDefaults:
    def test_initial_tick_is_zero(self):
        sensor = SimulatedSensor()
        assert sensor._tick == 0

    def test_simulate_anomalies_defaults_to_true(self):
        sensor = SimulatedSensor()
        assert sensor._simulate_anomalies is True

    def test_close_does_not_raise(self):
        sensor = SimulatedSensor()
        sensor.close()  # inherited no-op from SensorBase
