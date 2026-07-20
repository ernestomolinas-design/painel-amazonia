import React, { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CalendarDays,
  CloudRain,
  Database,
  RefreshCcw,
  Ship,
  TrendingDown,
  TrendingUp,
  Waves,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const DASHBOARD_DATA_URL = "/data/dashboard.json";

const MAIN_STATIONS = [
  { id: "manaus", name: "Manaus", river: "Rio Negro / Amazonas", basin: "Pontos críticos", current: 2746, delta7: 28, delta30: 106, risk: "atenção", mlt: 2680, p95: 2920, p05: 2140 },
  { id: "itacoatiara", name: "Itacoatiara", river: "Rio Amazonas", basin: "Pontos críticos", current: 1339, delta7: 18, delta30: 91, risk: "baixo", mlt: 1290, p95: 1510, p05: 850 },
  { id: "obidos", name: "Óbidos", river: "Rio Amazonas", basin: "Pontos críticos", current: 740, delta7: 14, delta30: 88, risk: "baixo", mlt: 705, p95: 890, p05: 390 },
  { id: "santarem", name: "Santarém", river: "Rio Amazonas / Tapajós", basin: "Pontos críticos", current: 708, delta7: 11, delta30: 79, risk: "baixo", mlt: 675, p95: 820, p05: 360 },
];

const UPPER_BASIN_STATIONS = [
  { id: "tabatinga", name: "Tabatinga", river: "Solimões", basin: "Solimões", current: 1169, delta7: -8, delta30: 42, risk: "atenção", mlt: 1210, p95: 1450, p05: 760 },
  { id: "porto_velho", name: "Porto Velho", river: "Madeira", basin: "Madeira", current: 1295, delta7: -22, delta30: -74, risk: "atenção", mlt: 1360, p95: 1620, p05: 650 },
  { id: "itaituba", name: "Itaituba", river: "Tapajós", basin: "Tapajós", current: 712, delta7: 6, delta30: 37, risk: "baixo", mlt: 690, p95: 880, p05: 390 },
  { id: "labrea", name: "Lábrea", river: "Purus", basin: "Purus", current: 1184, delta7: -11, delta30: 21, risk: "atenção", mlt: 1215, p95: 1480, p05: 720 },
  { id: "barcelos", name: "Barcelos", river: "Rio Negro", basin: "Negro", current: 500, delta7: 0, delta30: 0, risk: "baixo", mlt: 500, p95: 900, p05: 100 },
  { id: "altamira", name: "Altamira", river: "Rio Xingu", basin: "Xingu", current: 520, delta7: 0, delta30: 0, risk: "baixo", mlt: 520, p95: 950, p05: 180 },
];

const RAINFALL = [
  { basin: "Madeira", obs7: 42, fcst7: 35, obs30: 188 },
  { basin: "Tapajós", obs7: 36, fcst7: 31, obs30: 164 },
  { basin: "Purus", obs7: 51, fcst7: 44, obs30: 208 },
  { basin: "Negro", obs7: 92, fcst7: 80, obs30: 316 },
  { basin: "Solimões", obs7: 78, fcst7: 62, obs30: 284 },
  { basin: "Xingu", obs7: 44, fcst7: 38, obs30: 180 },
  { basin: "Baixo Amazonas", obs7: 55, fcst7: 48, obs30: 220 },
];

const MONTH_LABELS = ["Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez", "Jan", "Fev", "Mar", "Abr", "Mai"];
const MONTH_TICK_INDEXES = MONTH_LABELS.map((_, i) => Math.round(i * (365 / 12)));
const COLORS = ["#2563eb", "#16a34a", "#ea580c", "#7c3aed", "#0891b2", "#be123c", "#4f46e5", "#ca8a04", "#0f766e"];

const DEMO = {
  updatedAt: "2026-05-20T08:00:00-03:00",
  sourceMode: "demo",
  mainStations: MAIN_STATIONS,
  upperBasinStations: UPPER_BASIN_STATIONS,
  rainfall: RAINFALL,
  climateHistory: null,
};

function isNum(v) {
  return typeof v === "number" && Number.isFinite(v);
}

function num(v, fallback = 0) {
  return isNum(v) ? v : fallback;
}

function activeStations(stations) {
  return Array.isArray(stations)
    ? stations.filter((s) => isNum(s?.current) && s?.source !== "demo-fallback")
    : [];
}

function normalizeData(raw) {
  if (!raw || typeof raw !== "object") return DEMO;
  return {
    updatedAt: raw.updatedAt || DEMO.updatedAt,
    sourceMode: raw.sourceMode || "operational",
    mainStations: Array.isArray(raw.mainStations) && raw.mainStations.length ? raw.mainStations : DEMO.mainStations,
    upperBasinStations: Array.isArray(raw.upperBasinStations) && raw.upperBasinStations.length ? raw.upperBasinStations : DEMO.upperBasinStations,
    rainfall: Array.isArray(raw.rainfall) && raw.rainfall.length ? raw.rainfall : DEMO.rainfall,
    climateHistory: Array.isArray(raw.climateHistory) && raw.climateHistory.length ? raw.climateHistory : null,
    metadata: raw.metadata || {},
  };
}

function useDashboardData() {
  const [state, setState] = useState({ data: DEMO, status: "demo", error: null });

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const res = await fetch(DASHBOARD_DATA_URL, { signal: controller.signal, cache: "no-store" });
        if (res.status === 404) {
          setState({ data: DEMO, status: "demo", error: null });
          return;
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        setState({ data: normalizeData(await res.json()), status: "operational", error: null });
      } catch (err) {
        if (err.name === "AbortError") return;
        setState({ data: DEMO, status: "demo", error: err.message || "Falha ao carregar dados" });
      }
    }
    load();
    return () => controller.abort();
  }, []);

  return state;
}

