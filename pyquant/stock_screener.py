# Python Stock Screener

from openbb import obb
from openbb_finviz.utils.screener_helper import get_preset_choices
from openbb_core.provider.utils.errors import EmptyDataError
import pandas as pd
from datetime import datetime
import os
import time

today_str = datetime.today().strftime("%Y-%m-%d")

os.makedirs(f'outputs/{today_str}', exist_ok=True)

def get_data(preset):
    
    finviz_metrics = { # each value is a set of columns to drop
    'valuation':['market_cap'], 
    # 'financial':['market_cap', 'price', 'change_percent', 'volume'], 
    # 'ownership':['market_cap', 'price', 'change_percent', 'volume'], 
    # 'performance':['price', 'change_percent', 'volume', 'volume_avg'], 
    # 'technical':['price', 'change_percent', 'volume'], 
    # 'overview':['volume', 'price_to_earnings']
    }

    final_df = pd.DataFrame(columns=['symbol'])

    for metric in finviz_metrics.keys():
        # metric = 'overview'
        print(metric)

        try:
            df = (obb.equity.screener(provider='finviz', 
                                    # limit=500, 
                                    metric = metric, 
                                    preset=preset)
                            .to_df())
        except EmptyDataError as e:
            print(e)
            continue
        # print(df.head())
        # for c in df.columns:
        #     print(c)
        df = df.drop(columns=finviz_metrics[metric])

        # print(df.head())

        final_df = final_df.merge(df, 'outer', left_on='symbol', right_on='symbol')

        print('=================')
        time.sleep(5)

    return final_df

# Stock screening with FinViz
user_data_path = r"C:\Users\Max\OpenBBUserData"
presets = get_preset_choices(user_data_path)
# presets = presets + ['top_gainers']
target_presets = [k for k in presets.keys() if 'qtr' in k or 'month_' in k or 'half_' in k]
print(target_presets)

if not target_presets:
    print("No target presets found with 'qtr' or 'month_'. Using default presets.")
    target_presets = ['most_active', 'most_gainer', 'most_loser', 'new_high']

print(', '.join(target_presets))

# Ensure there are at least 6 presets for the following calls
if len(target_presets) < 6:
    print("Warning: Less than 6 target presets available. Appending defaults to reach 4.")
    default_fillers = ['most_active', 'most_gainer', 'most_loser', 'new_high']
    for filler in default_fillers:
        if len(target_presets) >= 6:
            break
        if filler not in target_presets:
            target_presets.append(filler)

dfs = [get_data(tp) for tp in target_presets]

output_df = pd.concat(dfs)
output_df = output_df.reset_index(drop=True)

drop_cols = [c for c in output_df.columns if c.endswith('_y')]
rename_cols = {c:c.replace('_x', '') for c in output_df.columns}

output_df = output_df.drop(columns=drop_cols)
output_df = output_df.rename(columns=rename_cols)

f1 = output_df['price'].fillna('100.0').astype(float)<=100.0
f2 = output_df['price'].fillna('100.0').astype(float)>=10.0

output_df = output_df.loc[f1&f2]

print(output_df.head())

output_file_name = f'{today_str}_qdqu&mdmu.csv'
output_file_path = os.path.join('outputs', today_str, output_file_name)
output_df.to_csv(output_file_path, sep='|', index=False)
