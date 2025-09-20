
import pandas as pd
import numpy as np
import requests
import os
from dotenv import load_dotenv
import json
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

load_dotenv()

API_KEY = os.getenv('ODDS_API_KEY')
BASE_URL = os.getenv('ODDS_API_BASE_URL')

SEASON = 2025
WEEK = 3

league_index = 1

odds_api_get_sports = f'{BASE_URL}/v4/sports/?apiKey={API_KEY}'

r = requests.get(odds_api_get_sports)

sport_keys = []
for sport in r.json():
    
    print(sport['key'])
    sport_keys.append(sport['key'])

t_sport_keys = [sk for sk in sport_keys if sk.startswith('americanfootball')]
t_sport_keys = [sk for sk in t_sport_keys if 'nfl' in sk or 'ncaaf' in sk]
t_sport_keys = [sk for sk in t_sport_keys if 'winner' not in sk]

odds_api_get_odds = f'{BASE_URL}/v4/sports/{t_sport_keys[league_index]}/odds/?apiKey={API_KEY}&regions=us,us2&markets=h2h,spreads,totals'


r2 = requests.get(odds_api_get_odds)

r2.json()


for card in r2.json():
    print(card)
    print('========================')


today_str = datetime.today().strftime('%Y-%m-%d')

r2_text = json.dumps(r2.json())
odds_data_dir = './odds_data'
os.makedirs(odds_data_dir, exist_ok=True) # Create the directory if it doesn't exist
with open(os.path.join(odds_data_dir, f'{today_str}_{t_sport_keys[league_index]}_odds.txt'),'w') as outfile:
    outfile.write(r2_text)


data = r2.json()


rows = []
for event in data:
    for bookmaker in event["bookmakers"]:
        for market in bookmaker["markets"]:
            market_send = ''
            team_send = ''
            
            for outcome in market["outcomes"]:
                if market["key"] == "h2h":
                    market_send = "h2h"
                    team_send = outcome["name"]
                elif market["key"] in ["totals", "spreads"]:
                    market_send = market["key"]
                    team_send = f'{outcome["name"]} {outcome["point"]}'
                rows.append({
                    "game": f"{event['home_team']} vs {event['away_team']}",
                    "commence_time": event["commence_time"],
                    "bookmaker": bookmaker["title"],
                    "team": team_send,
                    "decimal_odds": outcome["price"],
                    "implied_prob": 1.0 / float(outcome["price"]),
                    "market": market_send,
                })
            

df = pd.DataFrame(rows)
df['commence_time'] = pd.to_datetime(df['commence_time'])
print(df.head(10))


df_old = df.copy()
# current date (UTC) + 8 days
cutoff = pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=4)
df = df.loc[df['commence_time'] <= cutoff].reset_index(drop=True)


# Pivot so teams are rows and bookmakers are columns
for m in df['market'].unique():
    sub_df = df.loc[df['market']==m]
    pivot_df = sub_df.pivot_table(
        index=["game", "team", "market"],
        columns="bookmaker",
        values="implied_prob"
    )

    plt.figure(figsize=(12,16))
    sns.heatmap(pivot_df, annot=True, cmap="coolwarm", fmt=".2f")
    plt.title(f"{t_sport_keys[league_index]} Odds Across Bookmakers")
    plt.ylabel("Game / Team")
    plt.xlabel("Bookmaker")
    # plt.show()