function statusBanner(status, error) {
  if (status === "operational") {
    return { className: "border-emerald-200 bg-emerald-50 text-emerald-900", text: "Dados operacionais carregados de /data/dashboard.json." };
  }
  return {
    className: "border-slate-200 bg-white text-slate-700",
    text: error ? `Modo demonstração ativo. Detalhe: ${error}` : "Modo demonstração ativo. Quando /data/dashboard.json existir, o painel passa automaticamente para dados operacionais.",
  };
}

function formatUpdatedAt(value) {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value || "sem data";
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short", timeZone: "America/Sao_Paulo" }).format(d);
}

function formatDateLabel(dateValue, windowType) {
  const d = new Date(`${dateValue}T00:00:00`);
  if (Number.isNaN(d.getTime())) return "";
  if (windowType === "30d") {
    return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", timeZone: "America/Sao_Paulo" }).format(d);
  }
  return new Intl.DateTimeFormat("pt-BR", { month: "short", timeZone: "America/Sao_Paulo" }).format(d).replace(".", "").replace(/^./, (c) => c.toUpperCase());
}

function formatMonthlyTick(value) {
  const i = MONTH_TICK_INDEXES.indexOf(value);
  return i >= 0 ? MONTH_LABELS[i] : "";
}

function normalizePoint(point, index, station, windowType) {
  const level = num(point?.level, num(point?.cota, null));
  if (!isNum(level)) return null;
  const mlt = num(point?.mlt, num(station.mlt, level));
  const p95 = num(point?.p95, num(station.p95, mlt + 300));
  const p05 = num(point?.p05, num(station.p05, mlt - 300));
  const range = Math.max(1, p95 - p05);

  return {
    index,
    label: windowType === "30d" ? formatDateLabel(point?.date, "30d") || String(index + 1) : "",
    monthLabel: windowType === "12m" ? formatDateLabel(point?.date, "12m") : "",
    cota: level,
    relativoMlt: Math.round(level - mlt),
    normalizado: Math.round(((level - p05) / range) * 100),
  };
}

function seriesFromRealData(station, key, expectedLength, windowType) {
  if (!Array.isArray(station?.[key])) return [];
  const series = station[key].map((p, i) => normalizePoint(p, i, station, windowType)).filter(Boolean).slice(-expectedLength);
  return series.map((p, i) => ({ ...p, index: i }));
}

