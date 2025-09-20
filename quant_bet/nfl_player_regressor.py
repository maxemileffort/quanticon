import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
import joblib
import os
from crawler.nfl_player_data_extractor import create_nfl_player_dataframe
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

# Define paths for saving models
MODEL_DIR = "./models"
MODEL_PATH_PLAYER_RUSH_YDS = os.path.join(MODEL_DIR, "nfl_player_regressor_rush_yds_model.joblib")
MODEL_PATH_PLAYER_REC_YDS = os.path.join(MODEL_DIR, "nfl_player_regressor_rec_yds_model.joblib")
MODEL_PATH_PLAYER_PASS_YDS = os.path.join(MODEL_DIR, "nfl_player_regressor_pass_yds_model.joblib")
MODEL_PATH_PLAYER_TACKLES = os.path.join(MODEL_DIR, "nfl_player_regressor_tackles_model.joblib")
MODEL_PATH_PLAYER_SACKS = os.path.join(MODEL_DIR, "nfl_player_regressor_sacks_model.joblib")

def train_nfl_player_regressor_models():
    """
    Loads NFL player data, preprocesses it, trains Linear Regression models
    for various player stats, and saves the trained models.
    """
    os.makedirs(MODEL_DIR, exist_ok=True)

    df = create_nfl_player_dataframe()

    if df.empty:
        print("No NFL player data available to train models.")
        return

    # Convert 'year' to numeric and handle potential non-numeric values
    df['year'] = pd.to_numeric(df['year'], errors='coerce')
    df = df.dropna(subset=['year']) # Drop rows where year could not be converted

    # Define features and target variables
    # These features are examples and should be refined based on actual player data columns
    features = [
        'year', 'age', 'games', 'games_started', # General player info
        'rushing_att', 'rushing_yds', 'rushing_td', # Rushing stats
        'receiving_rec', 'receiving_yds', 'receiving_td', # Receiving stats
        'passing_cmp', 'passing_att', 'passing_yds', 'passing_td', # Passing stats
        'defense_tackles_solo', 'defense_tackles_assists', 'defense_sacks', # Defensive stats
        'kicking_fgm', 'kicking_fga', 'kicking_xpm', 'kicking_xpa', # Kicking stats
        # 'player_id' # Potentially use player_id as a categorical feature if needed
    ]
    
    # Ensure all required columns exist and handle missing values
    # For player data, many stats might be NaN for players not playing that position
    # We will fill NaNs with 0 for numerical features before training
    for col in features:
        if col not in df.columns:
            print(f"Missing column: {col}. Cannot train models.")
            return
    
    # Drop rows with any missing critical features (e.g., year, age, games played)
    df_filtered = df.dropna(subset=['year', 'age', 'games']).copy()

    if df_filtered.empty:
        print("No sufficient data after filtering for training the player regressor models.")
        return

    # Fill NaN values for statistical features with 0, as a player might not have stats in a category
    stats_features = [
        'rushing_att', 'rushing_yds', 'rushing_td',
        'receiving_rec', 'receiving_yds', 'receiving_td',
        'passing_cmp', 'passing_att', 'passing_yds', 'passing_td',
        'defense_tackles_solo', 'defense_tackles_assists', 'defense_sacks',
        'kicking_fgm', 'kicking_fga', 'kicking_xpm', 'kicking_xpa'
    ]
    for col in stats_features:
        if col in df_filtered.columns:
            df_filtered[col] = df_filtered[col].fillna(0)

    # Calculate sample weights based on recency (more recent years get higher weight)
    df_filtered = df_filtered.sort_values(by='year').reset_index(drop=True)
    min_weight = 0.1
    max_weight = 1.0
    df_filtered['sample_weight'] = min_weight + (df_filtered.index / (len(df_filtered) - 1)) * (max_weight - min_weight)

    # Preprocessing for numerical features
    # All features are treated as numerical for now, assuming proper handling of NaNs (filled with 0)
    numerical_features = features # All defined features are numerical after NaN handling

    preprocessor = ColumnTransformer(
        transformers=[
            ('num', StandardScaler(), numerical_features)
        ])

    # Define targets for player statistics
    targets = {
        'rushing_yds': MODEL_PATH_PLAYER_RUSH_YDS,
        'receiving_yds': MODEL_PATH_PLAYER_REC_YDS,
        'passing_yds': MODEL_PATH_PLAYER_PASS_YDS,
        'defense_tackles_solo': MODEL_PATH_PLAYER_TACKLES,
        'defense_sacks': MODEL_PATH_PLAYER_SACKS
    }

    X = df_filtered[features]

    for target_name, model_path in targets.items():
        if target_name not in df_filtered.columns:
            print(f"Target column '{target_name}' not found in player data. Skipping model training for this target.")
            continue

        y = df_filtered[target_name]
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Split weights as well
        sample_weights = df_filtered['sample_weight']
        w_train, w_test = train_test_split(sample_weights, test_size=0.2, random_state=42)

        model_pipeline = Pipeline(steps=[('preprocessor', preprocessor),
                                       ('regressor', LinearRegression())])
        
        model_pipeline.fit(X_train, y_train, regressor__sample_weight=w_train)
        y_pred = model_pipeline.predict(X_test)

        # Calculate residuals on the training set to estimate model uncertainty
        train_preds = model_pipeline.predict(X_train)
        residuals = y_train - train_preds
        residual_std_dev = residuals.std()

        print(f"\n--- {target_name} Player Regressor ---")
        print("Mean Squared Error:", mean_squared_error(y_test, y_pred))
        print("R2 Score:", r2_score(y_test, y_pred))
        print(f"Residual Standard Deviation (Training): {residual_std_dev:.2f}")
        
        # Save the model pipeline along with its residual standard deviation
        joblib.dump({'model': model_pipeline, 'residual_std_dev': residual_std_dev}, model_path)
        print(f"Model saved to {model_path}")

if __name__ == "__main__":
    train_nfl_player_regressor_models()
