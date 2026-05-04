# Indicator Spec — Daily Market Monitor

Country scope: **US, JP, DE, FR, IT, UK, CA, EA, KR, AU, CN** (G7 + Euro Area aggregate + Korea + Australia + China).

All Haver codes below are confirmed present in the local `haver-data` parquet at the time of writing (2026-04-29).

## Panels

### 1. Sovereign yields (daily)
Yield curve points: 3M, 1Y, 2Y, 5Y, 10Y, 20Y, 30Y. All `@intdaily` unless noted. **All codes verified present in parquet (2026-04-29).**

| Country | 3M | 1Y | 2Y | 5Y | 10Y | 20Y | 30Y |
|---|---|---|---|---|---|---|---|
| US | r111m3m | r111m1y | r111m2y | r111m5y | `fcm10@daily` | `fcm20@daily` | `fcm30@daily` |
| JP | r158m3m | r158m1y | r158m2y | r158m5y | r158ga | r158gk | r158gt |
| DE | r134e3m | r134m1y | r134m2y | r134m5y | r134ma | r134mk | r134mt |
| FR | r132m3m | r132m1y | r132m2y | r132m5y | r132ma | r132mk | r132mt |
| IT | r136m3m | r136m1y | r136m2y | r136m5y | r136ma | r136mk | r136mt |
| UK | t112d3m\* | r112m1y | r112m2y | r112m5y | r112ma | r112mk | r112mt |
| CA | r156m3m | r156m1y | r156m2y | r156m5y | r156ma | r156mk | r156mt |
| KR | r542s3m\* | r542m1y | r542m2y | r542m5y | r542ma | r542mk | r542mt |
| AU | r193g3m\* | r193m1y | r193m2y | r193m5y | r193ma | r193mk | r193mt |

\* short-end uses available equivalent (T-bill / deposit / bank-bill rate).

**US note:** `r111m10y/20y/30y@intdaily` do not exist. Use Treasury constant-maturity series from the `daily` database: `fcm10`, `fcm20`, `fcm30`. (1Y–5Y are still in `intdaily`.)

**EA aggregate:** not directly available — proxy with DE (Bund) for risk-free, or compute IT–DE / FR–DE spreads for periphery risk.

### 2. Breakeven inflation (daily)
10Y BEI where directly available. All verified present (2026-04-29) except where noted.

- US `fin10@daily` (10Y nominal − 10Y TIPS)
- JP `r158fbv@intdaily`
- DE `r134fbv@intdaily`
- FR `r132fbv@intdaily`
- CA `r156fbv@intdaily`
- AU `r193fbv@intdaily`
- KR `r542fbv@intdaily`
- UK — **no true BEI available**, leave gap (10Y forward inflation proxy removed).
- IT — **no series available**, leave gap.

### 3. FX (daily, vs USD)
- JPY `x111jpj`
- GBP `x111ukj`
- EUR `x111euj` (Euro/USD; invert for USD/EUR)
- CHF `x111chj`
- CAD `x111caj`
- AUD `x111auj`
- KRW `x111krj`
- WSJ Dollar Index `fxwsj@daily` (proxy for DXY)

### 4. Equity indices (daily, level + daily / 5d / 21d % change)
- US `s111sp5` (S&P 500)
- JP `s158nka` (Nikkei 225)
- DE `s134dax` (DAX)
- UK `s112fta` (FTSE All-Share)
- IT `s136mbi` (FTSE MIB)
- FR `s132cac` (CAC 40)
- CA `s156toi` (S&P/TSX)
- KR `s542cex` (KOSPI)
- AU `s193aor` (All Ordinaries)
- EA — use DE DAX or add EuroStoxx if available

### 5. Volatility indices (daily)
- US `s111vix` (VIX)
- DE `s134vdx` (VDAX-NEW)
- JP `s158nkx` (Nikkei vol)
- CA `s156sxc` (TSX 60 VIX)
- KR `s542v2x` (KOSPI 200 vol)

### 6. Policy rates (daily)
- US `r111rdt` (Fed funds target)
- JP `r158tar` (BoJ policy rate)
- UK `r112rd` (BoE Bank Rate)
- CA `r156dtr` (BoC overnight target)
- AU `r193rtr` (RBA cash rate)
- KR `r542rd` (BoK base rate)
- EA `r023rm` (ECB MRO)

### 7. Overnight rates (daily)
- US `r111obr` (OBFR)
- JP `r158rdu` (TONAR)
- UK `r112los` (SONIA)
- CA `r156rr` (CORRA)
- KR `r542ko` (KOFR)

### 8. Commodities & uncertainty (daily)
- WTI/oil `gscl@daily` (S&P GSCI Crude Oil index)
- Gold `gsgc@daily` (S&P GSCI Gold index)
- US Economic Policy Uncertainty `sepuin@daily`
- US Trade Policy Uncertainty `stpui@daily`

## Macro releases (lower-frequency, displayed alongside daily)
To be filled in next pass — pull from Japan/G10 monthly tags in `series.yaml`:
- Headline & core CPI (YoY)
- Industrial production (YoY)
- Composite PMI
- Unemployment rate
- Wages

## Transforms (in build script)
- `level` — raw last observation
- `chg_1d`, `chg_5d`, `chg_21d` — absolute change in pp for rates / yields, % change for prices / FX / equities
- `z_5y` — z-score of latest level vs trailing 5-year mean / sd

## Output JSON shape (target)
One file per panel, e.g. `public/data/yields.json`:

```json
{
  "vintage": "2026-04-29",
  "rows": [
    {
      "country": "JP",
      "series": "r158ga@intdaily",
      "label": "JGB 10Y",
      "latest": 1.025,
      "chg_1d": 0.012,
      "chg_5d": 0.04,
      "chg_21d": -0.08,
      "z_5y": 1.85,
      "history": [["2021-04-29", 0.10], ["2021-04-30", 0.11], ...]
    }
  ]
}
```

## Verification (2026-04-29)
All codes in this spec confirmed present in `data/data.parquet` except:
- **US 10Y/20Y/30Y in `intdaily`** — not available; use `fcm10/20/30@daily` instead (now reflected above).
- **Italy 10Y BEI** — no inflation-linked BTP / BEI series in parquet. Gap left as-is.
- **UK 10Y BEI** — no true BEI available; row omitted (forward-inflation proxy removed).

## Open items
- Decide on EA aggregate proxy (Bund or composite)
- Decide on which trailing window for z-scores (5y default; user-toggleable?)
- Decide whether to bundle history (large) or only latest + sparkline window in panel JSON