function synthetic30(station) {
  if (!isNum(station?.current)) return [];
  const current = station.current;
  const delta30 = num(station.delta30, 0);
  const mlt = num(station.mlt, current);
  const p95 = num(station.p95, mlt + 300);
  const p05 = num(station.p05, mlt - 300);
  const range = Math.max(1, p95 - p05);

  return Array.from({ length: 30 }, (_, i) => {
    const trend = current - delta30 + (delta30 / 29) * i;
    const cota = Math.round(trend + Math.sin(i / 2.8) * 10 + Math.cos(i / 4.1) * 5);
    return {
      index: i,
      label: `${String(i + 1).padStart(2, "0")}/05`,
      cota,
      relativoMlt: Math.round(cota - mlt),
      normalizado: Math.round(((cota - p05) / range) * 100),
    };
  });
}

function synthetic12(station) {
  if (!isNum(station?.current)) return [];
  const current = station.current;
  const delta30 = num(station.delta30, 0);
  const mlt = num(station.mlt, current);
  const p95 = num(station.p95, mlt + 300);
  const p05 = num(station.p05, mlt - 300);
  const range = Math.max(1, p95 - p05);

  return Array.from({ length: 365 }, (_, i) => {
    const phase = (i / 365) * Math.PI * 2;
    const cota = Math.round(mlt + Math.sin(phase - 1.25) * 180 + Math.sin(phase * 2.05) * 34 + (i / 364) * delta30 * 1.8);
    return {
      index: i,
      monthLabel: formatMonthlyTick(i),
      cota,
      relativoMlt: Math.round(cota - mlt),
      normalizado: Math.round(((cota - p05) / range) * 100),
    };
  });
}

function make30DaySeries(station) {
  const real = seriesFromRealData(station, "levels30d", 30, "30d");
  return real.length ? real : synthetic30(station);
}

function addMonthlyTicks(series) {
  return series.map((p, i) => ({ ...p, index: i, monthLabel: MONTH_TICK_INDEXES.includes(i) ? p.monthLabel || formatMonthlyTick(i) : "" }));
}

function make12MonthSeries(station) {
  const real = seriesFromRealData(station, "levels12m", 365, "12m");
  return real.length ? addMonthlyTicks(real) : synthetic12(station);
}

function pointValue(point, mode, series) {
  if (!point) return null;
  if (mode === "deltaInicio") {
    const first = series.find((p) => p && isNum(p.cota));
    return first && isNum(point.cota) ? Math.round(point.cota - first.cota) : null;
  }
  return point[mode];
}

function makeMultiStationSeries(stations, windowType, mode) {
  const list = activeStations(stations);
  const length = windowType === "30d" ? 30 : 365;
  const make = windowType === "30d" ? make30DaySeries : make12MonthSeries;
  const map = new Map(list.map((s) => [s.id, make(s)]));

  return Array.from({ length }, (_, i) => {
    const firstSeries = map.get(list[0]?.id) || [];
    const row = { index: i, label: firstSeries[i]?.label || "", monthLabel: firstSeries[i]?.monthLabel || "" };
    list.forEach((station) => {
      const series = map.get(station.id) || [];
      const value = pointValue(series[i], mode, series);
      if (isNum(value)) row[station.id] = value;
    });
    return row;
  });
}

function getZoomedYDomain(data, stations, padding = 6) {
  const values = data.flatMap((row) => activeStations(stations).map((s) => row[s.id]).filter(isNum));
  if (!values.length) return ["auto", "auto"];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min;
  const pad = Math.max(padding, Math.ceil(range * 0.08));
  return min === max ? [Math.floor(min - padding), Math.ceil(max + padding)] : [Math.floor(min - pad), Math.ceil(max + pad)];
}

function buildClimateHistory() {
  const labels = ["Jan/24", "Fev/24", "Mar/24", "Abr/24", "Mai/24", "Jun/24", "Jul/24", "Ago/24", "Set/24", "Out/24", "Nov/24", "Dez/24", "Jan/25", "Fev/25", "Mar/25", "Abr/25", "Mai/25", "Jun/25", "Jul/25", "Ago/25", "Set/25", "Out/25", "Nov/25", "Dez/25", "Jan/26", "Fev/26", "Mar/26", "Abr/26", "Mai/26"];

  return labels.map((label, i) => {
    const nino34 = Math.round((Math.sin(i / 4.8) * 1.05 + Math.cos(i / 8) * 0.38 + 0.28) * 100) / 100;
    const atlNorth = Math.round((Math.cos(i / 5.2) * 0.42 + 0.42) * 100) / 100;
    const atlSouth = Math.round((Math.sin(i / 6.4) * 0.34 + 0.36) * 100) / 100;
    return { label, nino34, atlNorth, atlSouth, atlDipole: Math.round((atlNorth - atlSouth) * 100) / 100 };
  });
}

