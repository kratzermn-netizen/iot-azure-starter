const { app, output, input } = require("@azure/functions");

// ── Konfiguration ────────────────────────────────────────────────────────────
const COSMOS_DB_NAME = "iotdb";
const COSMOS_CONTAINER = "measurements";
const COSMOS_CONNECTION_SETTING = "COSMOS_DB_CONNECTION";
const IOT_HUB_CONNECTION_SETTING = "IOT_HUB_CONNECTION";
const EVENT_HUB_NAME = "iothub-ehub-iot-hub-ma-57404860-566d179e2c";
const CONSUMER_GROUP = "$Default";
const MEASUREMENTS_QUERY = "SELECT TOP 100 * FROM c ORDER BY c.timestamp DESC";
// ─────────────────────────────────────────────────────────────────────────────

const cosmosOutput = output.cosmosDB({
  databaseName: COSMOS_DB_NAME,
  containerName: COSMOS_CONTAINER,
  connection: COSMOS_CONNECTION_SETTING,
  createIfNotExists: true,
  partitionKey: "/deviceId",
});

const cosmosInput = input.cosmosDB({
  databaseName: COSMOS_DB_NAME,
  containerName: COSMOS_CONTAINER,
  connection: COSMOS_CONNECTION_SETTING,
  sqlQuery: MEASUREMENTS_QUERY,
});

// IoT Hub Trigger → Cosmos DB
app.eventHub("IoTHubTrigger", {
  connection: IOT_HUB_CONNECTION_SETTING,
  eventHubName: EVENT_HUB_NAME,
  consumerGroup: CONSUMER_GROUP,
  cardinality: "one",
  extraOutputs: [cosmosOutput],
  handler: async (event, context) => {
    try {
      const data = typeof event === "object" ? event : JSON.parse(event.toString());

      context.log(`Nachricht empfangen von: ${data.deviceId ?? "unbekannt"}`);

      const document = {
        id: `${data.deviceId}-${data.timestamp}`,
        deviceId: data.deviceId,
        timestamp: data.timestamp,
        temperature: data.temperature,
        humidity: data.humidity,
        pressure: data.pressure,
      };

      context.extraOutputs.set(cosmosOutput, document);
      context.log(`Gespeichert: Temp=${data.temperature}°C`);
    } catch (err) {
      context.log.error(`Fehler: ${err.message}`);
      throw err;
    }
  },
});

// HTTP GET /api/measurements
app.http("get_measurements", {
  route: "measurements",
  methods: ["GET"],
  authLevel: "anonymous",
  extraInputs: [cosmosInput],
  handler: async (req, context) => {
    const docs = context.extraInputs.get(cosmosInput);
    return {
      status: 200,
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
      },
      body: JSON.stringify(docs ?? []),
    };
  },
});
