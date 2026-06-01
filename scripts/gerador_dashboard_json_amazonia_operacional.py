# TESTE_ARQUIVO_CERTO_WEEKLY
"""
Gerador operacional de public/data/dashboard.json para o Painel Hidroclimático Amazônia.

Fontes:
- ANA Telemetria para cotas: DadosHidrometeorologicos.
- NOAA/CPC semanal para Niño 3.4.
- NOAA/OOPC semanal NetCDF para TNA, TSA e TASI.

Instalação necessária para a parte OOPC:
python -m pip install xarray netCDF4

Uso:
python scripts/gerador_dashboard_json_amazonia_operacional.py --output public/data/dashboard.json
python scripts/gerador_dashboard_json_amazonia_operacional.py --test
python scripts/gerador_dashboard_json_amazonia_operacional.py --strict
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

TZ_BRT = timezone(timedelta(hours=-3))
DEFAULT_OUTPUT_PATH = Path("public/data/dashboard.json")
RAW_DATA_DIR = Path("data/raw")
REQUEST_TIMEOUT_SECONDS = 45
CLIMATOLOGY_YEARS = 10
CLIMATOLOGY_WINDOW_DAYS = 30

ANA_TELEMETRIA_URL = "https://telemetriaws1.ana.gov.br/ServiceANA.asmx/DadosHidrometeorologicos"
NOAA_CPC_NINO34_WEEKLY_URL = "https://www.cpc.ncep.noaa.gov/data/indices/wksst9120.for"
NOAA_OOPC_TNA_NC_URL = "https://stateoftheocean.osmc.noaa.gov/sur/data/tna.nc"
NOAA_OOPC_TSA_NC_URL = "https://stateoftheocean.osmc.noaa.gov/sur/data/tsa.nc"
NOAA_OOPC_TASI_NC_URL = "https://stateoftheocean.osmc.noaa.gov/sur/data/tasi.nc"

STATION_CODES = {
    "manaus": "14990000",
    "itacoatiara": "16030000",
    "obidos": "17050001",
    "santarem": "17900000",
    "tabatinga": "10100000",
    "porto_velho": "15400000",
    "itaituba": "17730000",
    "labrea": "13870000",
    "barcelos": "14480002",
    "altamira": "18850000",
}

DATE_KEYS = ["date", "data", "Data", "dataHora", "DataHora", "timestamp", "Timestamp"]
LEVEL_KEYS = ["level", "cota", "Cota", "nivel", "Nivel", "valor", "Valor", "value", "Value"]
MONTH_LABELS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


@dataclass
class LevelPoint:
    date: str
    level: int
    mlt: int
    p05: int
    p95: int
    source: str = "demo"


@dataclass
class Station:
    id: str
    name: str
    river: str
    basin: str
    current: int
    delta7: int
    delta30: int
    risk: str
    mlt: int
    p95: int
    p05: int
    station_code: str
    levels30d: list[LevelPoint] = field(default_factory=list)
    levels12m: list[LevelPoint] = field(default_factory=list)
    source: str = "demo"
    warning: str | None = None


MAIN_STATIONS = [
    Station("manaus", "Manaus", "Rio Negro / Amazonas", "Pontos críticos", 2746, 28, 106, "atenção", 2680, 2920, 2140, STATION_CODES["manaus"]),
    Station("itacoatiara", "Itacoatiara", "Rio Amazonas", "Pontos críticos", 1339, 18, 91, "baixo", 1290, 1510, 850, STATION_CODES["itacoatiara"]),
    Station("obidos", "Óbidos", "Rio Amazonas", "Pontos críticos", 740, 14, 88, "baixo", 705, 890, 390, STATION_CODES["obidos"]),
    Station("santarem", "Santarém", "Rio Amazonas / Tapajós", "Pontos críticos", 708, 11, 79, "baixo", 675, 820, 360, STATION_CODES["santarem"]),
]

UPPER_BASIN_STATIONS = [
    Station("tabatinga", "Tabatinga", "Solimões", "Solimões", 1169, -8, 42, "atenção", 1210, 1450, 760, STATION_CODES["tabatinga"]),
    Station("porto_velho", "Porto Velho", "Madeira", "Madeira", 1295, -22, -74, "atenção", 1360, 1620, 650, STATION_CODES["porto_velho"]),
    Station("itaituba", "Itaituba", "Tapajós", "Tapajós", 712, 6, 37, "baixo", 690, 880, 390, STATION_CODES["itaituba"]),
    Station("labrea", "Lábrea", "Purus", "Purus", 1184, -11, 21, "atenção", 1215, 1480, 720, STATION_CODES["labrea"]),
    Station("barcelos", "Barcelos", "Rio Negro", "Negro", 500, 0, 0, "baixo", 500, 900, 100, STATION_CODES["barcelos"]),
    Station("altamira", "Altamira", "Rio Xingu", "Xingu", 520, 0, 0, "baixo", 520, 950, 180, STATION_CODES["altamira"]),
]

RAINFALL_FALLBACK = [
    {"basin": "Madeira", "obs7": 42, "fcst7": 35, "obs30": 188, "source": "demo"},
    {"basin": "Tapajós", "obs7": 36, "fcst7": 31, "obs30": 164, "source": "demo"},
    {"basin": "Purus", "obs7": 51, "fcst7": 44, "obs30": 208, "source": "demo"},
    {"basin": "Negro", "obs7": 92, "fcst7": 80, "obs30": 316, "source": "demo"},
    {"basin": "Solimões", "obs7": 78, "fcst7": 62, "obs30": 284, "source": "demo"},
    {"basin": "Xingu", "obs7": 44, "fcst7": 38, "obs30": 180, "source": "demo"},
    {"basin": "Baixo Amazonas", "obs7": 55, "fcst7": 48, "obs30": 220, "source": "demo"},
]


def today_brt() -> date:
    return datetime.now(TZ_BRT).date()


def parse_end_date(value: str | None) -> date:
    if not value:
        return today_brt()
    return datetime.strptime(value, "%Y-%m-%d").date()


def br_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def month_add(base: date, months: int) -> date:
    month_index = base.month - 1 + months
    return date(base.year + month_index // 12, month_index % 12 + 1, 1)


def http_get_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "amazonia-hydro-dashboard/0.5"})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return response.read().decode("utf-8-sig", errors="replace")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} em {url}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"erro de conexão em {url}: {exc.reason}") from exc


# -------------------------
# NÍVEIS ANA / CSV
# -------------------------

def build_station_series(station: Station, end_date: date, warnings: list[str], strict: bool) -> Station:
    # Busca uma janela longa para calcular climatologia diária/sazonal.
    # A série operacional de 12 meses continua sendo extraída dos últimos 365 dias.
    start_date = end_date - timedelta(days=365 * CLIMATOLOGY_YEARS + CLIMATOLOGY_WINDOW_DAYS)
    attempts = [
        ("csv", lambda: fetch_level_series_from_csv(station, start_date, end_date)),
        ("ana-telemetria", lambda: fetch_level_series_from_ana_telemetria(station, start_date, end_date)),
    ]

    for source_name, fetcher in attempts:
        try:
            series = fetcher()
            if len(series) >= 365:
                return station_from_real_series(station, series, f"real-{source_name}", end_date, warnings)
            if len(series) >= 30:
                warnings.append(
                    f"{station.id}: série real com {len(series)} dias; climatologia de 10 anos insuficiente, usando fallback climatológico parcial"
                )
                return station_from_real_series(station, series, f"real-{source_name}-partial-climatology", end_date, warnings)
        except Exception as exc:
            msg = f"{station.id}: falha em {source_name}: {exc}"
            if strict:
                raise RuntimeError(msg) from exc
            warnings.append(msg)

    msg = f"{station.id}: sem série real suficiente; usando fallback sintético"
    if strict:
        raise RuntimeError(msg)
    warnings.append(msg)
    return station_from_fallback(station, end_date, msg)


def station_from_real_series(
    station: Station,
    series: list[LevelPoint],
    source: str,
    end_date: date,
    warnings: list[str] | None = None,
) -> Station:
    recent_start = end_date - timedelta(days=364)
    climatology = build_daily_climatology(series)
    if warnings is not None and len(series) < 365 * 3:
        warnings.append(
            f"{station.id}: climatologia calculada com apenas {len(series)} pontos; ideal é aproximadamente 10 anos diários"
        )

    complete = fill_missing_daily_points(series, station, recent_start, end_date, source, climatology)
    levels12m = complete[-365:]
    levels30d = levels12m[-30:]

    current = levels12m[-1].level
    current_mlt, current_p05, current_p95 = climatology_for_date(end_date, climatology, station)
    delta7 = current - levels12m[-8].level if len(levels12m) >= 8 else 0
    delta30 = current - levels12m[-30].level if len(levels12m) >= 30 else 0

    return replace(
        station,
        current=current,
        delta7=delta7,
        delta30=delta30,
        mlt=current_mlt,
        p05=current_p05,
        p95=current_p95,
        risk=infer_risk(current, current_mlt, current_p05, current_p95),
        levels30d=levels30d,
        levels12m=levels12m,
        source=source,
        warning=None,
    )


def station_from_fallback(station: Station, end_date: date, warning: str) -> Station:
    return replace(
        station,
        levels30d=build_synthetic_series(station, end_date, 30),
        levels12m=build_synthetic_series(station, end_date, 365),
        source="demo-fallback",
        warning=warning,
    )


def parse_level_point_date(point: LevelPoint) -> date | None:
    try:
        return datetime.strptime(point.date[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def mmdd_key(day: date) -> str:
    return day.strftime("%m-%d")


def climatology_day_index(day: date) -> int | None:
    # Ano não bissexto de referência para evitar deslocamentos após fevereiro.
    if day.month == 2 and day.day == 29:
        return None
    try:
        return date(2001, day.month, day.day).timetuple().tm_yday
    except ValueError:
        return None


def circular_day_distance(a: int, b: int, period: int = 365) -> int:
    diff = abs(a - b)
    return min(diff, period - diff)


def percentile(values: list[int], pct: float) -> int:
    if not values:
        raise ValueError("percentile sem valores")
    ordered = sorted(values)
    if len(ordered) == 1:
        return int(round(ordered[0]))
    pos = (len(ordered) - 1) * pct
    lower = math.floor(pos)
    upper = math.ceil(pos)
    if lower == upper:
        return int(round(ordered[int(pos)]))
    weight = pos - lower
    return int(round(ordered[lower] * (1 - weight) + ordered[upper] * weight))


def build_daily_climatology(points: list[LevelPoint]) -> dict[str, dict[str, int]]:
    dated_values: list[tuple[int, int]] = []
    for point in points:
        day = parse_level_point_date(point)
        if day is None:
            continue
        day_index = climatology_day_index(day)
        if day_index is None:
            continue
        dated_values.append((day_index, point.level))

    climatology: dict[str, dict[str, int]] = {}
    for month in range(1, 13):
        for day_num in range(1, 32):
            try:
                target = date(2001, month, day_num)
            except ValueError:
                continue
            target_index = target.timetuple().tm_yday
            values = [
                level for sample_index, level in dated_values
                if circular_day_distance(sample_index, target_index) <= CLIMATOLOGY_WINDOW_DAYS
            ]
            if not values:
                continue
            climatology[target.strftime("%m-%d")] = {
                "mean": int(round(sum(values) / len(values))),
                "p05": percentile(values, 0.05),
                "p95": percentile(values, 0.95),
                "n": len(values),
            }
    return climatology


def climatology_for_date(day: date, climatology: dict[str, dict[str, int]], station: Station) -> tuple[int, int, int]:
    key = "02-28" if day.month == 2 and day.day == 29 else mmdd_key(day)
    stats = climatology.get(key)
    if not stats:
        return station.mlt, station.p05, station.p95
    return stats["mean"], stats["p05"], stats["p95"]


def apply_daily_climatology(point: LevelPoint, station: Station, climatology: dict[str, dict[str, int]]) -> LevelPoint:
    day = parse_level_point_date(point)
    if day is None:
        return point
    mlt, p05, p95 = climatology_for_date(day, climatology, station)
    return replace(point, mlt=mlt, p05=p05, p95=p95)


def infer_risk(current: int, mlt: int, p05: int, p95: int) -> str:
    if current <= p05 or current >= p95:
        return "atenção"
    amp = max(1, p95 - mlt, mlt - p05)
    return "atenção" if abs(current - mlt) > 0.75 * amp else "baixo"


def fetch_level_series_from_csv(station: Station, start_date: date, end_date: date) -> list[LevelPoint]:
    path = RAW_DATA_DIR / f"{station.id}.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    return records_to_level_points(rows, station, start_date, end_date, "real-csv")


def fetch_level_series_from_ana_telemetria(station: Station, start_date: date, end_date: date) -> list[LevelPoint]:
    params = urllib.parse.urlencode({"CodEstacao": station.station_code, "DataInicio": br_date(start_date), "DataFim": br_date(end_date)})
    xml_text = http_get_text(f"{ANA_TELEMETRIA_URL}?{params}")
    return records_to_level_points(parse_ana_xml_records(xml_text), station, start_date, end_date, "real-ana-telemetria")


def parse_ana_xml_records(xml_text: str) -> list[dict[str, Any]]:
    if not xml_text.strip():
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise RuntimeError("resposta ANA não é XML válido") from exc

    records = []
    for element in root.iter():
        children = list(element)
        if not children:
            continue
        row = {child.tag.split("}")[-1]: child.text for child in children}
        lower = {key.lower() for key in row}
        if lower & {"datahora", "data", "nivel", "cota", "valor"}:
            records.append(row)
    return records


def first_present(record: dict[str, Any], keys: list[str]) -> Any:
    lower = {str(k).lower(): v for k, v in record.items()}
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
        if key.lower() in lower and lower[key.lower()] not in (None, ""):
            return lower[key.lower()]
    return None


def parse_record_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"]:
        try:
            return datetime.strptime(text[:19], fmt).date()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def parse_level(value: Any) -> int | None:
    if value is None:
        return None

    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        parsed = float(value)
    else:
        text = str(value).strip()
        if not text:
            return None

        # Formatos aceitos:
        # 2724.30  -> 2724.30
        # 2724,30  -> 2724.30
        # 2.724,30 -> 2724.30
        # 2,724.30 -> 2724.30
        if "," in text and "." in text:
            if text.rfind(",") > text.rfind("."):
                text = text.replace(".", "").replace(",", ".")
            else:
                text = text.replace(",", "")
        elif "," in text:
            text = text.replace(",", ".")

        try:
            parsed = float(text)
        except ValueError:
            return None

    if not math.isfinite(parsed):
        return None

    if parsed > 100000:
        parsed = parsed / 100

    return int(round(parsed))


def records_to_level_points(records: Iterable[dict[str, Any]], station: Station, start_date: date, end_date: date, source: str) -> list[LevelPoint]:
    points = []
    for record in records:
        day = parse_record_date(first_present(record, DATE_KEYS))
        level = parse_level(first_present(record, LEVEL_KEYS))
        if day is None or level is None or not (start_date <= day <= end_date):
            continue
        points.append(LevelPoint(day.isoformat(), level, station.mlt, station.p05, station.p95, source))
    return deduplicate_daily_points(points)


def deduplicate_daily_points(points: list[LevelPoint]) -> list[LevelPoint]:
    by_date: dict[str, list[int]] = {}
    sample: dict[str, LevelPoint] = {}
    for point in points:
        by_date.setdefault(point.date, []).append(point.level)
        sample[point.date] = point
    return [replace(sample[day], level=int(round(sum(values) / len(values)))) for day, values in sorted(by_date.items())]


def fill_missing_daily_points(
    points: list[LevelPoint],
    station: Station,
    start_date: date,
    end_date: date,
    source: str,
    climatology: dict[str, dict[str, int]] | None = None,
) -> list[LevelPoint]:
    climatology = climatology or {}
    by_date = {point.date: apply_daily_climatology(point, station, climatology) for point in points}
    filled = []
    previous_level = station.current
    day = start_date
    while day <= end_date:
        key = day.isoformat()
        if key in by_date:
            point = by_date[key]
            previous_level = point.level
            filled.append(point)
        else:
            mlt, p05, p95 = climatology_for_date(day, climatology, station)
            filled.append(LevelPoint(key, previous_level, mlt, p05, p95, f"{source}-filled"))
        day += timedelta(days=1)
    return filled


def build_synthetic_series(station: Station, end_date: date, days: int) -> list[LevelPoint]:
    start_date = end_date - timedelta(days=days - 1)
    out = []
    for i in range(days):
        current_date = start_date + timedelta(days=i)
        if days == 30:
            trend = station.current - station.delta30 + (station.delta30 / max(1, days - 1)) * i
            level = round(trend + math.sin(i / 2.8) * 10 + math.cos(i / 4.1) * 5)
        else:
            phase = (i / days) * math.pi * 2
            level = round(station.mlt + math.sin(phase - 1.25) * 180 + math.sin(phase * 2.05) * 34 + (i / max(1, days - 1)) * station.delta30 * 1.8)
        out.append(LevelPoint(current_date.isoformat(), int(level), station.mlt, station.p05, station.p95, "demo"))
    return out


# -------------------------
# CLIMA NOAA/CPC + NOAA/OOPC SEMANAL
# -------------------------

def build_climate_history(end_date: date, warnings: list[str], strict: bool) -> list[dict[str, Any]]:
    try:
        nino = fetch_noaa_cpc_weekly_nino34(NOAA_CPC_NINO34_WEEKLY_URL)
        tna = fetch_oopc_netcdf_series(NOAA_OOPC_TNA_NC_URL)
        tsa = fetch_oopc_netcdf_series(NOAA_OOPC_TSA_NC_URL)
        tasi = fetch_oopc_netcdf_series(NOAA_OOPC_TASI_NC_URL)
        rows = merge_climate_series_weekly(nino, tna, tsa, tasi, end_date, weeks=104)
        if rows:
            return rows
        raise RuntimeError("NOAA retornou séries climáticas semanais vazias")
    except Exception as exc:
        msg = f"climateHistory: falha NOAA/CPC/OOPC: {exc}; usando fallback sintético semanal"
        if strict:
            raise RuntimeError(msg) from exc
        warnings.append(msg)
        return build_synthetic_climate_history(end_date)


def fetch_noaa_cpc_weekly_nino34(url: str) -> list[dict[str, Any]]:
    """Lê a série semanal de SST/SSTA Niño 3.4 da NOAA/CPC.

    Fonte esperada: wksst9120.for. O arquivo traz linhas semanais com pares
    SST/anomalia para Niño 1+2, Niño 3, Niño 3.4 e Niño 4. O valor usado é a
    anomalia de Niño 3.4.
    """
    text = http_get_text(url)
    rows: list[dict[str, Any]] = []
    month_map = {
        "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
        "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
    }

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split()
        if not parts:
            continue

        raw_date = parts[0].upper()
        parsed_date = None
        if len(raw_date) >= 9 and raw_date[:2].isdigit() and raw_date[2:5] in month_map and raw_date[5:9].isdigit():
            parsed_date = date(int(raw_date[5:9]), month_map[raw_date[2:5]], int(raw_date[:2]))
        elif len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit() and parts[2].isdigit():
            # fallback para tabelas YYYY MM DD ...
            try:
                parsed_date = date(int(parts[0]), int(parts[1]), int(parts[2]))
                parts = parts[2:]
            except ValueError:
                parsed_date = None

        if parsed_date is None:
            continue

        numbers: list[float] = []
        for token in parts[1:]:
            try:
                numbers.append(float(token))
            except ValueError:
                pass

        # Formato CPC típico: Nino1+2 SST/SSTA, Nino3 SST/SSTA,
        # Nino3.4 SST/SSTA, Nino4 SST/SSTA. Logo, SSTA Nino3.4 = índice 5.
        if len(numbers) >= 6:
            nino34_anomaly = numbers[5]
        elif len(numbers) >= 4:
            # fallback conservador para formato somente com anomalias regionais
            nino34_anomaly = numbers[2]
        else:
            continue

        if math.isfinite(nino34_anomaly) and nino34_anomaly > -90:
            rows.append({"date": parsed_date, "value": round(float(nino34_anomaly), 2)})

    rows.sort(key=lambda row: row["date"])
    return rows


def fetch_oopc_netcdf_series(url: str) -> list[dict[str, Any]]:
    import xarray as xr

    with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "amazonia-hydro-dashboard/0.6"})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            tmp_path.write_bytes(response.read())
        dataset = xr.open_dataset(tmp_path)
        try:
            time_name = find_coord_name(dataset, ["time", "TIME", "date", "DATE"])
            value_name = find_data_var_name(dataset)
            rows = []
            for raw_time, raw_value in zip(dataset[time_name].values, dataset[value_name].values):
                parsed_date = parse_netcdf_time(raw_time)
                parsed_value = parse_netcdf_value(raw_value)
                if parsed_date is not None and parsed_value is not None:
                    rows.append({"date": parsed_date, "value": parsed_value})
            rows.sort(key=lambda row: row["date"])
            return rows
        finally:
            dataset.close()
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def find_coord_name(dataset: Any, candidates: list[str]) -> str:
    for name in candidates:
        if name in dataset.coords or name in dataset.variables:
            return name
    raise RuntimeError(f"não encontrei coordenada temporal no NetCDF. Variáveis: {list(dataset.variables)}")


def find_data_var_name(dataset: Any) -> str:
    for name in ["anom", "anomaly", "index", "value", "sst", "TNA", "TSA", "TASI", "tna", "tsa", "tasi"]:
        if name in dataset.data_vars:
            return name
    for name, variable in dataset.data_vars.items():
        if getattr(variable, "ndim", 0) == 1:
            return name
    raise RuntimeError(f"não encontrei variável de índice no NetCDF. Variáveis: {list(dataset.data_vars)}")


def parse_netcdf_time(value: Any) -> date | None:
    try:
        if hasattr(value, "astype"):
            return datetime.strptime(str(value.astype("datetime64[D]"))[:10], "%Y-%m-%d").date()
        return datetime.fromisoformat(str(value)[:10]).date()
    except Exception:
        return None


def parse_netcdf_value(value: Any) -> float | None:
    try:
        parsed = float(value)
    except Exception:
        return None
    return parsed if math.isfinite(parsed) and parsed > -90 else None


def latest_weekly_value_on_or_before(series: list[dict[str, Any]], target_date: date, max_lag_days: int = 14) -> float | None:
    candidates = [
        row for row in series
        if isinstance(row.get("date"), date)
        and row["date"] <= target_date
        and (target_date - row["date"]).days <= max_lag_days
        and row.get("value") is not None
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda row: row["date"])
    return round(float(candidates[-1]["value"]), 2)


def merge_climate_series_weekly(
    nino_weekly: list[dict[str, Any]],
    tna_weekly: list[dict[str, Any]],
    tsa_weekly: list[dict[str, Any]],
    tasi_weekly: list[dict[str, Any]],
    end_date: date,
    weeks: int,
) -> list[dict[str, Any]]:
    start_date = end_date - timedelta(days=weeks * 7)
    usable_nino = [row for row in nino_weekly if isinstance(row.get("date"), date) and start_date <= row["date"] <= end_date]
    if not usable_nino:
        usable_nino = nino_weekly[-weeks:]

    rows = []
    for row in usable_nino[-weeks:]:
        current_date = row["date"]
        nino34 = row.get("value")
        atl_north = latest_weekly_value_on_or_before(tna_weekly, current_date)
        atl_south = latest_weekly_value_on_or_before(tsa_weekly, current_date)
        tasi = latest_weekly_value_on_or_before(tasi_weekly, current_date)

        if atl_north is not None and atl_south is not None:
            dipole = round(atl_north - atl_south, 2)
            dipole_source = "TNA-TSA"
        else:
            dipole = tasi
            dipole_source = "TASI"

        rows.append({
            "label": current_date.strftime("%d/%m/%y"),
            "date": current_date.isoformat(),
            "nino34": round(float(nino34), 2) if nino34 is not None else None,
            "atlNorth": atl_north,
            "atlSouth": atl_south,
            "atlDipole": dipole,
            "atlDipoleSource": dipole_source if dipole is not None else None,
            "source": "NOAA/CPC weekly + NOAA/OOPC weekly",
        })
    return rows


def build_synthetic_climate_history(end_date: date) -> list[dict[str, Any]]:
    start_date = end_date - timedelta(days=103 * 7)
    rows = []
    for index in range(104):
        current = start_date + timedelta(days=index * 7)
        nino34 = round(math.sin(index / 7.5) * 0.75 + math.cos(index / 13) * 0.22 + 0.15, 2)
        atl_north = round(math.cos(index / 8.0) * 0.34 + 0.35, 2)
        atl_south = round(math.sin(index / 9.5) * 0.28 + 0.30, 2)
        rows.append({
            "label": current.strftime("%d/%m/%y"),
            "date": current.isoformat(),
            "nino34": nino34,
            "atlNorth": atl_north,
            "atlSouth": atl_south,
            "atlDipole": round(atl_north - atl_south, 2),
            "atlDipoleSource": "demo",
            "source": "demo",
        })
    return rows


# -------------------------
# DASHBOARD / CLI
# -------------------------

def station_to_json(station: Station) -> dict[str, Any]:
    data = asdict(station)
    data["levels30d"] = [asdict(point) for point in station.levels30d]
    data["levels12m"] = [asdict(point) for point in station.levels12m]
    return data


def infer_source_mode(stations: list[Station], climate: list[dict[str, Any]]) -> str:
    station_sources = {station.source for station in stations}
    has_real_station = any(source.startswith("real") for source in station_sources)
    has_real_climate = any(str(row.get("source", "")).startswith("NOAA/") for row in climate)
    if all(source.startswith("real") for source in station_sources) and has_real_climate:
        return "operational"
    if has_real_station or has_real_climate:
        return "mixed-operational-fallback"
    return "demo-fallback"


def build_dashboard(end_date: date | None = None, strict: bool = False) -> dict[str, Any]:
    end_date = end_date or today_brt()
    warnings: list[str] = []
    main = [build_station_series(station, end_date, warnings, strict) for station in MAIN_STATIONS]
    upper = [build_station_series(station, end_date, warnings, strict) for station in UPPER_BASIN_STATIONS]
    climate = build_climate_history(end_date, warnings, strict)
    return {
        "updatedAt": datetime.now(TZ_BRT).isoformat(timespec="seconds"),
        "date": end_date.isoformat(),
        "sourceMode": infer_source_mode(main + upper, climate),
        "metadata": {
            "warnings": warnings,
            "stationCodesConfigured": len(STATION_CODES),
            "climatology": {"years": CLIMATOLOGY_YEARS, "windowDays": CLIMATOLOGY_WINDOW_DAYS},
            "anaTelemetriaUrl": ANA_TELEMETRIA_URL,
            "noaaSources": {
                "nino34Weekly": NOAA_CPC_NINO34_WEEKLY_URL,
                "tnaWeekly": NOAA_OOPC_TNA_NC_URL,
                "tsaWeekly": NOAA_OOPC_TSA_NC_URL,
                "tasiWeekly": NOAA_OOPC_TASI_NC_URL,
            },
        },
        "mainStations": [station_to_json(station) for station in main],
        "upperBasinStations": [station_to_json(station) for station in upper],
        "rainfall": RAINFALL_FALLBACK,
        "climateHistory": climate,
    }


def validate_dashboard(data: dict[str, Any]) -> list[str]:
    errors = []
    for key in ["updatedAt", "date", "sourceMode", "metadata", "mainStations", "upperBasinStations", "rainfall", "climateHistory"]:
        if key not in data:
            errors.append(f"Campo obrigatório ausente: {key}")
    for group_name in ["mainStations", "upperBasinStations"]:
        stations = data.get(group_name, [])
        if not isinstance(stations, list) or not stations:
            errors.append(f"{group_name} deve ser uma lista não vazia")
            continue
        for station in stations:
            station_id = station.get("id", "?")
            if len(station.get("levels30d", [])) != 30:
                errors.append(f"{group_name}.{station_id}: levels30d deve ter 30 pontos")
            if len(station.get("levels12m", [])) != 365:
                errors.append(f"{group_name}.{station_id}: levels12m deve ter 365 pontos")
    if len(data.get("climateHistory", [])) < 12:
        errors.append("climateHistory deve ter pelo menos 12 pontos semanais")
    return errors


def write_dashboard(path: Path, end_date: date | None = None, strict: bool = False) -> Path:
    dashboard = build_dashboard(end_date, strict)
    errors = validate_dashboard(dashboard)
    if errors:
        raise ValueError("Dashboard inválido:\n" + "\n".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def run_self_tests() -> list[tuple[str, bool]]:
    dashboard = build_dashboard(date(2026, 5, 20), strict=False)
    errors = validate_dashboard(dashboard)
    stations = dashboard["mainStations"] + dashboard["upperBasinStations"]
    climate = dashboard["climateHistory"]
    return [
        ("dashboard valida sem erros", not errors),
        ("há 4 pontos críticos", len(dashboard["mainStations"]) == 4),
        ("há 6 sentinelas de alta bacia", len(dashboard["upperBasinStations"]) == 6),
        ("cada estação tem 30 pontos", all(len(station["levels30d"]) == 30 for station in stations)),
        ("cada estação tem 365 pontos", all(len(station["levels12m"]) == 365 for station in stations)),
        ("climateHistory inclui Niño 3.4", any(row.get("nino34") is not None for row in climate)),
        ("climateHistory inclui atlDipole", any(row.get("atlDipole") is not None for row in climate)),
    ]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gera dashboard.json para o painel hidroclimático da Amazônia.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="Caminho de saída do dashboard.json")
    parser.add_argument("--end-date", default=None, help="Data final da série no formato YYYY-MM-DD")
    parser.add_argument("--strict", action="store_true", help="Falha se ANA/NOAA não retornarem dados reais suficientes")
    parser.add_argument("--test", action="store_true", help="Executa testes internos e não grava arquivo")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    end_date = parse_end_date(args.end_date)
    if args.test:
        tests = run_self_tests()
        for name, passed in tests:
            print(f"{'OK' if passed else 'FAIL'} - {name}")
        return 0 if all(passed for _, passed in tests) else 1
    output = write_dashboard(Path(args.output), end_date=end_date, strict=args.strict)
    print(f"Arquivo gerado: {output}")
    print(f"Data-base: {end_date.isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