function basinSummary(stations) {
  const grouped = activeStations(stations).reduce((acc, station) => {
    acc[station.basin] = acc[station.basin] || [];
    acc[station.basin].push(station);
    return acc;
  }, {});

  return Object.entries(grouped).map(([basin, items]) => {
    const avgRelMlt = Math.round(items.reduce((sum, item) => sum + (item.current - num(item.mlt, item.current)), 0) / items.length);
    const avgDelta7 = Math.round(items.reduce((sum, item) => sum + num(item.delta7, 0), 0) / items.length);
    const worstRisk = items.some((item) => item.risk === "elevado") ? "elevado" : items.some((item) => item.risk === "atenção") ? "atenção" : "baixo";
    return { basin, stations: items.length, avgRelMlt, avgDelta7, worstRisk };
  });
}

function riskBadgeClasses(risk) {
  if (risk === "baixo") return "bg-emerald-100 text-emerald-800";
  if (risk === "atenção") return "bg-amber-100 text-amber-800";
  if (risk === "elevado") return "bg-orange-100 text-orange-800";
  return "bg-red-100 text-red-800";
}

function riskLabel(risk) {
  if (risk === "baixo") return "Baixo";
  if (risk === "atenção") return "Atenção";
  if (risk === "elevado") return "Elevado";
  return "Crítico";
}

function runSelfTests() {
  const main30 = makeMultiStationSeries(MAIN_STATIONS, "30d", "deltaInicio");
  const main12 = makeMultiStationSeries(MAIN_STATIONS, "12m", "cota");
  const upper30 = makeMultiStationSeries(UPPER_BASIN_STATIONS, "30d", "deltaInicio");
  const basins = basinSummary(UPPER_BASIN_STATIONS);

  return [
    { name: "Painel principal tem quatro estações críticas", pass: activeStations(MAIN_STATIONS).length === 4 },
    { name: "Gráfico principal de 30 dias tem 30 linhas", pass: main30.length === 30 },
    { name: "Gráfico principal de 12 meses tem 365 linhas", pass: main12.length === 365 },
    { name: "Séries de 30 dias começam em zero", pass: main30[0].manaus === 0 && upper30[0].tabatinga === 0 },
    { name: "Alta bacia usa uma sentinela por bacia", pass: activeStations(UPPER_BASIN_STATIONS).length === 6 },
    { name: "Bacias Madeira, Tapajós, Purus, Negro, Solimões e Xingu presentes", pass: ["Madeira", "Tapajós", "Purus", "Negro", "Solimões", "Xingu"].every((b) => basins.some((x) => x.basin === b)) },
    { name: "Diagnóstico climático aceita valores nulos", pass: getDiagnostics(MAIN_STATIONS, UPPER_BASIN_STATIONS, [{ nino34: null, atlDipole: null }])[2].value.includes("0.0") },
  ];
}

