/**
 * Jest tests for the Azure Function handler logic.
 *
 * The handler logic is extracted inline here rather than importing index.js
 * directly, because index.js calls app.eventHub / app.http at module load
 * time and has side-effects that require a live @azure/functions runtime.
 *
 * Run with: npm test  (from the /function directory)
 */

// ---------------------------------------------------------------------------
// Extracted pure logic (mirrors index.js exactly)
// ---------------------------------------------------------------------------

/**
 * Builds a Cosmos DB document from a raw IoT Hub event.
 * Returns { document, logMessage }.
 */
function buildDocument(event) {
  const data = typeof event === "object" ? event : JSON.parse(event.toString());
  const deviceLabel = data.deviceId ?? "unbekannt";
  const document = {
    id: `${data.deviceId}-${data.timestamp}`,
    deviceId: data.deviceId,
    timestamp: data.timestamp,
    temperature: data.temperature,
    humidity: data.humidity,
    pressure: data.pressure,
  };
  return { document, deviceLabel };
}

/**
 * Builds the HTTP response for GET /measurements.
 */
function buildMeasurementsResponse(docs) {
  return {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
    },
    body: JSON.stringify(docs ?? []),
  };
}

// ---------------------------------------------------------------------------
// Tests — IoTHubTrigger handler logic
// ---------------------------------------------------------------------------

describe("buildDocument — IoT Hub event processing", () => {
  const sampleEvent = {
    deviceId: "sensor-01",
    timestamp: "2024-01-15T12:00:00.000Z",
    temperature: 23.45,
    humidity: 58.2,
    pressure: 1013.1,
  };

  test("returns a document with the correct id format (deviceId-timestamp)", () => {
    const { document } = buildDocument(sampleEvent);
    expect(document.id).toBe("sensor-01-2024-01-15T12:00:00.000Z");
  });

  test("copies deviceId into the document", () => {
    const { document } = buildDocument(sampleEvent);
    expect(document.deviceId).toBe("sensor-01");
  });

  test("copies timestamp into the document", () => {
    const { document } = buildDocument(sampleEvent);
    expect(document.timestamp).toBe("2024-01-15T12:00:00.000Z");
  });

  test("copies temperature into the document", () => {
    const { document } = buildDocument(sampleEvent);
    expect(document.temperature).toBe(23.45);
  });

  test("copies humidity into the document", () => {
    const { document } = buildDocument(sampleEvent);
    expect(document.humidity).toBe(58.2);
  });

  test("copies pressure into the document", () => {
    const { document } = buildDocument(sampleEvent);
    expect(document.pressure).toBe(1013.1);
  });

  test("document has exactly the expected keys", () => {
    const { document } = buildDocument(sampleEvent);
    expect(Object.keys(document).sort()).toEqual(
      ["deviceId", "humidity", "id", "pressure", "temperature", "timestamp"].sort()
    );
  });
});

describe("buildDocument — JSON string event input", () => {
  const sampleEvent = {
    deviceId: "sensor-02",
    timestamp: "2024-01-15T13:00:00.000Z",
    temperature: 25.0,
    humidity: 60.0,
    pressure: 1012.0,
  };

  test("parses a JSON string and builds the correct document", () => {
    const jsonString = JSON.stringify(sampleEvent);
    const { document } = buildDocument(jsonString);
    expect(document.deviceId).toBe("sensor-02");
    expect(document.temperature).toBe(25.0);
  });

  test("JSON string produces the same document as an equivalent object", () => {
    const fromObject = buildDocument(sampleEvent).document;
    const fromString = buildDocument(JSON.stringify(sampleEvent)).document;
    expect(fromObject).toEqual(fromString);
  });

  test("Buffer-like object with toString() returning JSON is handled", () => {
    const bufferLike = {
      toString: () => JSON.stringify(sampleEvent),
    };
    // typeof bufferLike === "object", so it passes through the object branch
    // and we'd access bufferLike.deviceId which is undefined.
    // This test documents the *current* behaviour: object path is taken.
    const { document } = buildDocument(bufferLike);
    // deviceId is undefined on the buffer-like wrapper
    expect(document.deviceId).toBeUndefined();
  });
});

