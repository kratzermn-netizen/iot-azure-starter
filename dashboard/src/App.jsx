import { useState, useEffect, useCallback } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";

// ──────────────────────────────────────────────
// KONFIGURATION
// ──────────────────────────────────────────────
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:7071/api/measurements";
const REFRESH_INTERVAL_MS = 10_000; // Alle 10 Sekunden aktualisieren

// Schwellwerte für Alarme
const THRESHOLDS = {
  temperature: { warn: 28, critical: 35 },
  humidity: { warn: 75, critical: 85 },
  pressure: { warn: 1025, critical: 1035 },
};

// ──────────────────────────────────────────────
// Helper
// ──────────────────────────────────────────────
function formatTime(iso) {
  return iso ? iso.substring(11, 19) : "";
}

function getStatus(value, thresholds) {
  if (Math.abs(value) >= thresholds.critical) return "critical";
  if (Math.abs(value) >= thresholds.warn) return "warn";
  return "ok";
}

// ──────────────────────────────────────────────
// Sub-Components
// ──────────────────────────────────────────────
function KpiCard({ label, value, unit, thresholds, color }) {
  const status = getStatus(value, thresholds);
  const statusColors = { ok: "#22c55e", warn: "#f59e0b", critical: "#ef4444" };
  const dot = statusColors[status];

  return (
    <div style={{
      background: "#0f1117",
      border: `1px solid ${dot}33`,
      borderRadius: 12,
      padding: "20px 24px",
      flex: 1,
      minWidth: 160,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <div style={{ width: 8, height: 8, borderRadius: "50%", background: dot }} />
        <span style={{ color: "#6b7280", fontSize: 13, fontFamily: "monospace" }}>{label}</span>
      </div>
      <div style={{ fontSize: 36, fontWeight: 700, color: "#f9fafb", fontFamily: "monospace" }}>
        {value !== null ? value.toFixed(1) : "—"}
        <span style={{ fontSize: 16, color: "#9ca3af", marginLeft: 4 }}>{unit}</span>
      </div>
    </div>
  );
}

function SensorChart({ data, dataKey, label, unit, color, threshold }) {
  return (
    <div style={{
      background: "#0f1117",
      border: "1px solid #1f2937",
      borderRadius: 12,
      padding: "20px 16px 8px",
    }}>
      <div style={{ color: "#9ca3af", fontSize: 13, fontFamily: "monospace", marginBottom: 12 }}>
        {label} <span style={{ color: "#4b5563" }}>({unit})</span>
      </div>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis
            dataKey="timestamp"
            tickFormatter={formatTime}
            tick={{ fill: "#4b5563", fontSize: 11, fontFamily: "monospace" }}
            interval="preserveStartEnd"
          />
          <YAxis tick={{ fill: "#4b5563", fontSize: 11, fontFamily: "monospace" }} />
          <Tooltip
            contentStyle={{ background: "#1f2937", border: "none", borderRadius: 8, fontFamily: "monospace" }}
            labelFormatter={formatTime}
            formatter={(v) => [`${v.toFixed(2)} ${unit}`, label]}
          />
          {threshold && (
            <ReferenceLine y={threshold.warn} stroke="#f59e0b" strokeDasharray="4 4" />
          )}
          {threshold && (
            <ReferenceLine y={threshold.critical} stroke="#ef4444" strokeDasharray="4 4" />
          )}
          <Line
            type="monotone"
            dataKey={dataKey}
            stroke={color}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ──────────────────────────────────────────────
// Main App
// ──────────────────────────────────────────────
export default function App() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(API_URL);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      // Älteste zuerst für Charts
      const sorted = [...json].sort((a, b) =>
        a.timestamp.localeCompare(b.timestamp)
      );
      setData(sorted);
      setLastUpdate(new Date().toLocaleTimeString("de-DE"));
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [fetchData]);

  const latest = data[data.length - 1] || null;

  return (
    <div style={{
      minHeight: "100vh",
      background: "#060912",
      color: "#f9fafb",
      fontFamily: "system-ui, sans-serif",
      padding: "32px 24px",
      maxWidth: 1100,
      margin: "0 auto",
    }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 32 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, letterSpacing: -0.5 }}>
            IoT Sensor Dashboard
          </h1>
          <div style={{ color: "#6b7280", fontSize: 13, fontFamily: "monospace", marginTop: 4 }}>
            {latest?.deviceId || "—"} · {data.length} Messwerte
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            background: "#0f1117", border: "1px solid #1f2937",
            borderRadius: 20, padding: "6px 14px", fontSize: 12, fontFamily: "monospace",
          }}>
            <div style={{
              width: 6, height: 6, borderRadius: "50%",
              background: error ? "#ef4444" : "#22c55e",
              animation: error ? "none" : "pulse 2s infinite",
            }} />
            {error ? `Fehler: ${error}` : `Live · ${lastUpdate || "…"}`}
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div style={{ display: "flex", gap: 16, marginBottom: 24, flexWrap: "wrap" }}>
        <KpiCard
          label="Temperatur"
          value={latest?.temperature ?? null}
          unit="°C"
          thresholds={THRESHOLDS.temperature}
          color="#3b82f6"
        />
        <KpiCard
          label="Luftfeuchtigkeit"
          value={latest?.humidity ?? null}
          unit="%"
          thresholds={THRESHOLDS.humidity}
          color="#8b5cf6"
        />
        <KpiCard
          label="Luftdruck"
          value={latest?.pressure ?? null}
          unit="hPa"
          thresholds={THRESHOLDS.pressure}
          color="#10b981"
        />
      </div>

      {/* Charts */}
      {loading ? (
        <div style={{ color: "#4b5563", textAlign: "center", padding: 60, fontFamily: "monospace" }}>
          Lade Daten…
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <SensorChart
            data={data}
            dataKey="temperature"
            label="Temperatur"
            unit="°C"
            color="#3b82f6"
            threshold={THRESHOLDS.temperature}
          />
          <SensorChart
            data={data}
            dataKey="humidity"
            label="Luftfeuchtigkeit"
            unit="%"
            color="#8b5cf6"
            threshold={THRESHOLDS.humidity}
          />
          <SensorChart
            data={data}
            dataKey="pressure"
            label="Luftdruck"
            unit="hPa"
            color="#10b981"
            threshold={THRESHOLDS.pressure}
          />
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}

