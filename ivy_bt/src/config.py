import yaml
from pydantic import BaseModel
from typing import Literal

class BacktestConfig(BaseModel):
    start_date: str
    end_date: str
    instrument_type: Literal["forex", "crypto"]

class DataConfig(BaseModel):
    cache_enabled: bool
    cache_dir: str
    cache_format: Literal["parquet", "sqlite"]

class AppConfig(BaseModel):
    backtest: BacktestConfig
    data: DataConfig

def load_config(config_path: str = "config.yaml") -> AppConfig:
    with open(config_path, "r") as f:
        config_dict = yaml.safe_load(f)
    return AppConfig(**config_dict)