function RiskBadge({ risk }) {
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${riskBadgeClasses(risk)}`}>{riskLabel(risk)}</span>;
}

function Panel({ title, subtitle, children, icon: Icon }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-100 px-5 py-4">
        <div className="flex items-start gap-3">
          {Icon ? <div className="rounded-xl bg-slate-100 p-2"><Icon className="h-5 w-5" /></div> : null}
          <div>
            <h2 className="text-lg font-semibold">{title}</h2>
            {subtitle ? <p className="mt-1 text-sm text-slate-500">{subtitle}</p> : null}
          </div>
        </div>
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function Table({ rows, compact = false }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-slate-600">
            <th className="px-3 py-2">Estação</th>
            <th className="px-3 py-2">Bacia/Rio</th>
            <th className="px-3 py-2">Cota</th>
            <th className="px-3 py-2">7 dias</th>
            <th className="px-3 py-2">30 dias</th>
            <th className="px-3 py-2">Rel. clim. diária</th>
            <th className="px-3 py-2">Risco</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((station) => {
            const relMlt = station.current - num(station.mlt, station.current);
            return (
              <tr key={station.id} className="border-b border-slate-100">
                <td className="px-3 py-2 font-medium">{station.name}</td>
                <td className="px-3 py-2 text-slate-600">{compact ? station.basin : `${station.basin} · ${station.river}`}</td>
                <td className="px-3 py-2">{station.current} cm</td>
                <td className="px-3 py-2">{num(station.delta7) >= 0 ? "+" : ""}{num(station.delta7)} cm</td>
                <td className="px-3 py-2">{num(station.delta30) >= 0 ? "+" : ""}{num(station.delta30)} cm</td>
                <td className="px-3 py-2">{relMlt >= 0 ? "+" : ""}{relMlt} cm</td>
                <td className="px-3 py-2"><RiskBadge risk={station.risk} /></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function MultiStationLineChart({ data, stations, mode, yLabel, height = 430, zeroLine = false, monthlyTicks = false, yDomain }) {
  const list = activeStations(stations);
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
          <CartesianGrid vertical={false} strokeDasharray="4 8" strokeOpacity={0.35} />
          <XAxis
            dataKey={monthlyTicks ? "index" : "label"}
            type={monthlyTicks ? "number" : "category"}
            ticks={monthlyTicks ? MONTH_TICK_INDEXES : undefined}
            tickFormatter={monthlyTicks ? formatMonthlyTick : undefined}
            tick={{ fontSize: 12 }}
            interval={0}
            minTickGap={monthlyTicks ? 26 : 5}
          />
          <YAxis domain={yDomain} tick={{ fontSize: 12 }} label={{ value: yLabel, angle: -90, position: "insideLeft" }} />
          <Tooltip />
          <Legend />
          {zeroLine ? <ReferenceLine y={0} strokeDasharray="4 4" /> : null}
          {list.map((station, i) => (
            <Line
              key={`${mode}_${station.id}`}
              type="monotone"
              dataKey={station.id}
              name={station.name}
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={2.4}
              dot={false}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function BasinSummaryCards({ rows }) {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-5">
      {rows.map((row) => {
        const Icon = row.avgDelta7 >= 0 ? TrendingUp : TrendingDown;
        return (
          <div key={row.basin} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="font-semibold">{row.basin}</p>
                <p className="text-xs text-slate-500">1 estação sentinela</p>
              </div>
              <RiskBadge risk={row.worstRisk} />
            </div>
            <div className="mt-4 flex items-center gap-2 text-sm">
              <Icon className="h-4 w-4" />
              <span>{row.avgDelta7 >= 0 ? "+" : ""}{row.avgDelta7} cm em 7 dias</span>
            </div>
            <p className="mt-1 text-sm text-slate-600">Rel. clim. diária: {row.avgRelMlt >= 0 ? "+" : ""}{row.avgRelMlt} cm</p>
          </div>
        );
      })}
    </div>
  );
}

function getLastValidClimateValue(climate, key) {
  if (!Array.isArray(climate)) return null;

  for (let i = climate.length - 1; i >= 0; i -= 1) {
    const row = climate[i];
    if (isNum(row?.[key])) {
      return {
        value: row[key],
        label: row.label || "sem data",
        source: row.source || "fonte não informada",
      };
    }
  }

  return null;
}

function getDiagnostics(mainStations, upperStations, climate) {
  const all = [...activeStations(mainStations), ...activeStations(upperStations)];
  const latest = Array.isArray(climate) && climate.length ? climate[climate.length - 1] : {};

  const latestNino = getLastValidClimateValue(climate, "nino34");
  const latestDipole = getLastValidClimateValue(climate, "atlDipole");

  const nino = latestNino ? latestNino.value : 0;
  const dipole = latestDipole ? latestDipole.value : 0;

  const ninoIsCurrent = isNum(latest?.nino34);
  const dipoleIsCurrent = isNum(latest?.atlDipole);

  const anomaly = all.reduce((best, station) => {
    const relClim = station.current - num(station.mlt, station.current);
    return !best || relClim > best.relClim ? { station, relClim } : best;
  }, null);

  const drop = activeStations(upperStations).reduce((best, station) => {
    const delta7 = num(station.delta7, 0);
    return !best || delta7 < best.delta7 ? { station, delta7 } : best;
  }, null);

  const climateText =
    nino >= 0.5 ? `Niño 3.4 positivo (${nino.toFixed(1)} °C)` :
    nino <= -0.5 ? `Niño 3.4 negativo (${nino.toFixed(1)} °C)` :
    `Niño 3.4 neutro (${nino.toFixed(1)} °C)`;

  const atlText =
    dipole > 0 ? `Norte mais quente que Sul (+${dipole.toFixed(1)})` :
    dipole < 0 ? `Sul mais quente que Norte (${dipole.toFixed(1)})` :
    "gradiente Norte–Sul neutro";

  return [
    {
      title: "Maior anomalia positiva",
      value: anomaly ? anomaly.station.name : "—",
      detail: anomaly
        ? `${anomaly.relClim >= 0 ? "+" : ""}${anomaly.relClim} cm em relação à climatologia diária`
        : "sem dados",
      icon: Waves,
      tone: "neutral",
    },
    {
      title: "Pior tendência a montante",
      value: drop ? drop.station.basin : "—",
      detail: drop ? `${drop.station.name}: ${drop.delta7} cm em 7 dias` : "sem dados",
      icon: drop && drop.delta7 < 0 ? TrendingDown : TrendingUp,
      tone: drop && drop.delta7 < 0 ? "warning" : "neutral",
    },
    {
      title: "Sinal El Niño",
      value: latestNino ? climateText : "Niño 3.4 indisponível",
      detail: latestNino
        ? ninoIsCurrent
          ? `valor semanal mais recente carregado para ${latestNino.label}`
          : `dado semanal mais recente ainda não disponível; exibindo último valor válido (${latestNino.label})`
        : "sem valor válido de Niño 3.4 no dashboard.json",
      icon: Activity,
      tone: nino >= 0.5 ? "warning" : "neutral",
    },
    {
      title: "Dipolo Atlântico Tropical",
      value: latestDipole ? `${dipole >= 0 ? "+" : ""}${dipole.toFixed(1)}` : "indisponível",
      detail: latestDipole
        ? dipoleIsCurrent
          ? atlText
          : `${atlText}; dado mais recente válido: ${latestDipole.label}`
        : "sem valor válido de dipolo no dashboard.json",
      icon: Waves,
      tone: dipole > 0 ? "warning" : "neutral",
    },
  ];
}

function toneClasses(tone) {
  if (tone === "warning") return "border-amber-200 bg-amber-50";
  if (tone === "muted") return "border-slate-200 bg-slate-100";
  return "border-slate-200 bg-white";
}

function DiagnosticStrip({ diagnostics }) {
  return (
    <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
      {diagnostics.map((item) => {
        const Icon = item.icon;
        return (
          <div key={item.title} className={`rounded-2xl border p-4 shadow-sm ${toneClasses(item.tone)}`}>
            <div className="mb-3 flex items-center gap-2 text-sm text-slate-500">
              <Icon className="h-4 w-4" />
              <span>{item.title}</span>
            </div>
            <p className="text-xl font-semibold leading-tight">{item.value}</p>
            <p className="mt-2 text-sm text-slate-600">{item.detail}</p>
          </div>
        );
      })}
    </section>
  );
}

function ClimateCharts({ data }) {
  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
      <Panel title="Histórico semanal — El Niño" subtitle="Índice Niño 3.4 semanal. Na versão operacional, vem de /data/dashboard.json." icon={Activity}>
        <div className="h-[320px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
              <CartesianGrid vertical={false} strokeDasharray="4 8" strokeOpacity={0.35} />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 12 }} label={{ value: "anomalia (°C)", angle: -90, position: "insideLeft" }} />
              <Tooltip />
              <Legend />
              <ReferenceLine y={0.5} strokeDasharray="4 4" />
              <ReferenceLine y={-0.5} strokeDasharray="4 4" />
              <ReferenceLine y={0} strokeDasharray="2 2" />
              <Line type="monotone" dataKey="nino34" name="Niño 3.4" stroke="#dc2626" strokeWidth={2.5} dot={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      <Panel title="Histórico semanal — Atlântico Tropical" subtitle="Atlântico Norte, Atlântico Sul e dipolo Norte–Sul em base semanal." icon={Waves}>
        <div className="h-[320px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
              <CartesianGrid vertical={false} strokeDasharray="4 8" strokeOpacity={0.35} />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 12 }} label={{ value: "anomalia / índice", angle: -90, position: "insideLeft" }} />
              <Tooltip />
              <Legend />
              <ReferenceLine y={0} strokeDasharray="2 2" />
              <Line type="monotone" dataKey="atlNorth" name="Atlântico Norte" stroke="#2563eb" strokeWidth={2.2} dot={false} connectNulls />
              <Line type="monotone" dataKey="atlSouth" name="Atlântico Sul" stroke="#16a34a" strokeWidth={2.2} dot={false} connectNulls />
              <Line type="monotone" dataKey="atlDipole" name="Dipolo N-S" stroke="#0f766e" strokeWidth={2.8} dot={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Panel>
    </div>
  );
}

function RainfallChart({ data }) {
  return (
    <Panel title="Chuva por bacia" subtitle="Acumulados observados e previstos por bacia." icon={CloudRain}>
      <div className="h-[360px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
            <CartesianGrid vertical={false} strokeDasharray="4 8" strokeOpacity={0.35} />
            <XAxis dataKey="basin" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} label={{ value: "mm", angle: -90, position: "insideLeft" }} />
            <Tooltip />
            <Legend />
            <Bar dataKey="obs7" name="Observado 7 dias" fill="#2563eb" />
            <Bar dataKey="fcst7" name="Previsto 7 dias" fill="#16a34a" />
            <Bar dataKey="obs30" name="Observado 30 dias" fill="#94a3b8" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}

export default function HydroDashboard() {
  const { data: dashboardData, status, error } = useDashboardData();
  const mainSource = dashboardData.mainStations;
  const upperSource = dashboardData.upperBasinStations;
  const rainfallSource = dashboardData.rainfall;
  const climateSource = dashboardData.climateHistory || buildClimateHistory();

  const mainStations = useMemo(() => activeStations(mainSource), [mainSource]);
  const upperStations = useMemo(() => activeStations(upperSource), [upperSource]);
  const main30 = useMemo(() => makeMultiStationSeries(mainSource, "30d", "deltaInicio"), [mainSource]);
  const main30Domain = useMemo(() => getZoomedYDomain(main30, mainSource, 4), [main30, mainSource]);
  const main12 = useMemo(() => makeMultiStationSeries(mainSource, "12m", "cota"), [mainSource]);
  const upper30 = useMemo(() => makeMultiStationSeries(upperSource, "30d", "deltaInicio"), [upperSource]);
  const upper30Domain = useMemo(() => getZoomedYDomain(upper30, upperSource, 4), [upper30, upperSource]);
  const upper12 = useMemo(() => makeMultiStationSeries(upperSource, "12m", "cota"), [upperSource]);
  const main12Anomaly = useMemo(() => makeMultiStationSeries(mainSource, "12m", "relativoMlt"), [mainSource]);
  const main12AnomalyDomain = useMemo(() => getZoomedYDomain(main12Anomaly, mainSource, 20), [main12Anomaly, mainSource]);
  const upper12Anomaly = useMemo(() => makeMultiStationSeries(upperSource, "12m", "relativoMlt"), [upperSource]);
  const upper12AnomalyDomain = useMemo(() => getZoomedYDomain(upper12Anomaly, upperSource, 20), [upper12Anomaly, upperSource]);
  const basinRows = useMemo(() => basinSummary(upperSource), [upperSource]);
  const climate = useMemo(() => climateSource, [climateSource]);
  const diagnostics = useMemo(() => getDiagnostics(mainSource, upperSource, climate), [mainSource, upperSource, climate]);
  const banner = statusBanner(status, error);

  return (
    <div className="min-h-screen bg-slate-50 p-4 text-slate-900 md:p-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2 text-sm text-slate-500">
              <Ship className="h-4 w-4" /> Monitoramento hidroclimático para navegação
            </div>
            <h1 className="text-3xl font-bold tracking-tight md:text-4xl">Painel Amazônia — comparação operacional</h1>
            <p className="mt-2 max-w-4xl text-slate-600">
              Painel comparativo com pontos críticos no eixo Amazonas — Manaus, Itacoatiara, Óbidos e Santarém — e uma estação sentinela a montante para cada bacia: Madeira, Tapajós, Purus, Negro, Solimões e Xingu.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium">
              <CalendarDays className="h-4 w-4" /> {formatUpdatedAt(dashboardData.updatedAt)}
            </button>
            <button type="button" onClick={() => window.location.reload()} className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white">
              <RefreshCcw className="h-4 w-4" /> Atualizar dados
            </button>
          </div>
        </header>

        <div className={`rounded-2xl border px-4 py-3 text-sm ${banner.className}`}>{banner.text}</div>

        <DiagnosticStrip diagnostics={diagnostics} />

        <Panel title="Pontos críticos — últimos 30 dias" subtitle="Todas as estações com dado direto, simultaneamente. Eixo em variação acumulada desde o primeiro dia da janela." icon={Activity}>
          <MultiStationLineChart data={main30} stations={mainSource} mode="main30" yLabel="variação acumulada (cm)" yDomain={main30Domain} zeroLine />
        </Panel>

        <Panel title="Pontos críticos — últimos 12 meses corridos" subtitle="Cota absoluta diária nas estações principais com dado direto." icon={Waves}>
          <MultiStationLineChart data={main12} stations={mainSource} mode="main12" yLabel="cota absoluta (cm)" height={460} monthlyTicks />
        </Panel>

        <Panel title="Pontos críticos — anomalia em relação à climatologia diária" subtitle="Diferença entre a cota observada e a média climatológica diária dos últimos 10 anos. Use este gráfico para auditar a climatologia nos pontos principais." icon={AlertTriangle}>
          <MultiStationLineChart data={main12Anomaly} stations={mainSource} mode="main12Anomaly" yLabel="cm em relação à climatologia diária" height={460} monthlyTicks yDomain={main12AnomalyDomain} zeroLine />
        </Panel>


        <Panel title="Alta bacia — resumo por sistema" subtitle="Leitura rápida de antecedência hidrológica com uma estação sentinela por bacia." icon={AlertTriangle}>
          <BasinSummaryCards rows={basinRows} />
        </Panel>

        <Panel title="Alta bacia — últimos 30 dias" subtitle="Uma estação sentinela por bacia. Eixo em variação acumulada desde o primeiro dia da janela." icon={TrendingUp}>
          <MultiStationLineChart data={upper30} stations={upperSource} mode="upper30" yLabel="variação acumulada (cm)" height={460} yDomain={upper30Domain} zeroLine />
        </Panel>

        <Panel title="Alta bacia — últimos 12 meses corridos" subtitle="Cota absoluta diária das estações sentinela a montante." icon={TrendingDown}>
          <MultiStationLineChart data={upper12} stations={upperSource} mode="upper12" yLabel="cota absoluta (cm)" height={460} monthlyTicks />
        </Panel>


        <Panel title="Alta bacia — anomalia em relação à climatologia diária" subtitle="Diferença entre a cota observada e a média climatológica diária dos últimos 10 anos. Use este gráfico para identificar possíveis erros de escala, lacunas ou anomalias suspeitas." icon={AlertTriangle}>
          <MultiStationLineChart data={upper12Anomaly} stations={upperSource} mode="upper12Anomaly" yLabel="cm em relação à climatologia diária" height={460} monthlyTicks yDomain={upper12AnomalyDomain} zeroLine />
        </Panel>

        <ClimateCharts data={climate} />
        <RainfallChart data={rainfallSource} />

        <Panel title="Tabela sintética — pontos críticos" subtitle="Escopo atual: Manaus, Itacoatiara, Óbidos e Santarém." icon={Database}>
          <Table rows={mainStations} />
        </Panel>

        <Panel title="Tabela sintética — estações a montante" subtitle="Dados das estações sentinela das bacias Madeira, Tapajós, Purus, Negro, Solimões e Xingu." icon={Database}>
          <Table rows={upperStations} compact />
        </Panel>
      </div>
    </div>
  );
}
