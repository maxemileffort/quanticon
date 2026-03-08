# Trading Data Pipeline: Databento → MT5

Converts Databento OHLCV exports to MetaTrader 5 bar format, with optional outlier filtering, continuous series building, and QC validation.

## Dependencies

```
pip install pandas
```

---

## Pipeline Overview

```
[0] csv_profile.py          ← optional: inspect raw Databento CSV
        ↓
[1] bento_ingestion_prep.py ← convert to per-contract MT5 CSVs
        ↓
   ┌────┴────┐
  [2a]      [2b]
mt5_outright  mt5_continuous   ← run one or both
  _merge.py    _builder.py
   └────┬────┘
        ↓
[3] mt5_qc_validate.py      ← audit any MT5 output directory
```

---

## Step 0 — csv_profile.py (optional)

Profile a raw Databento CSV to understand its structure before converting.

```bash
python csv_profile.py --file glbx-mdp3-20160121-20260221.ohlcv-1m.csv
```

**Default flags:** `--sample-rows 5`, `--chunk-size 250000`, `--max-categorical-unique 50`

**Output (stdout only — no files written):**

```
================================================================================
CSV PROFILE
================================================================================
File: glbx-mdp3-20160121-20260221.ohlcv-1m.csv
Size: 1.23 GB

[1] BASIC OVERVIEW
Columns (12): ['ts_event', 'symbol', 'open', 'high', 'low', 'close', 'volume', ...]
Dtypes from sample:
  - ts_event: object
  - symbol: object
  ...
Top 5 rows preview:
 ts_event  symbol  open  high  low  close  volume ...

[2] STREAMING PROFILE (large-file friendly)
Rows: 12,450,000
Approx duplicate rows (within chunks): 0

[3] MISSINGNESS
  - ts_event: 0 (0.00%)
  - symbol: 0 (0.00%)
  ...

[4] NUMERIC SUMMARY
  - open: count=12,450,000, min=1000.25, max=22000.0, mean=15234.12, zeros=0, negatives=0
  ...

[5] CATEGORICAL/TEXT SNAPSHOT
  - symbol: unique=48
      'NQZ24': 320,400
      'NQH25': 298,100
      ...

[6] DATETIME CHECKS
  - ts_event: min=2016-01-21 00:00:00+00:00, max=2026-02-21 23:59:00+00:00

[7] FINANCIAL HEURISTICS
  - symbol: ['symbol']
  - price: ['open', 'high', 'low', 'close']
  - size: ['volume']
  - side: (not detected)

Done.
```

---

## Step 1 — bento_ingestion_prep.py (required)

Convert a Databento CSV into one MT5-formatted CSV per contract symbol.

```bash
python bento_ingestion_prep.py \
  --input  "path/to/glbx-mdp3-....ohlcv-1m.csv" \
  --output "path/to/output/mt5_nq.csv"
```

**Required flags:** `--input`, `--output`

**Default flags:** columns auto-detected from names; `--tickvol-default 1.0`, `--vol-default 0.0`, `--spread-default 0.0`; no header row; comma separator.

**Output files:** One CSV per symbol, named `<output-stem>_<SYMBOL><ext>` (e.g. `mt5_nq_NQZ24.csv`, `mt5_nq_NQH25.csv`). Files are written to the output path's parent directory.

**File format (no header, 9 columns):**
```
2024.12.16,09:30,21423.75,21430.00,21418.25,21425.50,1,0,0
2024.12.16,09:31,21425.50,21440.00,21420.00,21437.25,1,0,0
```
Columns: `Date(YYYY.MM.DD), Time(HH:MM), Open, High, Low, Close, TickVol, Vol, Spread`

**Console output:**
```
Resolved columns:
  symbol: symbol
  ts: ts_event
  open/high/low/close: open, high, low, close
  vol: volume
  tickvol: (using default)
Wrote 320,400 rows for symbol 'NQZ24' -> mt5_nq_NQZ24.csv (dropped: 0)
Wrote 298,100 rows for symbol 'NQH25' -> mt5_nq_NQH25.csv (dropped: 12)
...
Done. Total rows written: 12,447,380
```

