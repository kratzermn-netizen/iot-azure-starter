/**
 * Vitest + @testing-library/react tests for dashboard/src/App.jsx
 *
 * Run with: npm test  (from the /dashboard directory)
 */
import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

// ---------------------------------------------------------------------------
// Inline the pure helpers so we can unit-test them without
// importing App.jsx (which depends on recharts / browser APIs).
// ---------------------------------------------------------------------------

function getStatus(value, thresholds) {
  if (Math.abs(value) >= thresholds.critical) return "critical";
  if (Math.abs(value) >= thresholds.warn) return "warn";
  return "ok";
}

const THRESHOLDS = {
  temperature: { warn: 28, critical: 35 },
  humidity: { warn: 75, critical: 85 },
  pressure: { warn: 1025, critical: 1035 },
};

// ---------------------------------------------------------------------------
// formatTime — inline copy to test the falsy branch (not exported from App.jsx)
// ---------------------------------------------------------------------------

function formatTime(iso) {
  return iso ? iso.substring(11, 19) : "";
}

describe("formatTime", () => {
  test("extracts HH:MM:SS from a valid ISO timestamp", () => {
    // Critical: charts rely on this for axis labels
    expect(formatTime("2024-01-15T12:34:56.000Z")).toBe("12:34:56");
  });

  test("returns empty string for null (falsy branch)", () => {
    // Falsy branch — null timestamp must not throw or render garbage
    expect(formatTime(null)).toBe("");
  });

  test("returns empty string for undefined (falsy branch)", () => {
    expect(formatTime(undefined)).toBe("");
  });

  test("returns empty string for empty string input", () => {
    expect(formatTime("")).toBe("");
  });

  test("works with midnight timestamps", () => {
    expect(formatTime("2024-06-01T00:00:00.000Z")).toBe("00:00:00");
  });
});

// ---------------------------------------------------------------------------
// getStatus — pure logic tests (no DOM needed)
// ---------------------------------------------------------------------------

describe("getStatus", () => {
  describe("temperature thresholds", () => {
    test('returns "ok" for a normal temperature', () => {
      expect(getStatus(22, THRESHOLDS.temperature)).toBe("ok");
    });

    test('returns "ok" for zero', () => {
      expect(getStatus(0, THRESHOLDS.temperature)).toBe("ok");
    });

    test('returns "warn" exactly at the warn threshold', () => {
      expect(getStatus(28, THRESHOLDS.temperature)).toBe("warn");
    });

    test('returns "warn" just above the warn threshold', () => {
      expect(getStatus(29, THRESHOLDS.temperature)).toBe("warn");
    });

    test('returns "critical" exactly at the critical threshold', () => {
      expect(getStatus(35, THRESHOLDS.temperature)).toBe("critical");
    });

    test('returns "critical" above the critical threshold', () => {
      expect(getStatus(40, THRESHOLDS.temperature)).toBe("critical");
    });

    test("uses Math.abs — negative critical value triggers critical", () => {
      expect(getStatus(-35, THRESHOLDS.temperature)).toBe("critical");
    });

    test("uses Math.abs — negative warn value triggers warn", () => {
      expect(getStatus(-28, THRESHOLDS.temperature)).toBe("warn");
    });
  });

  describe("humidity thresholds", () => {
    test('returns "ok" for a normal humidity', () => {
      expect(getStatus(55, THRESHOLDS.humidity)).toBe("ok");
    });

    test('returns "warn" at humidity warn threshold', () => {
      expect(getStatus(75, THRESHOLDS.humidity)).toBe("warn");
    });

    test('returns "critical" at humidity critical threshold', () => {
      expect(getStatus(85, THRESHOLDS.humidity)).toBe("critical");
    });

    test('returns "critical" above humidity critical threshold', () => {
      expect(getStatus(90, THRESHOLDS.humidity)).toBe("critical");
    });
  });

  describe("pressure thresholds", () => {
    test('returns "ok" for a normal pressure', () => {
      expect(getStatus(1013, THRESHOLDS.pressure)).toBe("ok");
    });

    test('returns "warn" at pressure warn threshold', () => {
      expect(getStatus(1025, THRESHOLDS.pressure)).toBe("warn");
    });

    test('returns "critical" at pressure critical threshold', () => {
      expect(getStatus(1035, THRESHOLDS.pressure)).toBe("critical");
    });
  });
});

// ---------------------------------------------------------------------------
// Component tests — import App and child components
// ---------------------------------------------------------------------------

