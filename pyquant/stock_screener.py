# Python Stock Screener

from openbb import obb
from openbb_finviz.utils.screener_helper import get_preset_choices
import pandas as pd
from datetime import datetime
import os

def get_data(preset):
    
    finviz_metrics = { # each value is a set of columns to drop
    'valuation':['market_cap', 'price', 'change_percent'], 
    'financial':['market_cap', 'price', 'change_percent', 'volume'], 
    'ownership':['market_cap', 'price', 'change_percent', 'volume'], 
    'performance':['price', 'change_percent', 'volume', 'volume_avg'], 
    'technical':['price', 'change_percent', 'volume'], 
    'overview':['volume', 'price_to_earnings']
    }

    final_df = pd.DataFrame(columns=['symbol'])

    for metric in finviz_metrics.keys():
        # metric = 'overview'
        print(metric)

        df = (obb.equity.screener(provider='finviz', 
                                # limit=500, 
                                metric = metric, 
                                preset=preset)
                        .to_df())
        # print(df.head())
        # for c in df.columns:
        #     print(c)
        df = df.drop(columns=finviz_metrics[metric])

        # print(df.head())

        final_df = final_df.merge(df, 'outer', left_on='symbol', right_on='symbol')

        print('=================')

    # print(final_df.head())

    # output_file_name = f'{datetime.today().strftime("%Y-%m-%d")}_{preset}.csv'
    # output_file_path = os.path.join('outputs', output_file_name)
    # final_df.to_csv(output_file_path, sep='|', index=False)

    return final_df

# Stock screening with FinViz
user_data_path = r"C:\Users\maxw2\OpenBBUserData"
presets = get_preset_choices(user_data_path)
# presets = presets + ['top_gainers']
target_presets = [k for k in presets.keys() if 'qtr' in k or 'month_' in k]

print(', '.join(target_presets))

df1 = get_data(target_presets[0])
df2 = get_data(target_presets[1])
df3 = get_data(target_presets[2])
df4 = get_data(target_presets[3])
output_df = pd.concat([df1, df2, df3, df4])

drop_cols = [c for c in output_df.columns if c.endswith('_y')]
rename_cols = {c:c.replace('_x', '') for c in output_df.columns}

output_df = output_df.drop(columns=drop_cols)
output_df = output_df.rename(columns=rename_cols)

# output_df2 = output_df.loc[(output_df['country']=='USA')]

# if len(output_df2) > 5:
#     output_df = output_df2.copy()

print(output_df.head())

output_file_name = f'{datetime.today().strftime("%Y-%m-%d")}_qdqu&mdmu.csv'
output_file_path = os.path.join('outputs', output_file_name)
output_df.to_csv(output_file_path, sep='|', index=False)