import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
import joblib
import os
from crawler.nfl_data_extractor import create_nfl_dataframe
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

# Define paths for saving models
MODEL_DIR = "quanticon/quant_bet/models"
MODEL_PATH_TEAM_SCORE = os.path.join(MODEL_DIR, "nfl_regressor_team_score_model.joblib")
MODEL_PATH_OPP_SCORE = os.path.join(MODEL_DIR, "nfl_regressor_opp_score_model.joblib")
MODEL_PATH_PASS_YDS_OFF = os.path.join(MODEL_DIR, "nfl_regressor_pass_yds_off_model.joblib")
MODEL_PATH_RUSH_YDS_OFF = os.path.join(MODEL_DIR, "nfl_regressor_rush_yds_off_model.joblib")

def train_nfl_regressor_models():
    """
    Loads NFL game data, preprocesses it, trains Linear Regression models
    for various stats, and saves the trained models.
    """
    os.makedirs(MODEL_DIR, exist_ok=True)

    df = create_nfl_dataframe()

    if df.empty:
        print("No NFL data available to train models.")
        return

    # Convert 'date' to datetime and extract relevant features
    df['date'] = pd.to_datetime(df['date'] + ', ' + df['year'].astype(str))
    df['month'] = df['date'].dt.month
    df['day_of_week'] = df['date'].dt.dayofweek
    df['is_home_game'] = df['game_location'].apply(lambda x: 1 if x == '' else 0) # '' means home game on pro-football-reference

    # Define features and target variables
    features = [
        'week', 'month', 'day_of_week', 'is_home_game',
        'first_down_off', 'yards_off', 'pass_yds_off', 'rush_yds_off', 'to_off',
        'first_down_def', 'yards_def', 'pass_yds_def', 'rush_yds_def', 'to_def',
        'opponent' # Categorical feature
    ]
    
    # Ensure all required columns exist and handle missing values
    for col in features:
        if col not in df.columns:
            print(f"Missing column: {col}. Cannot train models.")
            return
    
    # Drop rows with any missing target values or critical features
    df_filtered = df.dropna(subset=features + ['team_score', 'opponent_score'])

    if df_filtered.empty:
        print("No sufficient data after filtering for training the regressor models.")
        return

    # Preprocessing for numerical and categorical features
    numerical_features = [
        'week', 'month', 'day_of_week', 'is_home_game',
        'first_down_off', 'yards_off', 'pass_yds_off', 'rush_yds_off', 'to_off',
        'first_down_def', 'yards_def', 'pass_yds_def', 'rush_yds_def', 'to_def'
    ]
    categorical_features = ['opponent']

    preprocessor = ColumnTransformer(
        transformers=[
            ('num', StandardScaler(), numerical_features),
            ('cat', OneHotEncoder(handle_unknown='ignore'), categorical_features)
        ])

    # Create a pipeline for each target
    targets = {
        'team_score': MODEL_PATH_TEAM_SCORE,
        'opponent_score': MODEL_PATH_OPP_SCORE,
        'pass_yds_off': MODEL_PATH_PASS_YDS_OFF,
        'rush_yds_off': MODEL_PATH_RUSH_YDS_OFF
    }

    X = df_filtered[features]

    for target_name, model_path in targets.items():
        y = df_filtered[target_name]
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        model_pipeline = Pipeline(steps=[('preprocessor', preprocessor),
                                       ('regressor', LinearRegression())])
        
        model_pipeline.fit(X_train, y_train)
        y_pred = model_pipeline.predict(X_test)

        print(f"\n--- {target_name} Regressor ---")
        print("Mean Squared Error:", mean_squared_error(y_test, y_pred))
        print("R2 Score:", r2_score(y_test, y_pred))
        joblib.dump(model_pipeline, model_path)
        print(f"Model saved to {model_path}")

if __name__ == "__main__":
    train_nfl_regressor_models()
