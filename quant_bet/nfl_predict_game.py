import pandas as pd
import joblib
import os
from bs4 import BeautifulSoup
import argparse # Import argparse for command-line arguments

from crawler.nfl_data_extractor import create_nfl_dataframe, get_team_full_name
from nfl_regressor import MODEL_DIR as REGRESSOR_MODEL_DIR
from nfl_predictor import MODEL_DIR as PREDICTOR_MODEL_DIR
import pandas as pd
import joblib
import os
from datetime import datetime

# Define paths to models
MODEL_PATH_WIN_PREDICTOR = os.path.join(PREDICTOR_MODEL_DIR, "nfl_predictor_win_model.joblib")
MODEL_PATH_TEAM_SCORE = os.path.join(REGRESSOR_MODEL_DIR, "nfl_regressor_team_score_model.joblib")
MODEL_PATH_OPP_SCORE = os.path.join(REGRESSOR_MODEL_DIR, "nfl_regressor_opp_score_model.joblib")
MODEL_PATH_PASS_YDS_OFF = os.path.join(REGRESSOR_MODEL_DIR, "nfl_regressor_pass_yds_off_model.joblib")
MODEL_PATH_RUSH_YDS_OFF = os.path.join(REGRESSOR_MODEL_DIR, "nfl_regressor_rush_yds_off_model.joblib")

def load_nfl_models():
    """
    Loads the trained NFL predictor and regressor models.
    """
    models = {}
    model_paths = {
        'win_predictor': MODEL_PATH_WIN_PREDICTOR,
        'team_score_regressor': MODEL_PATH_TEAM_SCORE,
        'opp_score_regressor': MODEL_PATH_OPP_SCORE,
        'pass_yds_off_regressor': MODEL_PATH_PASS_YDS_OFF,
        'rush_yds_off_regressor': MODEL_PATH_RUSH_YDS_OFF,
    }

    for name, path in model_paths.items():
        if os.path.exists(path):
            models[name] = joblib.load(path)
            print(f"NFL {name.replace('_', ' ').title()} model loaded from {path}")
        else:
            print(f"NFL {name.replace('_', ' ').title()} model not found at {path}")
            models[name] = None
    return models

def get_team_stats_for_prediction(team_abbr, year, current_week, is_home_game, opponent_abbr):
    """
    Generates a DataFrame row for a team's stats for prediction, based on average historical data.
    This is a simplified approach. In a real scenario, you'd use more sophisticated feature engineering
    based on recent performance, opponent strength, etc.
    """
    df = create_nfl_dataframe()
    # print(df.head())
    # print(df.groupby(['team', 'year'])['week'].count())
    # df.to_csv('temp.csv', index=False)
    if df.empty:
        print("No NFL data available to generate prediction features.")
        return pd.DataFrame()

    team_full_name = get_team_full_name(str(team_abbr).lower())
    opponent_full_name = get_team_full_name(str(opponent_abbr).lower())

    # Filter for the specific team and year
    team_df = df[(df['team'] == team_full_name)]
    team_yr_df = team_df.loc[team_df['year'].astype(int) == int(year)]

    if team_yr_df.empty:
        print(f"No historical data found for {team_full_name} in {year}.")
        # Fallback to previous year if no team-specific data
        team_yr_df = team_df[team_df['year'].astype(int) == int(year) - 1]
        if team_yr_df.empty:
            team_df = df # Use all available data if no data for the year
            print(f"Using all available data as fallback for {team_full_name} in {year}.")
        else:
            print(f"Using league average for {team_full_name} in {year}.")
    else:
        team_df = team_yr_df.copy()
    # Calculate average stats for the team (or league average if team data is sparse)
    avg_stats = team_df[[
        'first_down_off', 'yards_off', 'pass_yds_off', 'rush_yds_off', 'to_off',
        'first_down_def', 'yards_def', 'pass_yds_def', 'rush_yds_def', 'to_def'
    ]].mean().to_dict()

    # Create a DataFrame for the current game prediction
    prediction_data = {
        'week': [current_week],
        'month': [datetime.now().month], # Use current month for prediction
        'day_of_week': [datetime.now().weekday()], # Use current day of week
        'is_home_game': [1 if is_home_game else 0],
        'opponent': [opponent_full_name],
    }
    
    # Add average offensive and defensive stats
    for stat, value in avg_stats.items():
        prediction_data[stat] = [value]

    return pd.DataFrame(prediction_data)