# 2) Fix the earlier bar plotting issue by pivoting (prevents overwrites)
#    -> one grouped bar chart per game, all games automatically
def plot_all_games_grouped(df: pd.DataFrame, value_col: str = "decimal_odds"):
    games = df["game"].unique()
    for game in games:
        sub = df[df["game"] == game].copy()
        # pivot: rows=team, cols=bookmaker
        pivot = sub.pivot_table(index="team", columns="bookmaker", values=value_col, aggfunc="mean")
        # consistent bookmaker order
        bookmakers = list(pivot.columns)
        teams = list(pivot.index)

        # grouped bars: x = bookmakers, 2 bars (or more) per bookmaker, one per team
        x = np.arange(len(bookmakers))
        width = 0.8 / max(2, len(teams))  # spread bars across each bookmaker

        plt.figure(figsize=(10, 6))
        for i, team in enumerate(teams):
            y = pivot.loc[team, bookmakers].values.astype(float)
            plt.bar(x + (i - (len(teams)-1)/2)*width, y, width=width, label=team)

        yl = "Decimal Odds" if value_col == "decimal_odds" else "Implied Probability"
        plt.title(f"Odds across Books — {game}")
        plt.xlabel("Bookmaker")
        plt.ylabel(yl)
        plt.xticks(x, bookmakers, rotation=35, ha="right")
        plt.legend()
        plt.tight_layout()
        # plt.show()

# Example: decimal odds charts for all games
plot_all_games_grouped(df, value_col="decimal_odds")



# Example: implied probabilities (0–1) for all games
plot_all_games_grouped(df, value_col="implied_prob")


# 3) Optional: "best price by team" table (useful for line shopping)
def best_prices(df: pd.DataFrame) -> pd.DataFrame:
    idx = df.groupby(["game", "team"])["decimal_odds"].idxmax()
    best = df.loc[idx, ["game", "team", "decimal_odds", "bookmaker"]].sort_values(["game","team"])
    best = best.rename(columns={"decimal_odds": "best_decimal", "bookmaker": "best_book"})
    return best.reset_index(drop=True)

best_prices(df)



# 4) Optional: quick market snapshot per game (favorite vs underdog, average prices)
def market_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    # average decimal odds per team
    avg = (df.groupby(["game", "team", "market"])["decimal_odds"]
             .mean()
             .rename("avg_decimal")
             .reset_index())
    # favorite/underdog label within each game
    avg["rank"] = avg.groupby(["game", "market"])["avg_decimal"].rank(method="first")
    avg["role"] = avg.groupby(["game", "market"])["avg_decimal"].transform(lambda s: ["favorite" if x==s.min() else "underdog" for x in s])
    return avg.sort_values(["game","role","avg_decimal"]).reset_index(drop=True)

snap = market_snapshot(df)
snap



df = df.merge(snap, left_on=['game', 'team','market'], right_on=['game', 'team', 'market'], how='outer')
df


dk_games = df.loc[df['bookmaker']=='DraftKings', 'game'].unique()
dk_games


target_df = df.loc[df['game'].isin(dk_games)]


df2 = target_df.loc[target_df['rank']==1.0]


plot_all_games_grouped(df2, value_col="implied_prob")


df2.loc[:, 'league'] = t_sport_keys[league_index] # Use .loc to avoid SettingWithCopyWarning
df2.to_csv(os.path.join(odds_data_dir, f'{today_str}_{t_sport_keys[league_index]}.csv'), index=False)


df2.to_clipboard()


r2.headers['X-Requests-Used']


cutoff = pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=2)
df2 = df2.loc[df2['commence_time'] <= cutoff].reset_index(drop=True)
df2.head()


team_abrev_map = {
        'ari': 'Arizona Cardinals'
        , 'atl': 'Atlanta Falcons'
        , 'bal': 'Baltimore Ravens'        
        , 'buf': 'Buffalo Bills'
        , 'car': 'Carolina Panthers'
        , 'chi': 'Chicago Bears'
        , 'cin': 'Cincinnati Bengals'
        , 'cle': 'Cleveland Browns'
        , 'dal': 'Dallas Cowboys'
        , 'den': 'Denver Broncos'
        , 'det': 'Detroit Lions'
        , 'gb': 'Green Bay Packers'
        , 'hou': 'Houston Texans'
        , 'ind': 'Indianapolis Colts'
        , 'jax': 'Jacksonville Jaguars'
        , 'kan': 'Kansas City Chiefs'
        , 'lv': 'Las Vegas Raiders'
        , 'lac': 'Los Angeles Chargers'
        , 'lar': 'Los Angeles Rams'
        , 'mia': 'Miami Dolphins'
        , 'min': 'Minnesota Vikings'
        , 'ne': 'New England Patriots'
        , 'no': 'New Orleans Saints'
        , 'nyg': 'New York Giants'
        , 'nyj': 'New York Jets'
        , 'phi': 'Philadelphia Eagles'
        , 'pit': 'Pittsburgh Steelers'
        , 'sf': 'San Francisco 49ers'
        , 'sea': 'Seattle Seahawks'
        , 'tam': 'Tampa Bay Buccaneers'
        , 'ten': 'Tennessee Titans'
        , 'was': 'Washington Commanders'
    }

