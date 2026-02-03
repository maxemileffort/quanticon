import json
import os
from typing import Any, Dict, List, Optional, Tuple

import requests

import config


class ExecutionAdapter:
    """Base class for publishing signals to a destination."""

    def publish(self, payload: Dict[str, Any], output_path: str) -> None:
        raise NotImplementedError("publish must be implemented by subclasses")


class JsonAdapter(ExecutionAdapter):
    """Writes signals to JSON files (current production mode)."""

    def publish(self, payload: Dict[str, Any], output_path: str) -> None:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, default=str)


class DxTradeAdapter(ExecutionAdapter):
    """DX Trade REST adapter that converts signal payloads into orders."""

    def __init__(self, session: Optional[requests.Session] = None, dry_run: Optional[bool] = None) -> None:
        self.session = session or requests.Session()
        self.dry_run = config.DX_DRY_RUN if dry_run is None else dry_run
        self._instrument_cache: Dict[str, Any] = {}
        self._position_cache: Dict[str, Any] = {}

    def publish(self, payload: Dict[str, Any], output_path: str) -> None:
        results: List[Dict[str, Any]] = []
        signals = payload.get("signals", [])
        self._instrument_cache = self._fetch_instruments()
        self._position_cache = self._fetch_positions()

        for signal in signals:
            action_plan = self._build_action_plan(signal)
            if not action_plan:
                continue
            for order in action_plan:
                response = self._submit_order(order)
                results.append({"order": order, "response": response})

        audit_path = self._resolve_audit_path(output_path)
        os.makedirs(os.path.dirname(audit_path), exist_ok=True)
        with open(audit_path, "w", encoding="utf-8") as handle:
            json.dump({"payload": payload, "orders": results}, handle, indent=2, default=str)

    def _auth_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if config.DX_API_KEY:
            headers[config.DX_AUTH_HEADER] = f"{config.DX_AUTH_SCHEME} {config.DX_API_KEY}".strip()
        return headers

    def _request(self, method: str, endpoint: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{config.DX_BASE_URL.rstrip('/')}{endpoint}"
        if self.dry_run:
            return {"dry_run": True, "method": method, "url": url, "payload": payload}
        response = self.session.request(method, url, headers=self._auth_headers(), json=payload, timeout=30)
        response.raise_for_status()
        return response.json()

    def _fetch_instruments(self) -> Dict[str, Any]:
        if not config.DX_INSTRUMENTS_ENDPOINT:
            return {}
        try:
            response = self._request("GET", config.DX_INSTRUMENTS_ENDPOINT)
        except Exception:
            return {}
        instruments: Dict[str, Any] = {}
        data = response if isinstance(response, list) else response.get("data", [])
        for item in data:
            symbol = item.get(config.DX_INSTRUMENT_SYMBOL_FIELD)
            if symbol:
                instruments[str(symbol)] = item
        return instruments

    def _fetch_positions(self) -> Dict[str, Any]:
        if not config.DX_POSITIONS_ENDPOINT:
            return {}
        try:
            response = self._request("GET", config.DX_POSITIONS_ENDPOINT)
        except Exception:
            return {}
        positions: Dict[str, Any] = {}
        data = response if isinstance(response, list) else response.get("data", [])
        for item in data:
            symbol = item.get(config.DX_POSITION_SYMBOL_FIELD)
            if symbol:
                positions[str(symbol)] = item
        return positions

    def _resolve_audit_path(self, output_path: str) -> str:
        base, ext = os.path.splitext(output_path)
        return f"{base}_dxtrade{ext or '.json'}"

    def _map_symbol(self, symbol: str) -> str:
        return config.DX_SYMBOL_MAP.get(symbol, symbol)

    def _instrument_id(self, symbol: str) -> Optional[str]:
        mapped = self._map_symbol(symbol)
        if mapped in self._instrument_cache:
            return str(self._instrument_cache[mapped].get(config.DX_INSTRUMENT_ID_FIELD))
        return None

    def _get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        mapped = self._map_symbol(symbol)
        return self._position_cache.get(mapped)

    def _calc_quantity(self, price: float) -> float:
        if config.DX_POSITION_SIZING_MODE == "percent_equity":
            if config.DX_EQUITY <= 0:
                return config.DX_DEFAULT_QTY
            notional = config.DX_EQUITY * config.DX_PCT_EQUITY
            return max(notional / max(price, 1e-9), 0.0)
        return config.DX_DEFAULT_QTY

    def _build_action_plan(self, signal: Dict[str, Any]) -> List[Dict[str, Any]]:
        entry = signal.get("entry")
        new_signal = bool(signal.get("new_signal"))
        symbol = signal.get("symbol")
        if not symbol:
            return []

        instrument_id = self._instrument_id(symbol)
        if not instrument_id:
            return []

        position = self._get_position(symbol)
        position_side, position_qty = self._parse_position(position)

        if entry == "Flat":
            if position_qty > 0:
                return [self._build_order(instrument_id, "SELL", position_qty, reduce_only=True)]
            if position_qty < 0:
                return [self._build_order(instrument_id, "BUY", abs(position_qty), reduce_only=True)]
            return []

        if not new_signal:
            return []

        desired_side = "BUY" if entry == "Long" else "SELL"
        orders: List[Dict[str, Any]] = []
        if position_qty != 0:
            if (position_qty > 0 and desired_side == "SELL") or (position_qty < 0 and desired_side == "BUY"):
                orders.append(self._build_order(instrument_id, "SELL" if position_qty > 0 else "BUY", abs(position_qty), reduce_only=True))

        price = float(signal.get("price_open", 0.0) or 0.0)
        qty = self._calc_quantity(price)
        if qty > 0:
            orders.append(self._build_order(instrument_id, desired_side, qty, reduce_only=False))
        return orders

    def _parse_position(self, position: Optional[Dict[str, Any]]) -> Tuple[float, float]:
        if not position:
            return "", 0.0
        side = position.get(config.DX_POSITION_SIDE_FIELD, "")
        qty = position.get(config.DX_POSITION_QTY_FIELD, 0.0)
        try:
            qty_val = float(qty)
        except (TypeError, ValueError):
            qty_val = 0.0
        if str(side).lower() in {"short", "sell"}:
            qty_val = -abs(qty_val)
        return side, qty_val

    def _build_order(self, instrument_id: str, side: str, qty: float, reduce_only: bool) -> Dict[str, Any]:
        return {
            config.DX_FIELD_ACCOUNT: config.DX_ACCOUNT_ID,
            config.DX_FIELD_INSTRUMENT: instrument_id,
            config.DX_FIELD_SIDE: side,
            config.DX_FIELD_QTY: qty,
            config.DX_FIELD_ORDER_TYPE: config.DX_ORDER_TYPE,
            config.DX_FIELD_TIF: config.DX_TIME_IN_FORCE,
            config.DX_FIELD_REDUCE_ONLY: reduce_only,
        }

    def _submit_order(self, order: Dict[str, Any]) -> Any:
        try:
            return self._request("POST", config.DX_ORDER_ENDPOINT, payload=order)
        except Exception as exc:
            return {"error": str(exc), "order": order}