---

## Step 2a — mt5_outright_merge.py

Merge per-contract files into one chronologically sorted file per root, with rolling outlier filtering.

```bash
python mt5_outright_merge.py --input-dir "path/to/output"
```

> **Note:** By default only picks up files modified in the **last 24 hours**. Add `--all-files` to process everything regardless of modification time.

**Default flags:** `--input-dir .`, `--pattern mt5_*.csv`, `--hours-back 24`, outlier filter on (`--outlier-window 100`, `--outlier-min-periods 30`, `--outlier-z 8.0`); no deduplication; no header.

**Output files:** One CSV per root in the input directory:
```
mt5_nq_final_20160121-0000_20260221-2359.csv
mt5_mnq_final_20160121-0000_20260221-2359.csv
```

**Console output:**
```
[1/4] Scanning candidate files...
  Found 48 candidate files
[2/4] Classifying files...
  Outright files: 48
  Spread/rollover files skipped: 0
  Unknown files skipped: 0
[3/4] Merging outrights by root...
  -> MNQ: reading 48 file(s)
     progress 48/48
     root summary: input=6,200,000, outlier_dropped=12, dedupe_dropped=0, written=6,199,988
     wrote 6,199,988 rows -> mt5_mnq_final_20160121-0000_20260221-2359.csv
  -> NQ: reading 48 file(s)
     ...
[4/4] Done.
  Run summary: roots_written=2, input_rows=12,400,000, outlier_dropped=24, dedupe_dropped=0, written_rows=12,399,976
```

---

## Step 2b — mt5_continuous_builder.py

Build a roll-aware continuous series from per-contract files. Switches contracts using volume crossover, falling back to calendar roll if crossover is not detected.

```bash
python mt5_continuous_builder.py --input-dir "path/to/output"
```

**Default flags:** `--pattern mt5_*.csv`, `--roll-policy volume`, `--volume-column Vol`, `--volume-crossover-days 2`, `--min-overlap-days 3`, `--calendar-days-before-expiry 7`; no header; no roll report written.

**Output files:** Written to `<input-dir>/continuous/`:
```
continuous/mt5_nq_continuous_volume_20160121-0000_20260221-2359.csv
continuous/mt5_mnq_continuous_volume_20160121-0000_20260221-2359.csv
```

**Console output:**
```
[CC] Found 48 candidate files
[CC] Parsed outright contract files: 48
[CC] Skipped non-contract files: 0
[CC] Building MNQ from 24 contracts...
[CC] MNQ: wrote 5,980,412 rows -> continuous/mt5_mnq_continuous_volume_20160121-0000_20260221-2359.csv
[CC] Building NQ from 24 contracts...
[CC] NQ: wrote 5,941,230 rows -> continuous/mt5_nq_continuous_volume_20160121-0000_20260221-2359.csv
[CC] Done. roots_written=2
```

> Run **2a** for raw merged data (all contract bars concatenated). Run **2b** for a single clean series suitable for backtesting (no overlapping contract periods).

---

## Step 3 — mt5_qc_validate.py

Audit any directory of MT5 CSVs and produce three diagnostic reports.

```bash
python mt5_qc_validate.py --input-dir "path/to/validate"
```

**Default flags:** `--pattern mt5_*.csv`; severe checks: `invalid_datetime, missing_ohlc, non_positive_ohlc, ohlc_structure_violation, duplicate_datetime`; warning checks: `flat_bar, outlier_return`; outlier params: window=100, min-periods=30, z=8.0; no cleaned files written.

**Output files:** Written to `<input-dir>/qc_reports/`:
```
qc_reports/mt5_qc_summary_20260303-142500.csv    ← one row per file, all check counts
qc_reports/mt5_qc_detail_20260303-142500.csv     ← one row per flagged bar
qc_reports/mt5_qc_daily_20260303-142500.csv      ← anomalies grouped by calendar day
```

