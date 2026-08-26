#!/usr/bin/env python3
"""Anomali motoru: son 3 ay vs. önceki 12 ay baseline.

Girdi : data/us_imports.csv + data/br_imports.csv
Çıktı : data/anomalies.csv — koridor×HS6 bazında peak skorları

Yöntem:
- Her koridor×HS6 için aylık USD serisi kurulur (eksik aylar 0).
- recent  = son 3 ayın ortalaması
- base    = ondan önceki 12 ayın ortalaması ve std'si
- growth  = recent/base - 1
- z       = (recent - base_mean) / base_std
- new_flag= baseline'da hiç ticaret yokken şimdi başlamışsa "YENI"
Filtreler (gürültü elemek için):
- recent aylık ortalama >= MIN_RECENT_USD
- z >= Z_MIN  veya  growth >= GROWTH_MIN  veya  YENI ürün
"""
import csv
import math
import os
import statistics as st
from collections import defaultdict

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "anomalies.csv")

MIN_RECENT_USD = 100_000   # son 3 ay aylık ortalama en az bu kadar olmalı
Z_MIN = 2.0
GROWTH_MIN = 0.5           # %50
RECENT_N = 3
BASE_N = 12


def load_rows():
    rows = []
    for fn in ("us_imports.csv", "br_imports.csv"):
        p = os.path.join(DATA_DIR, fn)
        if os.path.exists(p):
            with open(p, newline="", encoding="utf-8") as f:
                rows.extend(csv.DictReader(f))
    return rows


def main():
    rows = load_rows()
    if not rows:
        print("Veri yok — once fetch scriptlerini calistir.")
        return

    months = sorted({r["time"] for r in rows})
    # Koridor bazında son yayınlanan ay farklı olabilir → koridor bazlı ay listesi
    corridor_months = defaultdict(set)
    series = defaultdict(dict)   # (corridor, hs6) -> {month: value}
    descs = {}
    for r in rows:
        key = (r["corridor"], r["hs6"])
        try:
            v = float(r["value_usd"])
        except ValueError:
            v = 0.0
        series[key][r["time"]] = series[key].get(r["time"], 0.0) + v
        corridor_months[r["corridor"]].add(r["time"])
        if r.get("desc"):
            descs[key] = r["desc"]

    results = []
    for (corridor, hs6), sv in series.items():
        cm = sorted(corridor_months[corridor])
        if len(cm) < RECENT_N + 6:   # en az 9 ay veri olsun
            continue
        recent_m = cm[-RECENT_N:]
        base_m = cm[-(RECENT_N + BASE_N):-RECENT_N]
        recent_vals = [sv.get(m, 0.0) for m in recent_m]
        base_vals = [sv.get(m, 0.0) for m in base_m]
        recent = sum(recent_vals) / len(recent_vals)
        base_mean = sum(base_vals) / len(base_vals) if base_vals else 0.0
        base_std = st.pstdev(base_vals) if len(base_vals) > 1 else 0.0

        if recent < MIN_RECENT_USD:
            continue

        is_new = base_mean == 0.0
        growth = (recent / base_mean - 1) if base_mean > 0 else math.inf
        z = (recent - base_mean) / base_std if base_std > 0 else (math.inf if is_new else 0.0)

        if not (is_new or z >= Z_MIN or growth >= GROWTH_MIN):
            continue

        results.append({
            "corridor": corridor,
            "hs6": hs6,
            "desc": descs.get((corridor, hs6), ""),
            "recent_avg_usd": round(recent),
            "baseline_avg_usd": round(base_mean),
            "growth_pct": "NEW" if is_new else round(growth * 100, 1),
            "z_score": "" if math.isinf(z) else round(z, 2),
            "recent_months": ",".join(recent_m),
            "score": (9999 if is_new else min(z, 50)) * math.log10(max(recent, 10)),
        })

    results.sort(key=lambda r: (r["corridor"], -r["score"]))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()) if results else
                           ["corridor", "hs6", "desc", "recent_avg_usd", "baseline_avg_usd",
                            "growth_pct", "z_score", "recent_months", "score"])
        w.writeheader()
        w.writerows(results)
    print(f"Anomali: {len(results)} kayit -> {OUT}")


if __name__ == "__main__":
    main()