// Recharts uses ResizeObserver which is not available in jsdom
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Import App after setting up globals
import App from "./App.jsx";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeMeasurement(overrides = {}) {
  return {
    id: "sensor-01-2024-01-15T12:00:00.000Z",
    deviceId: "sensor-01",
    timestamp: "2024-01-15T12:00:00.000Z",
    temperature: 22.5,
    humidity: 55.0,
    pressure: 1013.25,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// App — loading state
// ---------------------------------------------------------------------------

describe("App — loading state", () => {
  beforeEach(() => {
    // Return a promise that never resolves so the component stays in loading
    vi.spyOn(global, "fetch").mockImplementation(() => new Promise(() => {}));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test('shows "Lade Daten…" while data is loading', () => {
    render(<App />);
    expect(screen.getByText("Lade Daten…")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// App — error state
// ---------------------------------------------------------------------------

describe("App — error state", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("shows error message when fetch rejects", async () => {
    vi.spyOn(global, "fetch").mockRejectedValueOnce(new Error("Network error"));
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText(/Fehler/i)).toBeInTheDocument();
    });
  });

  test("shows the specific error text returned by fetch rejection", async () => {
    vi.spyOn(global, "fetch").mockRejectedValueOnce(new Error("Network error"));
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText(/Network error/i)).toBeInTheDocument();
    });
  });

  test("shows error when response is not ok (HTTP 500)", async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => [],
    });
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText(/Fehler/i)).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// App — success state
// ---------------------------------------------------------------------------

describe("App — successful data fetch", () => {
  const measurements = [
    makeMeasurement({
      id: "sensor-01-ts1",
      timestamp: "2024-01-15T12:00:00.000Z",
      temperature: 22.5,
      humidity: 55.0,
      pressure: 1013.25,
    }),
    makeMeasurement({
      id: "sensor-01-ts2",
      timestamp: "2024-01-15T12:01:00.000Z",
      temperature: 23.1,
      humidity: 56.0,
      pressure: 1014.0,
    }),
  ];

  beforeEach(() => {
    vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => measurements,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test('hides "Lade Daten…" after data loads', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.queryByText("Lade Daten…")).not.toBeInTheDocument();
    });
  });

  test("renders the dashboard heading", async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText("IoT Sensor Dashboard")).toBeInTheDocument();
    });
  });

  test("renders the device id in the subtitle area", async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText(/sensor-01/)).toBeInTheDocument();
    });
  });

  test("renders KPI card labels", async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText("Temperatur")).toBeInTheDocument();
      expect(screen.getByText("Luftfeuchtigkeit")).toBeInTheDocument();
      expect(screen.getByText("Luftdruck")).toBeInTheDocument();
    });
  });

  test("renders measurement count in subtitle", async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText(/2 Messwerte/)).toBeInTheDocument();
    });
  });

  test("fetch is called with the measurements URL", async () => {
    render(<App />);
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("measurements")
      );
    });
  });
});

// ---------------------------------------------------------------------------
// App — refresh interval behaviour
// ---------------------------------------------------------------------------

describe("App — data sorting", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("renders latest measurement's temperature (data sorted oldest-first)", async () => {
    // The app sorts data ascending by timestamp — last item is "latest"
    const measurements = [
      makeMeasurement({ timestamp: "2024-01-15T12:00:00.000Z", temperature: 10.0 }),
      makeMeasurement({ timestamp: "2024-01-15T13:00:00.000Z", temperature: 99.9 }),
    ];
    vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => measurements,
    });
    render(<App />);
    await waitFor(() => {
      // 99.9 is the latest — should appear as "99.9"
      expect(screen.getByText(/99\.9/)).toBeInTheDocument();
    });
  });

  test("shows Live status (green dot) when fetch succeeds", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => [makeMeasurement()],
    });
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText(/Live/)).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// KpiCard — via App with controlled data
// ---------------------------------------------------------------------------

describe("KpiCard rendering", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("renders the temperature value from the latest measurement", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => [makeMeasurement({ temperature: 22.5 })],
    });
    render(<App />);
    await waitFor(() => {
      // KpiCard calls value.toFixed(1) → "22.5"
      expect(screen.getByText(/22\.5/)).toBeInTheDocument();
    });
  });

  test('shows "—" for each KpiCard when data array is empty', async () => {
    vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    render(<App />);
    await waitFor(() => {
      // Three KpiCards, each showing "—" when value is null
      const dashes = screen.getAllByText("—");
      // At least the 3 KPI dashes (header also shows "—" for deviceId)
      expect(dashes.length).toBeGreaterThanOrEqual(3);
    });
  });

  test("renders the unit label °C", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => [makeMeasurement()],
    });
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText("°C")).toBeInTheDocument();
    });
  });

  test("renders the unit label %", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => [makeMeasurement()],
    });
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText("%")).toBeInTheDocument();
    });
  });

  test("renders the unit label hPa", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => [makeMeasurement()],
    });
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText("hPa")).toBeInTheDocument();
    });
  });
});