rev_team_abrev_map = {v:k for k,v in team_abrev_map.items()}


from nfl_predict_game import predict_nfl_game_outcome, predict_nfl_game_outcome_enhanced


games = []
original_pred_text_list = []
enhanced_pred_text_list = []

# Set this flag to True to use enhanced predictions, False for original
USE_ENHANCED_PREDICTION = True 
NUM_SIMULATIONS = 1000 # Number of simulations for enhanced prediction

for game in df2['game'].unique():
    teams = (game.split(' vs '))
    print(teams)
    team1_abbr = rev_team_abrev_map[teams[0]]
    print(team1_abbr)
    team2_abbr = rev_team_abrev_map[teams[1]]
    print(team2_abbr)

    games.append(game) 
    
    if USE_ENHANCED_PREDICTION:
        # Call enhanced prediction for Team 1 as home, Team 2 as away
        enhanced_pred1 = predict_nfl_game_outcome_enhanced(team1_abbr, team2_abbr, SEASON, WEEK, NUM_SIMULATIONS)
        enhanced_pred_text_list.append(enhanced_pred1)
        
        # Call enhanced prediction for Team 2 as home, Team 1 as away (for completeness, though usually one perspective is enough for simulation)
        enhanced_pred2 = predict_nfl_game_outcome_enhanced(team2_abbr, team1_abbr, SEASON, WEEK, NUM_SIMULATIONS)
        enhanced_pred_text_list.append(enhanced_pred2)
    else:
        # Original prediction for Team 1 as home, Team 2 as away
        original_pred1 = predict_nfl_game_outcome(team1_abbr, team2_abbr, SEASON, WEEK)
        original_pred_text_list.append(original_pred1)
        
        # Original prediction for Team 2 as home, Team 1 as away
        original_pred2 = predict_nfl_game_outcome(team2_abbr, team1_abbr, SEASON, WEEK)
        original_pred_text_list.append(original_pred2)


nfl_pred_outputs_dir = './nfl_pred_outs'
os.makedirs(nfl_pred_outputs_dir, exist_ok=True)

if USE_ENHANCED_PREDICTION:
    nfl_pred_outputs_path = os.path.join(nfl_pred_outputs_dir, f'{today_str}_nfl_preds_enhanced.txt')
    with open(nfl_pred_outputs_path, 'w') as outfile:
        for i, game in enumerate(games):
            outfile.write(f"Game: {game}\n")
            outfile.write(enhanced_pred_text_list[i*2] + '\n') # Team 1 home perspective
            outfile.write(enhanced_pred_text_list[i*2 + 1] + '\n') # Team 2 home perspective
            outfile.write('==============\n\n')
    print(f"Enhanced NFL predictions saved to {nfl_pred_outputs_path}")
else:
    nfl_pred_outputs_path = os.path.join(nfl_pred_outputs_dir, f'{today_str}_nfl_preds_original.txt')
    with open(nfl_pred_outputs_path, 'w') as outfile:
        for i, game in enumerate(games):
            outfile.write(f"Game: {game}\n")
            outfile.write(original_pred_text_list[i*2] + '\n') # Team 1 home perspective
            outfile.write(original_pred_text_list[i*2 + 1] + '\n') # Team 2 home perspective
            outfile.write('==============\n\n')
    print(f"Original NFL predictions saved to {nfl_pred_outputs_path}")
