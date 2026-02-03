import json
import os


def _get_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _get_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _get_json(value, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


DX_BASE_URL = os.getenv("DX_BASE_URL", "https://demo.dx.trade")
DX_API_KEY = os.getenv("DX_API_KEY", "")
DX_ACCOUNT_ID = os.getenv("DX_ACCOUNT_ID", "")

# Auth header configuration
DX_AUTH_HEADER = os.getenv("DX_AUTH_HEADER", "Authorization")
DX_AUTH_SCHEME = os.getenv("DX_AUTH_SCHEME", "Bearer")

# Endpoint paths (update to match DX Trade REST docs)
DX_INSTRUMENTS_ENDPOINT = os.getenv("DX_INSTRUMENTS_ENDPOINT", "/dxtrade/instruments")
DX_ORDER_ENDPOINT = os.getenv("DX_ORDER_ENDPOINT", "/dxtrade/orders")
DX_POSITIONS_ENDPOINT = os.getenv("DX_POSITIONS_ENDPOINT", "/dxtrade/positions")

# Instrument metadata fields
DX_INSTRUMENT_SYMBOL_FIELD = os.getenv("DX_INSTRUMENT_SYMBOL_FIELD", "symbol")
DX_INSTRUMENT_ID_FIELD = os.getenv("DX_INSTRUMENT_ID_FIELD", "id")

# Position metadata fields
DX_POSITION_SYMBOL_FIELD = os.getenv("DX_POSITION_SYMBOL_FIELD", "symbol")
DX_POSITION_QTY_FIELD = os.getenv("DX_POSITION_QTY_FIELD", "quantity")
DX_POSITION_SIDE_FIELD = os.getenv("DX_POSITION_SIDE_FIELD", "side")

# Order fields
DX_FIELD_ACCOUNT = os.getenv("DX_FIELD_ACCOUNT", "accountId")
DX_FIELD_INSTRUMENT = os.getenv("DX_FIELD_INSTRUMENT", "instrumentId")
DX_FIELD_SIDE = os.getenv("DX_FIELD_SIDE", "side")
DX_FIELD_QTY = os.getenv("DX_FIELD_QTY", "quantity")
DX_FIELD_ORDER_TYPE = os.getenv("DX_FIELD_ORDER_TYPE", "type")
DX_FIELD_TIF = os.getenv("DX_FIELD_TIF", "timeInForce")
DX_FIELD_REDUCE_ONLY = os.getenv("DX_FIELD_REDUCE_ONLY", "reduceOnly")

DX_ORDER_TYPE = os.getenv("DX_ORDER_TYPE", "MARKET")
DX_TIME_IN_FORCE = os.getenv("DX_TIME_IN_FORCE", "GTC")

# Sizing configuration
DX_POSITION_SIZING_MODE = os.getenv("DX_POSITION_SIZING_MODE", "fixed_qty")
DX_DEFAULT_QTY = _get_float(os.getenv("DX_DEFAULT_QTY", "1"), 1)
DX_PCT_EQUITY = _get_float(os.getenv("DX_PCT_EQUITY", "0.01"), 0.01)
DX_EQUITY = _get_float(os.getenv("DX_EQUITY", ""), 0.0)

# Optional override mapping for symbols (JSON string env or dict literal here)
DX_SYMBOL_MAP = _get_json(os.getenv("DX_SYMBOL_MAP_JSON"), {})

# Dry run flag to prevent live orders
DX_DRY_RUN = _get_bool(os.getenv("DX_DRY_RUN", "false"), default=False)