# MTF HMM Physics Runner

This folder contains the batch files and runner script that produce JSON signals for paper trading.

## Quick Start

- **Crypto:** double‑click `run_crypto.bat`
- **Forex:** double‑click `run_forex.bat`

Outputs are written to:

```
quanticon/ivy_bt/outputs/<universe>/signals_YYYYMMDD_HHMM.json
```

Each run also appends to:

```
quanticon/ivy_bt/outputs/<universe>/run_log.csv
```

## How to Read the JSON Output

### File‑level fields
- **run_timestamp**: when the batch ran (UTC)
- **universe**: `crypto` or `forex`
- **symbols**: list of processed tickers
- **signals**: actionable per‑symbol entries for *this run*
- **stats**: backtest risk summary for reference

### Per‑symbol fields (`signals[]`)
Each item is the **current state** at the latest 5‑minute bar:

- **symbol**: ticker (e.g., `EURUSD=X`)
- **timestamp**: timestamp of latest 5m bar
- **entry**: the **position to hold now** (`Long`, `Short`, `Flat`)
- **entry_state**: the most recent **mid‑TF** signal state
- **entry_change_time**: time of the last mid‑TF signal change
- **new_signal**: `true` if a **fresh signal just triggered**
- **price_open**: the **5m open** used for execution
- **dataset**: Train/Test label (reference only)
- **timeframes**: low/mid/high TF mapping

## When to Enter / Exit

### Enter a trade
If **`new_signal == true`**, a fresh mid‑TF signal appeared and should be executed on the **next 5m open**.

Use **`entry`** to determine direction:
- `Long` → open/hold a long
- `Short` → open/hold a short

### Hold a trade
If **`new_signal == false`** and `entry` is **Long/Short**, the model is already in that position.

### Exit a trade
If `entry` flips to **Flat**, exit at the **next 5m open**.

### Flip a trade
If `entry` flips from **Long → Short** or **Short → Long**, exit and re‑enter at the **next 5m open**.

## Next Steps
If you want a broker adapter (Alpaca/Kraken/Darwinex), we can extend `execution_adapters.py`
with a class that converts these signals into API orders.