describe("buildDocument — missing deviceId falls back to 'unbekannt'", () => {
  test("deviceLabel is 'unbekannt' when deviceId is missing", () => {
    const eventWithoutDeviceId = {
      timestamp: "2024-01-15T12:00:00.000Z",
      temperature: 20.0,
      humidity: 50.0,
      pressure: 1013.0,
    };
    const { deviceLabel } = buildDocument(eventWithoutDeviceId);
    expect(deviceLabel).toBe("unbekannt");
  });

  test("deviceLabel equals deviceId when deviceId is present", () => {
    const event = {
      deviceId: "sensor-01",
      timestamp: "2024-01-15T12:00:00.000Z",
      temperature: 20.0,
      humidity: 50.0,
      pressure: 1013.0,
    };
    const { deviceLabel } = buildDocument(event);
    expect(deviceLabel).toBe("sensor-01");
  });

  test("document.id uses 'undefined' when deviceId is absent (current behaviour)", () => {
    const eventWithoutDeviceId = {
      timestamp: "2024-01-15T12:00:00.000Z",
      temperature: 20.0,
      humidity: 50.0,
      pressure: 1013.0,
    };
    const { document } = buildDocument(eventWithoutDeviceId);
    expect(document.id).toBe("undefined-2024-01-15T12:00:00.000Z");
  });
});

// ---------------------------------------------------------------------------
// Tests — get_measurements HTTP handler logic
// ---------------------------------------------------------------------------

describe("buildMeasurementsResponse — GET /measurements", () => {
  test("returns HTTP 200", () => {
    const response = buildMeasurementsResponse([]);
    expect(response.status).toBe(200);
  });

  test("Content-Type header is application/json", () => {
    const response = buildMeasurementsResponse([]);
    expect(response.headers["Content-Type"]).toBe("application/json");
  });

  test("CORS header allows all origins", () => {
    const response = buildMeasurementsResponse([]);
    expect(response.headers["Access-Control-Allow-Origin"]).toBe("*");
  });

  test("body is a JSON string (not an object)", () => {
    const response = buildMeasurementsResponse([]);
    expect(typeof response.body).toBe("string");
  });

  test("returns empty array when docs is null", () => {
    const response = buildMeasurementsResponse(null);
    expect(JSON.parse(response.body)).toEqual([]);
  });

  test("returns empty array when docs is undefined", () => {
    const response = buildMeasurementsResponse(undefined);
    expect(JSON.parse(response.body)).toEqual([]);
  });

  test("returns empty array when docs is an empty array", () => {
    const response = buildMeasurementsResponse([]);
    expect(JSON.parse(response.body)).toEqual([]);
  });

  test("returns documents as a JSON array", () => {
    const docs = [
      { id: "sensor-01-ts1", deviceId: "sensor-01", temperature: 22.5 },
      { id: "sensor-01-ts2", deviceId: "sensor-01", temperature: 23.1 },
    ];
    const response = buildMeasurementsResponse(docs);
    const parsed = JSON.parse(response.body);
    expect(parsed).toHaveLength(2);
    expect(parsed[0].id).toBe("sensor-01-ts1");
    expect(parsed[1].temperature).toBe(23.1);
  });

  test("serialises all document fields into the body", () => {
    const doc = {
      id: "sensor-01-2024-01-15T12:00:00.000Z",
      deviceId: "sensor-01",
      timestamp: "2024-01-15T12:00:00.000Z",
      temperature: 22.5,
      humidity: 58.0,
      pressure: 1013.25,
    };
    const response = buildMeasurementsResponse([doc]);
    const parsed = JSON.parse(response.body);
    expect(parsed[0]).toEqual(doc);
  });
});
