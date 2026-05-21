import json
from pathlib import Path

data = json.loads(Path("public/data/dashboard.json").read_text(encoding="utf-8"))

for group_name in ["mainStations", "upperBasinStations"]:
    print("\n==", group_name, "==")
    for st in data[group_name]:
        levels = st.get("levels12m", [])
        if not levels:
            continue

        vals = [p.get("level") for p in levels if isinstance(p.get("level"), (int, float))]
        p05s = [p.get("p05") for p in levels if isinstance(p.get("p05"), (int, float))]
        p95s = [p.get("p95") for p in levels if isinstance(p.get("p95"), (int, float))]

        sources = {}
        for p in levels:
            source = p.get("source", "sem fonte")
            sources[source] = sources.get(source, 0) + 1

        jumps = []
        for a, b in zip(levels, levels[1:]):
            if isinstance(a.get("level"), (int, float)) and isinstance(b.get("level"), (int, float)):
                d = b["level"] - a["level"]
                if abs(d) > 80:
                    jumps.append((b.get("date"), d, a["level"], b["level"]))

        widths = [
            b - a for a, b in zip(p05s, p95s)
            if isinstance(a, (int, float)) and isinstance(b, (int, float))
        ]

        print(f"\n{st['name']} ({st['id']})")
        print("  source estação:", st.get("source"))
        print("  fontes levels12m:", sources)
        print("  nível min/max:", min(vals), max(vals))
        print("  p05/p95 width min/max:", min(widths), max(widths))
        print("  saltos >80 cm/dia:", len(jumps), jumps[:8])