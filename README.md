# IoT Azure Starter 🚀

Vollständiges Starter-Template: Python Sensor-Simulator → Azure IoT Hub → Azure Function → Cosmos DB → React Dashboard.

## Projektstruktur

```
iot-azure-starter/
├── simulator/          # Python IoT-Gerät Simulator
│   ├── simulator.py
│   └── requirements.txt
├── function/           # Azure Function (Backend)
│   ├── function_app.py
│   ├── host.json
│   ├── requirements.txt
│   └── local.settings.json   ← NIE in Git einchecken!
├── dashboard/          # React Frontend
│   ├── src/App.jsx
│   └── package.json
└── .github/workflows/
    └── deploy.yml      # CI/CD Pipeline
```

---

## Setup-Anleitung (Schritt für Schritt)

### Schritt 1 — Azure Ressourcen anlegen (Azure Portal)

1. **IoT Hub** anlegen
   - Azure Portal → "Ressource erstellen" → "IoT Hub"
   - Free Tier (F1) auswählen
   - Nach dem Anlegen: `IoT Hub → Geräte → + Gerät` → Name: `sensor-01`

2. **Cosmos DB** anlegen
   - Azure Portal → "Ressource erstellen" → "Azure Cosmos DB"
   - API: NoSQL auswählen
   - **Free Tier aktivieren** (wichtig!)
   - Nach dem Anlegen: Datenbank `iotdb` + Container `measurements` anlegen
   - Partition Key: `/deviceId`

3. **Azure Function App** anlegen
   - Azure Portal → "Ressource erstellen" → "Function App"
   - Runtime: Python 3.11
   - Plan: Consumption (Serverless)

4. **Azure Static Web Apps** anlegen
   - Azure Portal → "Ressource erstellen" → "Static Web App"
   - Mit GitHub Repo verbinden (Free Plan)

---

### Schritt 2 — Connection Strings holen

| Was | Wo im Portal |
|-----|-------------|
| IoT Hub Device Connection String | IoT Hub → Geräte → sensor-01 → Primäre Verbindungszeichenfolge |
| IoT Hub Event Hub Connection String | IoT Hub → Integrierte Endpunkte → Event Hub-kompatibler Endpunkt |
| Cosmos DB Connection String | Cosmos DB → Schlüssel → Primäre Verbindungszeichenfolge |
| Function Publish Profile | Function App → Übersicht → Veröffentlichungsprofil abrufen |
| Static Web App Token | Static Web App → Übersicht → Token für Bereitstellung verwalten |

---

### Schritt 3 — GitHub Secrets eintragen

In deinem GitHub Repo → Settings → Secrets → Actions:

| Secret Name | Wert |
|-------------|------|
| `AZURE_FUNCTION_APP_NAME` | Name deiner Function App |
| `AZURE_FUNCTION_PUBLISH_PROFILE` | Inhalt des Publish Profile XML |
| `AZURE_STATIC_WEB_APPS_API_TOKEN` | Deployment Token |
| `VITE_API_URL` | URL deiner Function App + `/api/measurements` |

---

### Schritt 4 — Simulator lokal starten

```bash
cd simulator
pip install -r requirements.txt

# Connection String in simulator.py eintragen, dann:
python simulator.py
```

---

### Schritt 5 — Dashboard lokal testen

```bash
cd dashboard
npm install
npm run dev
# → http://localhost:5173
```

---

### Schritt 6 — Deployment

```bash
git add .
git commit -m "Initial commit"
git push origin main
# GitHub Actions deployt automatisch
```

---

## Schwellwerte anpassen

In `dashboard/src/App.jsx`:

```js
const THRESHOLDS = {
  temperature: { warn: 28, critical: 35 },
  humidity:    { warn: 75, critical: 85 },
  pressure:    { warn: 1025, critical: 1035 },
};
```

## Kosten

Alles im Free Tier gehalten:
- IoT Hub F1: kostenlos (8.000 Nachrichten/Tag)
- Cosmos DB: kostenlos (1.000 RU/s, 25 GB)
- Azure Functions: kostenlos (1 Mio. Aufrufe/Monat)
- Static Web Apps: kostenlos
