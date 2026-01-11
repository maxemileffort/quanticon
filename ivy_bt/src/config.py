import yaml
from pydantic import BaseModel
from typing import Literal

class BacktestConfig(BaseModel):
    start_date: str
    end_date: str
    instrument_type: Literal["forex", "crypto", "spy", "iwm", "xlf", "xlv", "xle", "xlk"]

class DataConfig(BaseModel):
    cache_enabled: bool
    cache_dir: str
    cache_format: Literal["parquet", "sqlite"]

class OptimizationConfig(BaseModel):
    metric: Literal["Sharpe", "Return"]
    enable_portfolio_opt: bool
    enable_monte_carlo: bool
    enable_wfo: bool
    enable_plotting: bool

class AppConfig(BaseModel):
    backtest: BacktestConfig
    data: DataConfig
    optimization: OptimizationConfig

def load_config(config_path: str = "config.yaml") -> AppConfig:
    with open(config_path, "r") as f:
        config_dict = yaml.safe_load(f)
    return AppConfig(**config_dict)
