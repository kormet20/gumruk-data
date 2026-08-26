#!/usr/bin/env python3
"""Brezilya ithalat verisini Comex Stat API'den çeker (aylık, NCM→HS6).

Koridorlar (Brezilya'ya giden): Çin→BR, ABD→BR, Türkiye→BR
Çıktı: data/br_imports.csv  (time, corridor, hs6, desc, value_usd)
Artımlı çalışır. API key gerektirmez.
"""
import csv
import json
import os
import ssl
import sys
import time as _t
import urllib.request
from datetime import date

BASE = "https://api-comexstat.mdic.gov.br"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "br_imports.csv")
START_MONTH = "2023-01"

# Ülke isimleri (API'nin ülke tablosundan koda çevrilir)
TARGETS = {"China": "CN->BR", "United States": "US->BR", "Turkey": "TR->BR"}
# Portekizce olasılıklar için yedek eşleşme
ALT_NAMES = {
    "China": ["China"],
    "United States": ["United States", "United States of America", "Estados Unidos"],
    "Turkey": ["Turkey", "Türkiye", "Turquia", "Turquía"],
}

CTX = ssl.create_default_context()


def http_json(url, payload=None, retries=3):
    for attempt in range(retries):
        try:
            if payload is not None:
                req = urllib.request.Request(
                    url, data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json", "User-Agent": "gumruk-data/1.0"})
            else:
                req = urllib.request.Request(url, headers={"User-Agent": "gumruk-data/1.0"})
            with urllib.request.urlopen(req, timeout=180, context=CTX) as r:
                return json.load(r)
        except Exception:
            if attempt == retries - 1:
                raise
            _t.sleep(8 * (attempt + 1))


def resolve_country_codes():
    """API ülke tablosundan hedef ülkelerin kodlarını bul."""
    data = http_json(BASE + "/tables/countries?language=en")
    rows = data.get("data", {}).get("list", data.get("data", []))
    if isinstance(rows, dict):
        rows = rows.get("list", [])
    codes = {}
    for canonical, corridor in TARGETS.items():
        wanted = [n.lower() for n in ALT_NAMES[canonical]]
        for row in rows:
            name = str(row.get("text") or row.get("country") or row.get("noPaisIng") or "").lower()
            if name in wanted:
                codes[corridor] = row.get("id") or row.get("coPais")
                break
    missing = [c for c in TARGETS.values() if c not in codes]
    if missing:
        raise RuntimeError(f"Ulke kodu bulunamadi: {missing} — tables/countries yaniti degismis olabilir")
    return codes  # {corridor: code}


def existing_months():
    if not os.path.exists(OUT):
        return set()
    with open(OUT, newline="", encoding="utf-8") as f:
        return {row["time"] for row in csv.DictReader(f)}


def month_range(start, end):
    y, m = int(start[:4]), int(start[5:7])
    ey, em = int(end[:4]), int(end[5:7])
    out = []
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def latest_expected_month():
    """Brezilya bir önceki ayı ayın ilk günlerinde yayınlar."""
    t = date.today()
    y, m = t.year, t.month - 1
    if m <= 0:
        m += 12
        y -= 1
    return f"{y:04d}-{m:02d}"


def fetch_period(code, frm, to):
    """Bir ülke için dönem verisini NCM detayında çek."""
    payload = {
        "flow": "import",
        "monthDetail": True,
        "period": {"from": frm, "to": to},
        "filters": [{"filter": "country", "values": [code]}],
        "details": ["ncm"],
        "metrics": ["metricFOB"],
        "language": "en",
    }
    data = http_json(BASE + "/general?language=en", payload)
    d = data.get("data", {})
    return d.get("list", d if isinstance(d, list) else [])


def main():
    have = existing_months()
    months = [m for m in month_range(START_MONTH, latest_expected_month()) if m not in have]
    if not months:
        print("ComexStat: yeni ay yok, guncel.")
        return
    codes = resolve_country_codes()

    # ComexStat API 'period' parametresini yil araligi + ay penceresi olarak yorumlar;
    # bu yuzden her yili kendi icinde (ayni-yil from/to ile) cekiyoruz.
    year_windows = {}
    for m in months:
        y = m[:4]
        year_windows.setdefault(y, []).append(m)

    new_rows = []
    for corridor, code in codes.items():
        rows = []
        for y in sorted(year_windows):
            ym = sorted(year_windows[y])
            rows.extend(fetch_period(code, ym[0], ym[-1]))
            _t.sleep(1)
        for r in rows:
            ym_y = str(r.get("year") or r.get("coAno") or "")
            ym_m = str(r.get("monthNumber") or r.get("coMes") or "").zfill(2)
            t = f"{ym_y}-{ym_m}"
            if t not in months:
                continue
            ncm = str(r.get("coNcm") or r.get("ncm") or "")
            desc = str(r.get("noNcm") or r.get("ncmDescription") or r.get("description") or "")[:120]
            val = r.get("metricFOB") or r.get("vlFob") or 0
            new_rows.append({
                "time": t,
                "corridor": corridor,
                "hs6": ncm[:6],
                "desc": desc,
                "value_usd": str(val),
            })
        print(f"ComexStat {corridor}: {len(rows)} ham satir")
        _t.sleep(2)

    if new_rows:
        # NCM(8) → HS6 toplama
        agg = {}
        for r in new_rows:
            k = (r["time"], r["corridor"], r["hs6"])
            if k in agg:
                agg[k]["value_usd"] = str(float(agg[k]["value_usd"]) + float(r["value_usd"]))
            else:
                agg[k] = dict(r)
        rows = sorted(agg.values(), key=lambda x: (x["time"], x["corridor"], x["hs6"]))
        write_header = not os.path.exists(OUT)
        with open(OUT, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["time", "corridor", "hs6", "desc", "value_usd"])
            if write_header:
                w.writeheader()
            w.writerows(rows)
        print(f"ComexStat: {len(rows)} satir eklendi.")
    else:
        print("ComexStat: eklenecek yeni satir yok.")


if __name__ == "__main__":
    sys.exit(main())
