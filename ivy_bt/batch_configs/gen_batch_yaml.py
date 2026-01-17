import sys
import os

# Add parent directory to path to allow imports from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from src.strategies import get_all_strategies
import itertools

today = datetime.today()
today_str = today.strftime('%Y%m%d%H%M%S')
this_month_str = today.strftime('%Y-%m') + '-01'

strats = get_all_strategies()
ecos = ['forex', 'crypto', 'spy', 'etf']

print(strats)

def gen_header_text(today_str, max_workers=4):
  
  template = f"""
  max_workers: {max_workers}
  output_file: "C:\\Users\\Max\\Desktop\\projects\\quanticon\\ivy_bt\\batch_results\\batch_results_ema_{today_str}.csv"
  jobs:
  """
  return template

def gen_job_text(today_str, this_month_str, combo, max_workers=4):
  strat = combo[0]
  eco = combo[1]
  combo_str = strat + eco
  template = f"""
  
  jobs:
    - job_id: "{combo_str}"
      strategy_name: "{strat}"
      instrument_type: "{eco}"
      start_date: "2020-01-01"
      end_date: "{this_month_str}"
      metric: "Sharpe"
      enable_plotting: true

  """

header = gen_header_text(today_str)
for combo in itertools.product(strats, ecos):
    print(combo)
    inner_text = gen_job_text(combo, max_workers=4)
