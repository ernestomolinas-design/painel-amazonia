import argparse
import json
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path


CLIMATOLOGY_WINDOW_DAYS = 30


def day_of_year(value: date) -> int:
    return int(value.strftime("%j"))


def circular_day_distance(a: int, b: int) -> int:
    raw = abs(a - b)
    return min(raw, 366 - raw)


def percentile(values, q):
    values = sorted(values)
    if not values:
        return None
    if len(values) == 1:
        return values[0]

    pos = (len(values) - 1) * q / 100
    lower = int(pos)
    upper = min(lower + 1, len(values) - 1)
    weight = pos - lower
    return values[lower] * (1 - weight) + values[upper] * weight


def mean(values):
    return sum(values) / len(values) if values else None


def median(values):
    return percentile(values, 50)


def load_dashboard(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def find_station(data, station_id):
    all_stations = data.get("mainStations", []) + data.get("upperBasinStations", [])
    for station in all_stations:
        if station.get("id") == station_id:
            return station
    raise SystemExit(f"Estação não encontrada: {station_id}")


def parse_date(text):
    return datetime.strptime(text, "%Y-%m-%d").date()


def audit_station_date(data, station_id, target_date_text):
    station = find_station(data, station_id)
    target_date = parse_date(target_date_text)
    target_doy = day_of_year(target_date)

    levels12m = station.get("levels12m", [])
    target_points = [p for p in levels12m if p.get("date") == target_date_text]

    print(f"\nEstação: {station.get('name')} ({station.get('id')})")
    print(f"Fonte da estação: {station.get('source')}")
    print(f"Data alvo: {target_date_text}")

    if target_points:
        p = target_points[0]
        level = p.get("level")
        clim = p.get("mlt")
        p05 = p.get("p05")
        p95 = p.get("p95")
        print("\nValor no dashboard.json:")
        print(f"  cota observada: {level} cm")
        print(f"  climatologia diária / mlt: {clim} cm")
        print(f"  p05: {p05} cm")
        print(f"  p95: {p95} cm")
        if isinstance(level, (int, float)) and isinstance(clim, (int, float)):
            print(f"  anomalia: {level - clim:+.0f} cm")
    else:
        print("\nA data alvo não aparece em levels12m.")

    print("\nObservação importante:")
    print(
        "Este auditor usa apenas o dashboard.json atual. "
        "Ele consegue verificar a coerência do valor exibido, mas não reconstrói "
        "a amostra histórica completa de 10 anos se ela não estiver salva no JSON."
    )

    print("\nAmostra disponível em levels12m ao redor do mesmo dia do ano:")
    nearby = []
    for point in levels12m:
        if not isinstance(point.get("level"), (int, float)):
            continue
        try:
            point_date = parse_date(point["date"])
        except Exception:
            continue

        dist = circular_day_distance(day_of_year(point_date), target_doy)
        if dist <= CLIMATOLOGY_WINDOW_DAYS:
            nearby.append(
                {
                    "date": point["date"],
                    "level": point.get("level"),
                    "mlt": point.get("mlt"),
                    "p05": point.get("p05"),
                    "p95": point.get("p95"),
                    "source": point.get("source"),
                    "dist": dist,
                }
            )

    nearby.sort(key=lambda x: x["date"])

    if not nearby:
        print("  Nenhum ponto próximo encontrado em levels12m.")
        return

    levels = [x["level"] for x in nearby if isinstance(x["level"], (int, float))]
    mlts = [x["mlt"] for x in nearby if isinstance(x["mlt"], (int, float))]

    print(f"  pontos encontrados em ±{CLIMATOLOGY_WINDOW_DAYS} dias do ciclo anual: {len(nearby)}")
    print(f"  cota observada min/média/mediana/max: {min(levels):.0f} / {mean(levels):.0f} / {median(levels):.0f} / {max(levels):.0f} cm")
    print(f"  mlt min/média/mediana/max: {min(mlts):.0f} / {mean(mlts):.0f} / {median(mlts):.0f} / {max(mlts):.0f} cm")

    print("\nPrimeiros pontos próximos:")
    for row in nearby[:10]:
        level = row.get("level")
        clim = row.get("mlt")
        anom = level - clim if isinstance(level, (int, float)) and isinstance(clim, (int, float)) else None
        print(
            f"  {row['date']}  level={level:>5}  mlt={clim:>5}  "
            f"anom={anom:+5.0f}  p05={row.get('p05')}  p95={row.get('p95')}  source={row.get('source')}"
        )

    print("\nÚltimos pontos próximos:")
    for row in nearby[-10:]:
        level = row.get("level")
        clim = row.get("mlt")
        anom = level - clim if isinstance(level, (int, float)) and isinstance(clim, (int, float)) else None
        print(
            f"  {row['date']}  level={level:>5}  mlt={clim:>5}  "
            f"anom={anom:+5.0f}  p05={row.get('p05')}  p95={row.get('p95')}  source={row.get('source')}"
        )


def main():
    parser = argparse.ArgumentParser(description="Audita anomalias/climatologia no dashboard.json.")
    parser.add_argument("--dashboard", default="public/data/dashboard.json")
    parser.add_argument("--station", required=True, help="ID da estação, ex.: manaus, labrea, barcelos")
    parser.add_argument("--date", required=True, help="Data no formato YYYY-MM-DD")
    args = parser.parse_args()

    data = load_dashboard(args.dashboard)
    audit_station_date(data, args.station, args.date)


if __name__ == "__main__":
    main()