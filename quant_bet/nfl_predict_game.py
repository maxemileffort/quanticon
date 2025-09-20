import pandas as pd
import joblib
import os
import argparse
import numpy as np # Import numpy for numerical operations and random sampling

from crawler.nfl_data_extractor import create_nfl_dataframe, get_team_full_name
from nfl_regressor import MODEL_DIR as REGRESSOR_MODEL_DIR
from nfl_predictor import MODEL_DIR as PREDICTOR_MODEL_DIR
from datetime import datetime, timedelta

# Define paths to models
MODEL_PATH_WIN_PREDICTOR = os.path.join(PREDICTOR_MODEL_DIR, "nfl_predictor_win_model.joblib")
MODEL_PATH_TEAM_SCORE = os.path.join(REGRESSOR_MODEL_DIR, "nfl_regressor_team_score_model.joblib")
MODEL_PATH_OPP_SCORE = os.path.join(REGRESSOR_MODEL_DIR, "nfl_regressor_opp_score_model.joblib")
MODEL_PATH_PASS_YDS_OFF = os.path.join(REGRESSOR_MODEL_DIR, "nfl_regressor_pass_yds_off_model.joblib")
MODEL_PATH_RUSH_YDS_OFF = os.path.join(REGRESSOR_MODEL_DIR, "nfl_regressor_rush_yds_off_model.joblib")

def load_nfl_models():
    """
    Loads the trained NFL predictor and regressor models.
    This function loads the original models without residual standard deviations.
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
            # For regressors, the saved object is now a dictionary
            if 'regressor' in name:
                loaded_obj = joblib.load(path)
                models[name] = loaded_obj['model'] # Load only the model pipeline
            else:
                models[name] = joblib.load(path)
            print(f"NFL {name.replace('_', ' ').title()} model loaded from {path}")
        else:
            print(f"NFL {name.replace('_', ' ').title()} model not found at {path}")
            models[name] = None
    return models

def load_nfl_models_enhanced():
    """
    Loads the trained NFL predictor and regressor models, including residual standard deviations
    for regressors.
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
            if 'regressor' in name:
                loaded_obj = joblib.load(path)
                models[name] = loaded_obj['model']
                models[f"{name}_std_dev"] = loaded_obj['residual_std_dev']
            else:
                models[name] = joblib.load(path)
            print(f"NFL {name.replace('_', ' ').title()} model loaded from {path}")
        else:
            print(f"NFL {name.replace('_', ' ').title()} model not found at {path}")
            models[name] = None
    return models

def find_nfl_dataframe():
    file_path = './dataframes/nfl_temp.csv'
    five_days_ago = datetime.now() - timedelta(days=5)

    if os.path.isfile(file_path):
        file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
        if file_mod_time > five_days_ago:
            try:
                df = pd.read_csv(file_path)
                print(f"Loaded NFL data from {file_path} (less than 5 days old).")
                return df
            except Exception as e:
                print(f"Error reading existing NFL data file: {e}. Creating new dataframe.")
        else:
            print(f"NFL data file is older than 5 days. Creating new dataframe.")
    else:
        print(f"NFL data file not found at {file_path}. Creating new dataframe.")
    
    df = create_nfl_dataframe()
    # Ensure the directory exists before saving
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    df.to_csv(file_path, index=False)
    print(f"New NFL data dataframe created and saved to {file_path}.")
    return df

def get_team_stats_for_prediction(team_abbr, year, current_week, is_home_game, opponent_abbr):
    """
    Generates a DataFrame row for a team's stats for prediction, based on average historical data.
    This is a simplified approach. In a real scenario, you'd use more sophisticated feature engineering
    based on recent performance, opponent strength, etc.
    """
    df = find_nfl_dataframe()
    # print(df.head())
    # print(df.groupby(['team', 'year'])['week'].count())
    # df.to_csv('./dataframes/nfl_temp.csv', index=False)
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
    X_predict2 = team2_data[features_for_prediction]

    # Make predictions
    predicted_win = models['win_predictor'].predict(X_predict)[0]
    predicted_team1_score = models['team_score_regressor'].predict(X_predict)[0]
    predicted_team1_opp_score = models['opp_score_regressor'].predict(X_predict)[0]
    predicted_team1_pass_yds_off = models['pass_yds_off_regressor'].predict(X_predict)[0]
    predicted_team1_rush_yds_off = models['rush_yds_off_regressor'].predict(X_predict)[0]
    predicted_team2_pass_yds_off = models['pass_yds_off_regressor'].predict(X_predict2)[0]
    predicted_team2_rush_yds_off = models['rush_yds_off_regressor'].predict(X_predict2)[0]

    pred_text = f"\nPrediction for {get_team_full_name(team1_abbr)} (Home) vs {get_team_full_name(team2_abbr)} (Away) in Week {week}, {year}:"
    pred_text += f"\nPredicted Winner: {get_team_full_name(team1_abbr) if predicted_win == 1 else get_team_full_name(team2_abbr)}"
    pred_text += f"\nPredicted {get_team_full_name(team1_abbr)} Score: {predicted_team1_score:.2f}"
    pred_text += f"\nPredicted {get_team_full_name(team2_abbr)} Score: {predicted_team1_opp_score:.2f}"
    pred_text += f"\nPredicted {get_team_full_name(team1_abbr)} Pass Yards: {predicted_team1_pass_yds_off:.2f}"
    pred_text += f"\nPredicted {get_team_full_name(team1_abbr)} Rush Yards: {predicted_team1_rush_yds_off:.2f}"
    pred_text += f"\nPredicted {get_team_full_name(team2_abbr)} Pass Yards: {predicted_team2_pass_yds_off:.2f}"
    pred_text += f"\nPredicted {get_team_full_name(team2_abbr)} Rush Yards: {predicted_team2_rush_yds_off:.2f}"

    print(pred_text)

    return pred_text