**Console output:**
```
[QC] Found 2 files matching 'mt5_*.csv'
[QC] (1/2) Checking mt5_nq_final_20160121-0000_20260221-2359.csv ...
      rows=6,199,988, severe=0, warning=412, outlier_return=412, dup_dt=0
[QC] (2/2) Checking mt5_mnq_final_20160121-0000_20260221-2359.csv ...
      rows=6,199,988, severe=0, warning=387, outlier_return=387, dup_dt=0
[QC] Done.
[QC] Summary report: qc_reports/mt5_qc_summary_20260303-142500.csv
[QC] Detail report:  qc_reports/mt5_qc_detail_20260303-142500.csv
[QC] Daily report:   qc_reports/mt5_qc_daily_20260303-142500.csv
```

---

---

## Alpha Discovery Scripts

A second set of scripts for finding statistical edge in the MT5 data. Goal: identify patterns strong enough to pass a prop firm challenge (typical: 8–10% profit target, 5% max drawdown).

### Dependencies

```
pip install pandas numpy scipy statsmodels matplotlib
```

### Run Order

```
alpha_resample.py      ← Step A: build resampled timeframe cache (run first)
        ↓
alpha_stationarity.py  ─┐
alpha_calendar.py       ├─ Steps B–F: independent analyses (any order)
alpha_gaps.py           │
alpha_momentum.py       │
alpha_volatility.py    ─┘
        ↓
alpha_screener.py      ← Step G: walk-forward OOS test of surviving signals
```

All alpha scripts write CSV reports to `alpha_output/` by default.

---

### Step A — alpha_resample.py *(run first)*

Resamples the 1-min MT5 CSV into 5m, 15m, 30m, 1h, 4h, and daily frames. All downstream alpha scripts read these cached files.

```bash
python alpha_resample.py \
  --input "C:\...\mt5_mnq_final_....csv" \
  --output-dir alpha_output
```

**Default flags:** `--timeframes 5min,15min,30min,1h,4h,D`

**Output files** (in `alpha_output/resampled/`):
```
mnq_5m.csv    mnq_15m.csv    mnq_30m.csv
mnq_1h.csv    mnq_4h.csv     mnq_daily.csv
```
Each file has a header row and columns: `datetime, Open, High, Low, Close, Vol, return, log_return, range, body, atr14`

**Console:**
```
[resample] Loading ... 1m rows: 2,357,957  (2019-05-05 to 2026-02-20)
[resample]     5m ->  471,591 bars (2019-05-05 to 2026-02-20) -> mnq_5m.csv
[resample]    15m ->  157,197 bars -> mnq_15m.csv
[resample]    30m ->   78,598 bars -> mnq_30m.csv
[resample]     1h ->   39,299 bars -> mnq_1h.csv
[resample]     4h ->    9,824 bars -> mnq_4h.csv
[resample]  daily ->    1,699 bars -> mnq_daily.csv
[resample] Done. Files written to alpha_output/resampled/
```

---

### Step B — alpha_stationarity.py

ADF test, Hurst exponent (R/S method), and Variance Ratio test at each timeframe. Answers: *should you trend-follow or mean-revert at each horizon?*

- Hurst < 0.45 = mean-reverting; Hurst > 0.55 = trending
- VR > 1.0 = momentum; VR < 1.0 = mean reversion

```bash
python alpha_stationarity.py --input-dir alpha_output/resampled
```

**Default flags:** `--timeframes 5m,15m,30m,1h,4h,daily`, `--vr-lags 2,4,8,16`, `--rolling-hurst-window 252`

**Output files:**
```
alpha_output/stationarity_report.csv     ← ADF + Hurst + VR per timeframe
alpha_output/rolling_hurst_daily.csv     ← rolling 252-day Hurst over time
```

