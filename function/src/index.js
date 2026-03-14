const { app, output } = require("@azure/functions");

const cosmosOutput = output.cosmosDB({
  databaseName: "iotdb",
  containerName: "measurements",
  connection: "COSMOS_DB_CONNECTION",
  createIfNotExists: true,
  partitionKey: "/deviceId",
});

// IoT Hub Trigger → Cosmos DB
app.eventHub("IoTHubTrigger", {
  connection: "IOT_HUB_CONNECTION",
  eventHubName: "",
  consumerGroup: "$Default",
  cardinality: "one",
  extraOutputs: [cosmosOutput],
  handler: async (event, context) => {
    try {
      const raw = Buffer.isBuffer(event) ? event.toString("utf8") : JSON.stringify(event);
      const data = typeof event === "object" ? event : JSON.parse(raw);

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
      context.log.error(`Fehler beim Verarbeiten: ${err.message}`);
      throw err;
    }
  },
});

// HTTP GET /api/measurements → letzte 100 Messwerte
app.http("get_measurements", {
  route: "measurements",
  methods: ["GET"],
  authLevel: "anonymous",
  extraInputs: [
    require("@azure/functions").input.cosmosDB({
      databaseName: "iotdb",
      containerName: "measurements",
      connection: "COSMOS_DB_CONNECTION",
      sqlQuery: "SELECT TOP 100 * FROM c ORDER BY c.timestamp DESC",
    }),
  ],
  handler: async (req, context) => {
    const docs = context.extraInputs.get(context.options.extraInputs[0]);
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
