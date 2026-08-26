#!/usr/bin/env python3
"""Anomali raporunu HTML olarak üretir.

Girdi : data/anomalies.csv
Çıktı : reports/rapor_<tarih>.html  ve  reports/latest.html
"""
import csv
import html
import os
from datetime import date

DATA = os.path.join(os.path.dirname(__file__), "..", "data", "anomalies.csv")
REPORTS = os.path.join(os.path.dirname(__file__), "..", "reports")
TOP_N = 25

CORRIDOR_TR = {
    "CN->US": "Çin → ABD", "BR->US": "Brezilya → ABD", "TR->US": "Türkiye → ABD",
    "CN->BR": "Çin → Brezilya", "US->BR": "ABD → Brezilya", "TR->BR": "Türkiye → Brezilya",
}


def money(v):
    v = float(v)
    if v >= 1e9: return f"${v/1e9:.2f} Mr"
    if v >= 1e6: return f"${v/1e6:.2f} M"
    if v >= 1e3: return f"${v/1e3:.0f} B"
    return f"${v:.0f}"


def main():
    rows = []
    if os.path.exists(DATA):
        with open(DATA, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

    by_corridor = {}
    for r in rows:
        by_corridor.setdefault(r["corridor"], []).append(r)

    today = date.today().isoformat()
    parts = [f"""<!DOCTYPE html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Gümrük Peak Raporu {today}</title>
<style>
body{{font-family:-apple-system,'Segoe UI',Roboto,sans-serif;background:#faf9f5;color:#1a1915;margin:0;line-height:1.5}}
.wrap{{max-width:1000px;margin:0 auto;padding:36px 20px}}
h1{{font-size:24px;margin:0 0 4px}} .sub{{color:#6b675e;font-size:13px;margin-bottom:24px}}
h2{{font-size:17px;margin:30px 0 8px;border-bottom:1px solid #e8e5dd;padding-bottom:6px}}
table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid #e8e5dd;font-size:13px;margin:8px 0}}
th{{background:#f4f2ec;text-align:left;padding:8px 10px;font-size:11.5px;text-transform:uppercase;color:#6b675e}}
td{{padding:7px 10px;border-top:1px solid #e8e5dd}}
.new{{color:#0f6b5c;font-weight:700}} .num{{text-align:right;white-space:nowrap}}
.g{{font-weight:700;color:#9a3412}} .empty{{color:#6b675e;font-size:13px;padding:10px 0}}
</style></head><body><div class="wrap">
<h1>Gümrük İhracat-Artışı (Peak) Raporu</h1>
<div class="sub">Üretim tarihi: {today} · Yöntem: son 3 ay ortalaması vs. önceki 12 ay baseline · Filtre: aylık ≥ $100B, z≥2 veya artış ≥%50</div>"""]

    order = ["CN->US", "BR->US", "TR->US", "CN->BR", "US->BR", "TR->BR"]
    for c in order:
        title = CORRIDOR_TR.get(c, c)
        items = by_corridor.get(c, [])[:TOP_N]
        parts.append(f"<h2>{title} <span style='font-weight:400;color:#6b675e'>({len(by_corridor.get(c, []))} anomali)</span></h2>")
        if not items:
            parts.append("<div class='empty'>Bu koridorda eşiği aşan anomali yok (veya veri henüz çekilmedi).</div>")
            continue
        parts.append("<table><tr><th>HS6</th><th>Ürün</th><th class='num'>Son 3 ay (aylık ort.)</th>"
                     "<th class='num'>Baseline</th><th class='num'>Artış</th><th class='num'>Z</th></tr>")
        for r in items:
            g = r["growth_pct"]
            gcell = "<span class='new'>YENİ ÜRÜN</span>" if g == "NEW" else f"<span class='g'>%{g}</span>"
            parts.append(
                f"<tr><td><b>{html.escape(r['hs6'])}</b></td><td>{html.escape(r['desc'])}</td>"
                f"<td class='num'>{money(r['recent_avg_usd'])}</td>"
                f"<td class='num'>{money(r['baseline_avg_usd'])}</td>"
                f"<td class='num'>{gcell}</td><td class='num'>{r['z_score']}</td></tr>")
        parts.append("</table>")

    parts.append("<div class='sub' style='margin-top:30px'>Kaynaklar: US Census Bureau (ABD ithalatı), "
                 "Comex Stat / MDIC (Brezilya ithalatı). Ayna veri yaklaşımı: ihracatçı ülke verisi yerine "
                 "ithalatçı ülkenin resmî kayıtları kullanılır.</div></div></body></html>")

    os.makedirs(REPORTS, exist_ok=True)
    out = os.path.join(REPORTS, f"rapor_{today}.html")
    content = "\n".join(parts)
    with open(out, "w", encoding="utf-8") as f:
        f.write(content)
    with open(os.path.join(REPORTS, "latest.html"), "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Rapor: {out}")


if __name__ == "__main__":
    main()
