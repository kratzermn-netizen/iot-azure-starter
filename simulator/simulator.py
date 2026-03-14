"""
simulator.py — Hauptprogramm: Sensor → Azure IoT Hub

Jetzt mit sauberer Sensor-Abstraktion:
  Simulator-Modus:  USE_REAL_SENSOR = False  (Standard, läuft auf jedem PC)
  Pi-Modus:         USE_REAL_SENSOR = True   (auf dem Raspberry Pi mit BME280)
"""

import time
import json
from datetime import datetime, timezone
from azure.iot.device import IoTHubDeviceClient, Message

# ──────────────────────────────────────────────
# KONFIGURATION
# ──────────────────────────────────────────────

# Azure IoT Hub → Geräte → sensor-01 → Primäre Verbindungszeichenfolge
CONNECTION_STRING = "HIER_DEINE_CONNECTION_STRING_EINFÜGEN"

DEVICE_ID = "sensor-01"
SEND_INTERVAL_SECONDS = 5

# ┌─────────────────────────────────────────────┐
# │  SENSOR AUSWAHL                             │
# │  False = Simulator (PC)                     │
# │  True  = Echter BME280 (Raspberry Pi)       │
# └─────────────────────────────────────────────┘
USE_REAL_SENSOR = False


# ──────────────────────────────────────────────
# Sensor initialisieren
# ──────────────────────────────────────────────
def create_sensor():
    if USE_REAL_SENSOR:
        from sensor_bme280 import BME280Sensor
        return BME280Sensor()
    else:
        from sensor_simulator import SimulatedSensor
        return SimulatedSensor(simulate_anomalies=True)


# ──────────────────────────────────────────────
# Hauptprogramm
# ──────────────────────────────────────────────
def main():
    mode = "🍓 Raspberry Pi + BME280" if USE_REAL_SENSOR else "💻 Simulator"
    print(f"🚀 IoT Client startet — Modus: {mode}")
    print(f"   Gerät:     {DEVICE_ID}")
    print(f"   Intervall: {SEND_INTERVAL_SECONDS}s")
    print("─" * 50)

    if CONNECTION_STRING == "HIER_DEINE_CONNECTION_STRING_EINFÜGEN":
        print("❌ Bitte CONNECTION_STRING eintragen!")
        print("   Azure Portal → IoT Hub → Geräte → sensor-01")
        print("   → Primäre Verbindungszeichenfolge kopieren")
        return

    sensor = create_sensor()
    client = IoTHubDeviceClient.create_from_connection_string(CONNECTION_STRING)

    try:
        while True:
            reading = sensor.read()

            payload = {
                "deviceId": DEVICE_ID,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "temperature": reading.temperature,
                "humidity": reading.humidity,
                "pressure": reading.pressure,
            }

            message = Message(json.dumps(payload))
            message.content_type = "application/json"
            message.content_encoding = "utf-8"

            client.send_message(message)

            print(
                f"✅ [{payload['timestamp'][11:19]}] "
                f"Temp: {reading.temperature:6.2f}°C | "
                f"Feuchte: {reading.humidity:5.1f}% | "
                f"Druck: {reading.pressure:7.2f} hPa"
            )

            time.sleep(SEND_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\n\n⏹  Gestoppt.")
    finally:
        sensor.close()
        client.disconnect()


if __name__ == "__main__":
    main()