def predict_nfl_game_outcome_enhanced(team1_abbr, team2_abbr, year, week, num_simulations=1000):
    """
    Loads enhanced models, fetches and preprocesses data, and performs Monte Carlo simulations
    to predict a range of outcomes for a game.
    """
    models = load_nfl_models_enhanced()

    required_models = ['win_predictor', 'team_score_regressor', 'opp_score_regressor',
                       'pass_yds_off_regressor', 'rush_yds_off_regressor']
    for model_name in required_models:
        if models.get(model_name) is None:
            print(f"Required model '{model_name}' could not be loaded. Cannot make enhanced predictions.")
            return

    team1_data = get_team_stats_for_prediction(team1_abbr, year, week, is_home_game=True, opponent_abbr=team2_abbr)
    if team1_data.empty:
        print(f"Could not retrieve sufficient data for {team1_abbr} for enhanced prediction.")
        return

    team2_data = get_team_stats_for_prediction(team2_abbr, year, week, is_home_game=False, opponent_abbr=team1_abbr)
    if team2_data.empty:
        print(f"Could not retrieve sufficient data for {team2_abbr} for enhanced prediction.")
        return

    features_for_prediction = [
        'week', 'month', 'day_of_week', 'is_home_game',
        'first_down_off', 'yards_off', 'pass_yds_off', 'rush_yds_off', 'to_off',
        'first_down_def', 'yards_def', 'pass_yds_def', 'rush_yds_def', 'to_def',
        'opponent'
    ]

    X_predict_team1 = team1_data[features_for_prediction]
    X_predict_team2 = team2_data[features_for_prediction]

    # Get win probabilities
    # Access the model pipeline from the dictionary
    win_proba_team1 = models['win_predictor']['model'].predict_proba(X_predict_team1)[0][1] # Probability of Team 1 winning
    win_proba_team2 = models['win_predictor']['model'].predict_proba(X_predict_team2)[0][0] # Probability of Team 2 winning (as home team loss)

    # Store simulation results
    simulated_winners = []
    simulated_team1_scores = []
    simulated_team2_scores = []
    simulated_team1_pass_yds = []
    simulated_team1_rush_yds = []
    simulated_team2_pass_yds = []
    simulated_team2_rush_yds = []

    for _ in range(num_simulations):
        # Simulate winner based on probability
        if np.random.rand() < win_proba_team1:
            simulated_winners.append(get_team_full_name(team1_abbr))
        else:
            simulated_winners.append(get_team_full_name(team2_abbr))

        # Simulate scores and yards using normal distribution with residual std dev
        sim_team1_score = np.random.normal(models['team_score_regressor'].predict(X_predict_team1)[0], models['team_score_regressor_std_dev'])
        sim_team2_score = np.random.normal(models['opp_score_regressor'].predict(X_predict_team1)[0], models['opp_score_regressor_std_dev'])
        sim_team1_pass_yds = np.random.normal(models['pass_yds_off_regressor'].predict(X_predict_team1)[0], models['pass_yds_off_regressor_std_dev'])
        sim_team1_rush_yds = np.random.normal(models['rush_yds_off_regressor'].predict(X_predict_team1)[0], models['rush_yds_off_regressor_std_dev'])
        sim_team2_pass_yds = np.random.normal(models['pass_yds_off_regressor'].predict(X_predict_team2)[0], models['pass_yds_off_regressor_std_dev'])
        sim_team2_rush_yds = np.random.normal(models['rush_yds_off_regressor'].predict(X_predict_team2)[0], models['rush_yds_off_regressor_std_dev'])

        simulated_team1_scores.append(max(0, sim_team1_score)) # Scores can't be negative
        simulated_team2_scores.append(max(0, sim_team2_score))
        simulated_team1_pass_yds.append(max(0, sim_team1_pass_yds))
        simulated_team1_rush_yds.append(max(0, sim_team1_rush_yds))
        simulated_team2_pass_yds.append(max(0, sim_team2_pass_yds))
        simulated_team2_rush_yds.append(max(0, sim_team2_rush_yds))

    # Aggregate results
    team1_win_count = simulated_winners.count(get_team_full_name(team1_abbr))
    team2_win_count = simulated_winners.count(get_team_full_name(team2_abbr))
    
    team1_win_percentage = (team1_win_count / num_simulations) * 100
    team2_win_percentage = (team2_win_count / num_simulations) * 100

    # Calculate percentiles for scores and yards
    percentiles = [25, 50, 75] # Q1, Median, Q3
    team1_score_percentiles = np.percentile(simulated_team1_scores, percentiles)
    team2_score_percentiles = np.percentile(simulated_team2_scores, percentiles)
    team1_pass_yds_percentiles = np.percentile(simulated_team1_pass_yds, percentiles)
    team1_rush_yds_percentiles = np.percentile(simulated_team1_rush_yds, percentiles)
    team2_pass_yds_percentiles = np.percentile(simulated_team2_pass_yds, percentiles)
    team2_rush_yds_percentiles = np.percentile(simulated_team2_rush_yds, percentiles)

    pred_text = f"\nEnhanced Prediction for {get_team_full_name(team1_abbr)} (Home) vs {get_team_full_name(team2_abbr)} (Away) in Week {week}, {year} ({num_simulations} simulations):"
    pred_text += f"\n{get_team_full_name(team1_abbr)} Win Probability: {team1_win_percentage:.2f}%"
    pred_text += f"\n{get_team_full_name(team2_abbr)} Win Probability: {team2_win_percentage:.2f}%"

    pred_text += f"\n\nPredicted {get_team_full_name(team1_abbr)} Score (Q1/Median/Q3): {team1_score_percentiles[0]:.2f}/{team1_score_percentiles[1]:.2f}/{team1_score_percentiles[2]:.2f}"
    pred_text += f"\nPredicted {get_team_full_name(team2_abbr)} Score (Q1/Median/Q3): {team2_score_percentiles[0]:.2f}/{team2_score_percentiles[1]:.2f}/{team2_score_percentiles[2]:.2f}"
    pred_text += f"\nPredicted {get_team_full_name(team1_abbr)} Pass Yards (Q1/Median/Q3): {team1_pass_yds_percentiles[0]:.2f}/{team1_pass_yds_percentiles[1]:.2f}/{team1_pass_yds_percentiles[2]:.2f}"
    pred_text += f"\nPredicted {get_team_full_name(team1_abbr)} Rush Yards (Q1/Median/Q3): {team1_rush_yds_percentiles[0]:.2f}/{team1_rush_yds_percentiles[1]:.2f}/{team1_rush_yds_percentiles[2]:.2f}"
    pred_text += f"\nPredicted {get_team_full_name(team2_abbr)} Pass Yards (Q1/Median/Q3): {team2_pass_yds_percentiles[0]:.2f}/{team2_pass_yds_percentiles[1]:.2f}/{team2_pass_yds_percentiles[2]:.2f}"
    pred_text += f"\nPredicted {get_team_full_name(team2_abbr)} Rush Yards (Q1/Median/Q3): {team2_rush_yds_percentiles[0]:.2f}/{team2_rush_yds_percentiles[1]:.2f}/{team2_rush_yds_percentiles[2]:.2f}"

    print(pred_text)
    return pred_text


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Predict NFL game outcome and stats.")
    parser.add_argument("team1_abbr", type=str, help="Abbreviation of Team 1 (e.g., KAN for Kansas City Chiefs)")
    parser.add_argument("team2_abbr", type=str, help="Abbreviation of Team 2 (e.g., DEN for Denver Broncos)")
    parser.add_argument("year", type=int, help="Year of the game (e.g., 2025)")
    parser.add_argument("week", type=int, help="Week of the game (e.g., 1)")
    parser.add_argument("--enhanced", action="store_true", help="Use enhanced prediction with Monte Carlo simulation.")
    parser.add_argument("--simulations", type=int, default=1000, help="Number of Monte Carlo simulations for enhanced prediction.")


    args = parser.parse_args()

    if args.enhanced:
        predict_nfl_game_outcome_enhanced(str(args.team1_abbr).lower(),
                                          str(args.team2_abbr).lower(),
                                          args.year,
                                          args.week,
                                          args.simulations)
    else:
        predict_nfl_game_outcome(str(args.team1_abbr).lower(),
                                 str(args.team2_abbr).lower(),
                                 args.year,
                                 args.week)
