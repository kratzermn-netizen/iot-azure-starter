#!/bin/bash
# deploy_pi.sh — Installiert beide Services auf dem Raspberry Pi
#
# Ausführen auf dem Pi:
#   chmod +x deploy_pi.sh
#   sudo ./deploy_pi.sh

set -e

INSTALL_DIR="/opt/iot"
CERT_DIR="/etc/iot/certs"
ENV_DIR="/etc/iot"

echo "=== IoT Services Setup ==="

# 1. Verzeichnisse anlegen
echo "[1/7] Verzeichnisse anlegen..."
sudo mkdir -p "$INSTALL_DIR"/{data_collector,connectivity,shared}
sudo mkdir -p "$CERT_DIR"
sudo mkdir -p "$ENV_DIR"

# 2. I2C aktivieren (falls noch nicht)
echo "[2/7] I2C prüfen..."
if ! lsmod | grep -q i2c_dev; then
    echo "  → I2C aktivieren (Reboot erforderlich nach Setup)"
    sudo raspi-config nonint do_i2c 0
fi

# 3. Python-Abhängigkeiten
echo "[3/7] Python Virtual Environment..."
sudo apt-get install -y python3-venv python3-smbus i2c-tools
sudo python3 -m venv "$INSTALL_DIR/venv"
sudo "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
sudo "$INSTALL_DIR/venv/bin/pip" install \
    adafruit-circuitpython-bme280 \
    psutil \
    msgpack \
    paho-mqtt \
    requests

# 4. Code kopieren
echo "[4/7] Code installieren..."
sudo cp shared/protocol.py "$INSTALL_DIR/shared/"
sudo cp data_collector/collector.py "$INSTALL_DIR/data_collector/"
sudo cp connectivity/connector.py "$INSTALL_DIR/connectivity/"

# Shared im Python-Pfad verfügbar machen
echo "$INSTALL_DIR/shared" | sudo tee "$INSTALL_DIR/venv/lib/python3.*/site-packages/iot_shared.pth" > /dev/null

# 5. Konfigurationsdateien
echo "[5/7] Konfiguration..."
if [ ! -f "$ENV_DIR/collector.env" ]; then
    sudo cp systemd/collector.env.template "$ENV_DIR/collector.env"
    echo "  → Bitte $ENV_DIR/collector.env anpassen!"
fi
if [ ! -f "$ENV_DIR/connector.env" ]; then
    sudo cp systemd/connector.env.template "$ENV_DIR/connector.env"
    echo "  → Bitte $ENV_DIR/connector.env anpassen!"
fi

# 6. Berechtigungen
echo "[6/7] Berechtigungen..."
sudo chown -R pi:pi "$INSTALL_DIR"
sudo chmod 700 "$CERT_DIR"
sudo chmod 600 "$ENV_DIR"/*.env 2>/dev/null || true

# 7. systemd Services
echo "[7/7] systemd Services registrieren..."
sudo cp systemd/iot-collector.service /etc/systemd/system/
sudo cp systemd/iot-connector.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable iot-connector.service
sudo systemctl enable iot-collector.service

echo ""
echo "=== Setup abgeschlossen ==="
echo ""
echo "Nächste Schritte:"
echo "  1. Zertifikate kopieren nach $CERT_DIR/"
echo "     sudo cp device.pem device.key $CERT_DIR/"
echo "     sudo chmod 600 $CERT_DIR/*"
echo ""
echo "  2. Konfiguration anpassen:"
echo "     sudo nano $ENV_DIR/connector.env"
echo "     sudo nano $ENV_DIR/collector.env"
echo ""
echo "  3. Services starten:"
echo "     sudo systemctl start iot-connector"
echo "     sudo systemctl start iot-collector"
echo ""
echo "  4. Logs prüfen:"
echo "     journalctl -u iot-connector -f"
echo "     journalctl -u iot-collector -f"
