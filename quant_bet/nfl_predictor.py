import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
import joblib
import os
from crawler.nfl_data_extractor import create_nfl_dataframe
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

# Define paths for saving models
MODEL_DIR = "./models"
MODEL_PATH_WIN_PREDICTOR = os.path.join(MODEL_DIR, "nfl_predictor_win_model.joblib")

def train_nfl_predictor_model():
    """
    Loads NFL game data, preprocesses it, trains a Logistic Regression model,
    and saves the trained model.
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

    # Define the target variable: 1 if home team wins, 0 otherwise
    # Assuming 'game_location' is empty for home games and '@' for away games
    # And 'game_outcome' is 'W' for win, 'L' for loss, 'T' for tie
    df['home_team_win'] = ((df['game_location'] == '') & (df['game_outcome'] == 'W')) | \
                          ((df['game_location'] == '@') & (df['game_outcome'] == 'L'))
    df['home_team_win'] = df['home_team_win'].astype(int)

    # Calculate sample weights based on recency
    # Sort by date to ensure proper weighting
    df_filtered = df_filtered.sort_values(by='date').reset_index(drop=True)
    # Assign higher weights to more recent games.
    # A simple linear weighting: latest game gets weight 1.0, oldest gets a small base weight.
    min_weight = 0.1
    max_weight = 1.0
    df_filtered['sample_weight'] = min_weight + (df_filtered.index / (len(df_filtered) - 1)) * (max_weight - min_weight)
    
    # Define features for prediction
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
    df_filtered = df.dropna(subset=features + ['home_team_win'])

    if df_filtered.empty:
        print("No sufficient data after filtering for training the predictor model.")
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

    X = df_filtered[features]
    y = df_filtered['home_team_win']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    # Split weights as well
    sample_weights = df_filtered['sample_weight']
    w_train, w_test = train_test_split(sample_weights, test_size=0.2, random_state=42, stratify=y)

    model_pipeline = Pipeline(steps=[('preprocessor', preprocessor),
                                   ('classifier', LogisticRegression(random_state=42, solver='liblinear'))])
    
    model_pipeline.fit(X_train, y_train, classifier__sample_weight=w_train)
    y_pred = model_pipeline.predict(X_test)

    print("\n--- Win Predictor Model ---")
    print("Accuracy:", accuracy_score(y_test, y_pred))
    print("Classification Report:\n", classification_report(y_test, y_pred))

    joblib.dump(model_pipeline, MODEL_PATH_WIN_PREDICTOR)
    print(f"Model saved to {MODEL_PATH_WIN_PREDICTOR}")

if __name__ == "__main__":
    train_nfl_predictor_model()