def predict_nfl_game_outcome(team1_abbr, team2_abbr, year, week):
    """
    Loads models, fetches and preprocesses data, and makes predictions for a game.
    """
    models = load_nfl_models()

    # Check if all necessary models are loaded
    required_models = ['win_predictor', 'team_score_regressor', 'opp_score_regressor',
                       'pass_yds_off_regressor', 'rush_yds_off_regressor']
    for model_name in required_models:
        if models.get(model_name) is None:
            print(f"Required model '{model_name}' could not be loaded. Cannot make predictions.")
            return

    # Get features for Team 1 (playing at home)
    team1_data = get_team_stats_for_prediction(team1_abbr, year, week, is_home_game=True, opponent_abbr=team2_abbr)
    if team1_data.empty:
        print(f"Could not retrieve sufficient data for {team1_abbr} for prediction.")
        return

    # Get features for Team 2 (playing away)
    team2_data = get_team_stats_for_prediction(team2_abbr, year, week, is_home_game=False, opponent_abbr=team1_abbr)
    if team2_data.empty:
        print(f"Could not retrieve sufficient data for {team2_abbr} for prediction.")
        return

    # The models were trained on a single team's perspective.
    # We need to prepare the input for prediction from Team 1's perspective.
    # The features should be structured as they were during training.
    
    # For simplicity, let's assume we are predicting from team1's perspective.
    # The features for prediction should be the same as defined in nfl_regressor.py and nfl_predictor.py
    features_for_prediction = [
        'week', 'month', 'day_of_week', 'is_home_game',
        'first_down_off', 'yards_off', 'pass_yds_off', 'rush_yds_off', 'to_off',
        'first_down_def', 'yards_def', 'pass_yds_def', 'rush_yds_def', 'to_def',
        'opponent'
    ]

    # Ensure the prediction data has all the required features
    # For now, we'll use team1_data directly, assuming it contains all necessary features
    # and the preprocessor in the pipeline will handle the one-hot encoding for 'opponent'.
    X_predict = team1_data[features_for_prediction]

    # Make predictions
    predicted_win = models['win_predictor'].predict(X_predict)[0]
    predicted_team1_score = models['team_score_regressor'].predict(X_predict)[0]
    predicted_team1_opp_score = models['opp_score_regressor'].predict(X_predict)[0]
    predicted_team1_pass_yds_off = models['pass_yds_off_regressor'].predict(X_predict)[0]
    predicted_team1_rush_yds_off = models['rush_yds_off_regressor'].predict(X_predict)[0]

    print(f"\nPrediction for {get_team_full_name(team1_abbr)} (Home) vs {get_team_full_name(team2_abbr)} (Away) in Week {week}, {year}:")
    print(f"  Predicted Winner: {get_team_full_name(team1_abbr) if predicted_win == 1 else get_team_full_name(team2_abbr)}")
    print(f"  Predicted {get_team_full_name(team1_abbr)} Score: {predicted_team1_score:.2f}")
    print(f"  Predicted {get_team_full_name(team2_abbr)} Score: {predicted_team1_opp_score:.2f}")
    print(f"  Predicted {get_team_full_name(team1_abbr)} Pass Yards: {predicted_team1_pass_yds_off:.2f}")
    print(f"  Predicted {get_team_full_name(team1_abbr)} Rush Yards: {predicted_team1_rush_yds_off:.2f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Predict NFL game outcome and stats.")
    parser.add_argument("team1_abbr", type=str, help="Abbreviation of Team 1 (e.g., KAN for Kansas City Chiefs)")
    parser.add_argument("team2_abbr", type=str, help="Abbreviation of Team 2 (e.g., DEN for Denver Broncos)")
    parser.add_argument("year", type=int, help="Year of the game (e.g., 2025)")
    parser.add_argument("week", type=int, help="Week of the game (e.g., 1)")

    args = parser.parse_args()

    predict_nfl_game_outcome(str(args.team1_abbr).lower()
                             , str(args.team2_abbr).lower()
                             , args.year
                             , args.week)

# team_name_map = {
#         'crd': 'Arizona Cardinals'
#         'az': 'Arizona Cardinals'
# , 'atl': 'Atlanta Falcons'
# , 'rav': 'Baltimore Ravens',
# , 'bal': 'Baltimore Ravens',
#         'buf': 'Buffalo Bills'
# , 'car': 'Carolina Panthers'
# , 'chi': 'Chicago Bears',
#         'cin': 'Cincinnati Bengals'
# , 'cle': 'Cleveland Browns'
# , 'dal': 'Dallas Cowboys',
#         'den': 'Denver Broncos'
# , 'det': 'Detroit Lions'
# , 'gnb': 'Green Bay Packers',
# , 'gb': 'Green Bay Packers',
#         'htx': 'Houston Texans'
# , 'clt': 'Indianapolis Colts'
# , 'ind': 'Indianapolis Colts'
# , 'jax': 'Jacksonville Jaguars',
#         'kan': 'Kansas City Chiefs'
# , 'rai': 'Las Vegas Raiders'
# , 'lv': 'Las Vegas Raiders'
# , 'sdg': 'Los Angeles Chargers',
# , 'lac': 'Los Angeles Chargers',
#         'ram': 'Los Angeles Rams'
#         'lar': 'Los Angeles Rams'
# , 'mia': 'Miami Dolphins'
# , 'min': 'Minnesota Vikings',
#         'nwe': 'New England Patriots'
#         'ne': 'New England Patriots'
# , 'nor': 'New Orleans Saints'
# , 'no': 'New Orleans Saints'
# , 'nyg': 'New York Giants',
#         'nyj': 'New York Jets'
# , 'phi': 'Philadelphia Eagles'
# , 'pit': 'Pittsburgh Steelers',
#         'sfo': 'San Francisco 49ers'
# , 'sea': 'Seattle Seahawks'
# , 'tam': 'Tampa Bay Buccaneers',
#         'oti': 'Tennessee Titans'
#         'ten': 'Tennessee Titans'
# , 'was': 'Washington Commanders'
#     }