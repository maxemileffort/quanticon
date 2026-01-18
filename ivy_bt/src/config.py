import yaml
from pydantic import BaseModel
from typing import Literal

class BacktestConfig(BaseModel):
    start_date: str
    end_date: str
    interval: str = "1d"
    instrument_type: Literal["forex", "crypto", "spy", "iwm", "xlf", "xlv", "xle", "xlk"]

class DataConfig(BaseModel):
    cache_enabled: bool
    cache_dir: str
    cache_format: Literal["parquet", "sqlite"]
    data_source: Literal["yfinance", "alpaca"] = "yfinance"

class OptimizationConfig(BaseModel):
    metric: Literal["Sharpe", "Return"]
    enable_portfolio_opt: bool
    enable_monte_carlo: bool
    enable_wfo: bool
    enable_plotting: bool
    view_plotting: bool = False

class AlpacaConfig(BaseModel):
    api_key: str = None
    secret_key: str = None
    paper: bool = True

class AppConfig(BaseModel):
    backtest: BacktestConfig
    data: DataConfig
    optimization: OptimizationConfig
    alpaca: AlpacaConfig = AlpacaConfig()

def load_config(config_path: str = "config.yaml") -> AppConfig:
    with open(config_path, "r") as f:
        config_dict = yaml.safe_load(f)
    return AppConfig(**config_dict)
