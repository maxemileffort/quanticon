import json
import os
from typing import Any, Dict


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