**Console:**
```
TF       ADF(close)     ADF(ret)     Hurst     VR@2    VR@4    VR@8    VR@16   Interpretation
5m       0.732          0.000***     0.512     1.02    1.04    1.07    1.11    near-random walk, slight momentum
15m      0.741          0.000***     0.528     1.04    1.09    1.14    1.19    mild momentum
1h       0.698          0.000***     0.547     1.07    1.14    1.22    1.31    trending
daily    0.881          0.000***     0.563     1.09    1.18    1.29    1.42    trending
```

---

### Step C — alpha_calendar.py

Time-of-day, day-of-week, end-of-month turnover, and monthly seasonality patterns.

> **Timezone note:** If your data is in UTC (Databento default), time-of-day buckets will show in UTC. CME RTH = 14:30–21:00 UTC. Pass `--tz US/Eastern` to convert.

```bash
python alpha_calendar.py \
  --input "C:\...\mt5_mnq_final_....csv" \
  --daily-csv alpha_output/resampled/mnq_daily.csv
```

**Default flags:** `--bucket-minutes 30`, `--eom-window 5`

**Output files:**
```
alpha_output/calendar_tod.csv        ← mean return + win rate per 30-min bucket × day-of-week
alpha_output/calendar_dow.csv        ← daily stats per weekday
alpha_output/calendar_eom.csv        ← returns ±5 trading days around month end
alpha_output/calendar_monthly.csv    ← Jan–Dec seasonality
```

**Console (excerpt):**
```
=== Day-of-Week Returns (Daily) ===
  Mon: mean=-0.04%, median=-0.01%, win=47%, avg_range=142.3 pts, n=365
  Tue: mean=+0.12%, median=+0.08%, win=54%, avg_range=138.7 pts, n=363
  Wed: mean=+0.09%, median=+0.05%, win=53%, avg_range=141.2 pts, n=362
  Thu: mean=+0.05%, median=+0.02%, win=51%, avg_range=139.8 pts, n=364
  Fri: mean=-0.02%, median=-0.03%, win=49%, avg_range=136.4 pts, n=362

=== End-of-Month Effect (window = ±5 trading days) ===
  Offset -2 (Last 2      ): mean=+0.18%, win=58%, n=83  <<
  Offset -1 (Last 1      ): mean=+0.21%, win=60%, n=83  <<
  Offset  0 (Last (EOM)  ): mean=+0.08%, win=52%, n=83
  Offset +1 (First +1    ): mean=-0.05%, win=48%, n=83
```

---

### Step D — alpha_gaps.py

Overnight gap analysis: measures the move from prior RTH close to next RTH open and tests whether gaps fill within the same session.

> **Timezone note:** Default RTH times are `09:30` / `16:00`. For UTC data, pass `--rth-open 14:30 --rth-close 21:00` or `--tz US/Eastern`.

```bash
python alpha_gaps.py \
  --input "C:\...\mt5_mnq_final_....csv" \
  --tz US/Eastern
```

**Default flags:** `--rth-open 09:30`, `--rth-close 16:00`, `--gap-buckets 0.1,0.3,0.5,1.0`, `--min-gap-pct 0.01`

**Output files:**
```
alpha_output/gap_summary.csv    ← fill rate + median fill time per gap size bucket
alpha_output/gap_detail.csv     ← one row per gap event with date, gap_pct, filled, fill_time_min
```

**Console:**
```
=== Gap Fill Analysis (n=1,621 gap events) ===
Gap bucket   Fill rate   Med fill time      N
< 0.1%           71%          42 min      842
0.1–0.3%         64%          67 min      421
0.3–0.5%         51%         112 min      198
0.5–1.0%         38%         180 min       89
>= 1.0%          22%         N/A           31

Up-gaps fill: 62% (n=790) | Down-gaps fill: 68% (n=831)
Weekend gaps fill: 55% (n=340) | Weekday gaps fill: 66% (n=1,281)
```

---

### Step E — alpha_momentum.py

Return autocorrelation at each timeframe and simulation of simple N-bar momentum rules.

```bash
python alpha_momentum.py --input-dir alpha_output/resampled
```

