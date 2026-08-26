# gumruk-data

6 ticaret koridorunda (Çin→ABD, Brezilya→ABD, Türkiye→ABD, Çin→Brezilya, ABD→Brezilya, Türkiye→Brezilya)
HS6 bazında ihracat artışı (peak) tespiti yapan otomatik veri hattı.

## Nasıl çalışır

1. **GitHub Actions** her Pazartesi 06:00 UTC'de çalışır (`.github/workflows/update-data.yml`)
2. `scripts/fetch_census.py` — ABD ithalatını US Census API'den çeker (ayna veri: CN/BR/TR → ABD)
3. `scripts/fetch_comexstat.py` — Brezilya ithalatını Comex Stat API'den çeker (ayna veri: CN/US/TR → BR)
4. `scripts/anomaly.py` — son 3 ay vs. önceki 12 ay baseline; z-score + %artış + yeni-ürün tespiti
5. `scripts/make_report.py` — `reports/latest.html` raporunu üretir
6. Sonuçlar repoya commit edilir; Claude oturumu repoyu çekip raporu teslim eder

## Kurulum

- Repo Settings → Secrets and variables → Actions → **New repository secret**:
  `CENSUS_API_KEY` = Census API anahtarınız
- İlk çalıştırma: Actions sekmesi → "Gumruk verisini guncelle" → **Run workflow**
  (ilk seferde ~3,5 yıllık veri çekilir, 10-20 dk sürebilir)

## Eşikler (`scripts/anomaly.py`)

- `MIN_RECENT_USD = 100_000` — son 3 ay aylık ortalaması bunun altındaysa elenir
- `Z_MIN = 2.0`, `GROWTH_MIN = 0.5` (%50)
