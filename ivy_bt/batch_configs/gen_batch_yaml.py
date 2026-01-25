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

outputs_path = r'C:\Users\Max\Desktop\projects\quanticon\ivy_bt\batch_configs'

for r,d,files in os.walk(outputs_path):
  for f in files:
    pth = os.path.join(r,f)
    if 'archive' in pth:
      continue
    if '.py' in f:
      continue
    # print(pth)
    os.remove(pth)

strats = get_all_strategies()
ecos = [
  # 'forex', 
  'crypto', 
  # 'spy', 
  # 'etf'
  ]

def gen_header_text(combo_strat, today_str, max_workers=4):

  base_path = "C:\\Users\\Max\\Desktop\\projects\\quanticon\\ivy_bt\\batch_results"
  output_file_path = os.path.join(base_path, f"batch_results_{combo_strat}_{today_str}.csv") 
  
  template = f"""max_workers: {max_workers}"""
  template += f"""\noutput_file: '{output_file_path}' """
  template += f"""\njobs:"""
  
  return template

def gen_job_text(combo, this_month_str ):
  strat = combo[0]
  eco = combo[1]
  combo_str = strat + '_' + eco
  template =  f"""\n  - job_id: "{combo_str}" """
  template += f"""\n    strategy_name: "{strat}" """
  template += f"""\n    instrument_type: "{eco}" """
  template += f"""\n    start_date: "2020-01-01" """
  template += f"""\n    end_date: "{this_month_str}" """
  template += f"""\n    metric: "Sharpe" """
  template += f"""\n    enable_plotting: true"""

  return template



combos = [f'{c[0]}_{c[1]}' for c in itertools.product(strats, ecos)]
strat_check = ''
yaml_files = []
for combo in combos:
  combo_strat = combo.split('_')[0]
  if combo_strat == strat_check:
    continue
  if combo_strat.lower() == 'pairstrading': # this needs rework before we can scale the testing on it
    continue
  strat_check = combo_strat

  related_yamls = [c.split('_') for c in combos if combo_strat in c]

  header = gen_header_text(combo_strat, today_str)
  jobs = []
  for ry in related_yamls:
    inner_text = gen_job_text(ry, this_month_str)
    jobs.append(inner_text)

  file_text = header + ''.join(jobs)

  fname = f'{combo_strat}_{today_str}.yaml'
  save_file_dest = os.path.join(outputs_path,fname)

  with open(save_file_dest, 'w') as outfile:
    outfile.write(file_text)

  yaml_files.append(save_file_dest)

  jobs = []

for f in yaml_files:
  print(f"""cd "C:/Users/Max/Desktop/projects/quanticon/ivy_bt" && python main.py --batch "{f.replace('\\', '/')}" """)
