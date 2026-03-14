"""
sensor_bme280.py — Echter BME280 Sensor (nur auf Raspberry Pi)

Verkabelung BME280 → Pi 5 (GPIO):
  VCC  → Pin 1  (3.3V)
  GND  → Pin 6  (Ground)
  SDA  → Pin 3  (GPIO 2, I2C Data)
  SCL  → Pin 5  (GPIO 3, I2C Clock)

Voraussetzungen auf dem Pi:
  sudo apt install python3-smbus i2c-tools
  pip install adafruit-circuitpython-bme280

I2C aktivieren:
  sudo raspi-config → Interface Options → I2C → Enable
  i2cdetect -y 1   → sollte Adresse 0x76 oder 0x77 zeigen
"""

from sensor import SensorBase, SensorReading

# Dieser Import funktioniert NUR auf dem Raspberry Pi
try:
    import board
    import adafruit_bme280.basic as adafruit_bme280
    BME280_AVAILABLE = True
except ImportError:
    BME280_AVAILABLE = False


class BME280Sensor(SensorBase):
    """
    Liest echte Messwerte vom BME280 über I2C.
    Nur auf Raspberry Pi mit angeschlossenem Sensor verwenden.
    """

    def __init__(self, i2c_address: int = 0x76):
        if not BME280_AVAILABLE:
            raise RuntimeError(
                "adafruit-circuitpython-bme280 nicht installiert.\n"
                "Nur auf Raspberry Pi verfügbar:\n"
                "  pip install adafruit-circuitpython-bme280"
            )

        i2c = board.I2C()
        self._bme = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=i2c_address)

        # Oversampling für bessere Genauigkeit
        self._bme.overscan_temperature = adafruit_bme280.OVERSCAN_X8
        self._bme.overscan_humidity = adafruit_bme280.OVERSCAN_X4
        self._bme.overscan_pressure = adafruit_bme280.OVERSCAN_X4

        print(f"✅ BME280 initialisiert (I2C Adresse: {hex(i2c_address)})")

    def read(self) -> SensorReading:
        return SensorReading(
            temperature=round(self._bme.temperature, 2),
            humidity=round(self._bme.humidity, 2),
            pressure=round(self._bme.pressure, 2),
        )

    def close(self):
        pass  # I2C wird automatisch geschlossen
