#!/usr/bin/env python3
"""ABD ithalat verisini US Census API'den çeker (aylık, HS6).

Koridorlar (ABD'ye giden): Çin→ABD, Brezilya→ABD, Türkiye→ABD
Çıktı: data/us_imports.csv  (time, corridor, hs6, desc, value_usd)
Artımlı çalışır: mevcut CSV'deki son aydan sonrasını çeker.
"""
import csv
import json
import os
import sys
import time as _t
import urllib.request
import urllib.parse
from datetime import date

API = "https://api.census.gov/data/timeseries/intltrade/imports/hs"
KEY = os.environ.get("CENSUS_API_KEY", "")

# Census ülke kodları
COUNTRIES = {
    "5700": "CN->US",   # Çin
    "3510": "BR->US",   # Brezilya
    "4890": "TR->US",   # Türkiye
}

START_MONTH = "2023-01"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "us_imports.csv")


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
    """Census ~5-6 hafta gecikmeli yayınlar; bugünden 2 ay geriyi hedefle."""
    t = date.today()
    y, m = t.year, t.month - 2
    if m <= 0:
        m += 12
        y -= 1
    return f"{y:04d}-{m:02d}"


def existing_months():
    if not os.path.exists(OUT):
        return set()
    with open(OUT, newline="", encoding="utf-8") as f:
        return {row["time"] for row in csv.DictReader(f)}


def fetch_month(cty, month, retries=3):
    params = {
        "get": "I_COMMODITY,I_COMMODITY_SDESC,GEN_VAL_MO",
        "COMM_LVL": "HS6",
        "CTY_CODE": cty,
        "time": month,
    }
    if KEY:
        params["key"] = KEY
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                if r.status == 204:
                    return None  # ay henüz yayınlanmamış
                data = json.load(r)
                return data
        except urllib.error.HTTPError as e:
            if e.code in (204, 404):
                return None
            if attempt == retries - 1:
                raise
            _t.sleep(5 * (attempt + 1))
        except Exception:
            if attempt == retries - 1:
                raise
            _t.sleep(5 * (attempt + 1))
    return None


def main():
    have = existing_months()
    months = [m for m in month_range(START_MONTH, latest_expected_month()) if m not in have]
    if not months:
        print("Census: yeni ay yok, güncel.")
        return

    new_rows = []
    for month in months:
        got_any = False
        for cty, corridor in COUNTRIES.items():
            data = fetch_month(cty, month)
            if not data or len(data) < 2:
                continue
            hdr = data[0]
            i_hs = hdr.index("I_COMMODITY")
            i_desc = hdr.index("I_COMMODITY_SDESC")
            i_val = hdr.index("GEN_VAL_MO")
            for row in data[1:]:
                new_rows.append({
                    "time": month,
                    "corridor": corridor,
                    "hs6": row[i_hs],
                    "desc": (row[i_desc] or "")[:120],
                    "value_usd": row[i_val] or "0",
                })
            got_any = True
            _t.sleep(1)
        print(f"Census {month}: {'OK' if got_any else 'henuz yayinlanmamis'}")
        if not got_any:
            break  # sonraki aylar da yoktur

    if new_rows:
        write_header = not os.path.exists(OUT)
        with open(OUT, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["time", "corridor", "hs6", "desc", "value_usd"])
            if write_header:
                w.writeheader()
            w.writerows(new_rows)
        print(f"Census: {len(new_rows)} satir eklendi.")
    else:
        print("Census: eklenecek yeni satir yok.")


if __name__ == "__main__":
    sys.exit(main())