**Default flags:** `--timeframes 5m,15m,30m,1h,4h,daily`, `--max-lag 20`, `--momentum-lookbacks 1,2,3,5,10`

**Output files:**
```
alpha_output/momentum_autocorr.csv    ← lag-N autocorr + Ljung-Box p-value per timeframe
alpha_output/momentum_rules.csv       ← Sharpe/win rate/PF for each N-bar momentum rule
alpha_output/momentum_tod.csv         ← lag-1 autocorr by hour of day (1h bars)
```

**Console:**
```
TF        Lag-1 AC    Sig        DW   Interpretation
5m        +0.02134    **      1.957   near-random walk
15m       +0.03121    ***     1.938   momentum
1h        +0.04412    ***     1.912   momentum
daily     +0.07231    ***     1.856   momentum

=== Best Momentum Rule per Timeframe (by Sharpe, long-only) ===
TF          N   Sharpe    Win%      PF    MaxDD   Trades
daily       5    0.681   54.2%   1.181   -8.3%    1,234
1h          2    0.552   53.0%   1.122  -12.1%   24,891
15m         3    0.412   52.1%   1.091  -15.4%   94,320
```

---

### Step F — alpha_volatility.py

ATR-based regime classification, NR4/NR7 setup testing, and volatility clustering (persistence of high/low vol periods).

```bash
python alpha_volatility.py --input-dir alpha_output/resampled
```

**Default flags:** `--atr-period 14`, `--regime-low-pct 33`, `--regime-high-pct 67`, `--forward-bars 1,2,3,5`

**Output files:**
```
alpha_output/volatility_regimes.csv       ← forward return stats per regime (daily + 1h)
alpha_output/volatility_regimes_1h.csv    ← same for 1h bars
alpha_output/volatility_clustering.csv    ← |return| autocorrelation (vol persistence)
alpha_output/nr4_nr7_stats.csv            ← NR4/NR7 setup forward return stats
```

**Console:**
```
=== Daily Return Stats by ATR Regime ===
Regime     N   Mean%    Win%    Sharpe
low      563  +0.04%   51.0%    0.281
mid      572  +0.06%   52.1%    0.412
high     564  -0.01%   49.0%    0.082

=== NR4 / NR7 Setup Analysis (daily) ===
  NR7 dir=up    n=89 | fwd1d=+0.15%  win=57.3%
  NR7 dir=down  n=94 | fwd1d=-0.11%  win=55.3%
  NR4 dir=up    n=210 | fwd1d=+0.08%  win=54.1%
```

---

### Step G — alpha_screener.py *(run last)*

Walk-forward out-of-sample test of 8 simple daily signals. Identifies which signals survive the IS→OOS transition with acceptable Sharpe decay.

**Pass criteria:** OOS Sharpe ≥ 0.3 AND Sharpe decay ≤ 50% of IS Sharpe.
**Note:** OOS Sharpe numbers are gross. Subtract ~0.3 for typical MNQ execution costs.

```bash
python alpha_screener.py \
  --input-dir alpha_output/resampled \
  --train-end 2023-12-31 \
  --test-start 2024-01-01
```

**Signals tested:** `always_long` (benchmark), `eom_momentum`, `dow_filter`, `momentum_5d`, `momentum_3d`, `low_vol`, `mid_vol`, `nr7_up`

**Output files:**
```
alpha_output/screener_results.csv          ← IS + OOS stats for all signals, sorted by OOS Sharpe
alpha_output/screener_equity_curves.csv    ← daily cumulative return per signal (full period)
```

**Console:**
```
=== Walk-Forward Signal Screener ===
Signal                 IS Sharpe  OOS Sharpe   Decay%  OOS MaxDD  OOS Win%   Result
eom_momentum               0.71        0.58    18.3%     -4.2%     59.0%     PASS
low_vol                    0.61        0.52    14.8%     -3.8%     55.0%     PASS
dow_filter                 0.38        0.31    18.4%     -5.1%     53.0%     PASS
momentum_5d                0.55        0.41    25.5%     -6.8%     52.0%     PASS
always_long                0.48        0.33    31.3%     -9.1%     53.5%     PASS
momentum_3d                0.41        0.22    46.3%     -7.9%     51.5%     FAIL
nr7_up                     0.29        0.09    69.0%     -9.4%     51.0%     FAIL
mid_vol                    0.31        0.18    41.9%     -7.2%     50.8%     FAIL

5/8 signals passed OOS validation.
Top signals: eom_momentum, low_vol, dow_filter

Prop firm viability note (subtract ~0.3 Sharpe for MNQ commissions):
  eom_momentum          : OOS Sharpe 0.580, adj 0.280 -> marginal
  low_vol               : OOS Sharpe 0.520, adj 0.220 -> marginal
  dow_filter            : OOS Sharpe 0.310, adj 0.010 -> marginal
```

---

### Alpha Script Default Flag Reference

| Script | Flag | Default |
|---|---|---|
| alpha_resample | `--timeframes` | `5min,15min,30min,1h,4h,D` |
| alpha_resample | `--output-dir` | `alpha_output` |
| alpha_stationarity | `--timeframes` | `5m,15m,30m,1h,4h,daily` |
| alpha_stationarity | `--vr-lags` | `2,4,8,16` |
| alpha_stationarity | `--rolling-hurst-window` | `252` |
| alpha_calendar | `--bucket-minutes` | `30` |
| alpha_calendar | `--eom-window` | `5` |
| alpha_calendar | `--tz` | off (use data as-is) |
| alpha_gaps | `--rth-open` | `09:30` |
| alpha_gaps | `--rth-close` | `16:00` |
| alpha_gaps | `--gap-buckets` | `0.1,0.3,0.5,1.0` |
| alpha_gaps | `--min-gap-pct` | `0.01` |
| alpha_momentum | `--max-lag` | `20` |
| alpha_momentum | `--momentum-lookbacks` | `1,2,3,5,10` |
| alpha_volatility | `--atr-period` | `14` |
| alpha_volatility | `--regime-low-pct` | `33` |
| alpha_volatility | `--regime-high-pct` | `67` |
| alpha_volatility | `--forward-bars` | `1,2,3,5` |
| alpha_screener | `--train-end` | `2023-12-31` |
| alpha_screener | `--test-start` | `2024-01-01` |
| alpha_screener | `--pass-oos-sharpe` | `0.3` |
| alpha_screener | `--max-decay-pct` | `50.0` |

---

## Default Flag Reference

| Script | Flag | Default |
|---|---|---|
| csv_profile | `--sample-rows` | `5` |
| csv_profile | `--chunk-size` | `250000` |
| csv_profile | `--max-categorical-unique` | `50` |
| bento_ingestion_prep | `--tickvol-default` | `1.0` |
| bento_ingestion_prep | `--vol-default` | `0.0` |
| bento_ingestion_prep | `--spread-default` | `0.0` |
| bento_ingestion_prep | `--with-header` | off |
| mt5_outright_merge | `--input-dir` | `.` (current dir) |
| mt5_outright_merge | `--hours-back` | `24` |
| mt5_outright_merge | `--outlier-window` | `100` |
| mt5_outright_merge | `--outlier-z` | `8.0` |
| mt5_outright_merge | `--dedupe-datetime` | off |
| mt5_continuous_builder | `--roll-policy` | `volume` |
| mt5_continuous_builder | `--volume-column` | `Vol` |
| mt5_continuous_builder | `--volume-crossover-days` | `2` |
| mt5_continuous_builder | `--calendar-days-before-expiry` | `7` |
| mt5_continuous_builder | `--write-roll-report` | off |
| mt5_qc_validate | `--outlier-window` | `100` |
| mt5_qc_validate | `--outlier-z` | `8.0` |
| mt5_qc_validate | `--write-cleaned` | off |
| mt5_qc_validate | `--clean-mode` | `severe` |
