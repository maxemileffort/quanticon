import os
import pandas as pd
from crawler.ufc_data_extractor import extract_fighter_details, extract_fight_history, get_ufc_html_files
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
import numpy as np
import joblib # Import joblib for model persistence

def load_and_process_data(base_directory):
    all_fighter_details = []
    all_fight_histories = []
    
    ufc_html_files = get_ufc_html_files(base_directory)
    print(f"Found {len(ufc_html_files)} UFC fighter detail files for processing.")

    for file_path in ufc_html_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            details = extract_fighter_details(html_content)
            history_df = extract_fight_history(html_content)

            if details:
                all_fighter_details.append(details)
            
            if not history_df.empty:
                # Add fighter name to each fight history entry for merging later
                history_df['Fighter Name'] = details.get('Fighter Name', 'Unknown')
                all_fight_histories.append(history_df)

        except Exception as e:
            print(f"Error processing file {file_path}: {e}")
            continue

    fighters_df = pd.DataFrame(all_fighter_details)
    fights_df = pd.concat(all_fight_histories, ignore_index=True)

    return fighters_df, fights_df

def feature_engineer_regression(fighters_df, fights_df, target_metric='Str 1'):
    # Convert numerical columns to numeric types
    numeric_cols_details = ['Height', 'Weight', 'Reach', 'SLpM', 'Str. Acc.', 'SApM', 'Str. Def', 'TD Avg.', 'TD Acc.', 'TD Def.', 'Sub. Avg.']
    for col in numeric_cols_details:
        if col in fighters_df.columns:
            fighters_df[col] = fighters_df[col].astype(str).str.replace('[^0-9.]', '', regex=True)
            fighters_df[col] = pd.to_numeric(fighters_df[col], errors='coerce')

    numeric_cols_fights = ['Kd 1', 'Kd 2', 'Str 1', 'Str 2', 'Td 1', 'Td 2', 'Sub 1', 'Sub 2', 'Round']
    for col in numeric_cols_fights:
        if col in fights_df.columns:
            fights_df[col] = pd.to_numeric(fights_df[col], errors='coerce')

    # Convert 'DOB' to datetime and calculate age
    fighters_df['DOB'] = pd.to_datetime(fighters_df['DOB'], errors='coerce')
    fighters_df['Age'] = (pd.to_datetime('now') - fighters_df['DOB']).dt.days / 365.25

    # Merge fighter 1 details
    fights_df = pd.merge(fights_df, fighters_df, left_on='Fighter 1', right_on='Fighter Name', how='left', suffixes=('_f1', ''))
    fights_df.rename(columns={'Fighter Name': 'Fighter Name_f1'}, inplace=True)

    # Merge fighter 2 details (opponent)
    fights_df = pd.merge(fights_df, fighters_df, left_on='Fighter 2', right_on='Fighter Name', how='left', suffixes=('', '_f2'))
    fights_df.rename(columns={'Fighter Name': 'Fighter Name_f2'}, inplace=True)

    # Drop rows with missing target variable or key features
    # For predicting Fighter 1's metric, we need Fighter 1's metric and Fighter 2's defense stats
    # Corrected column names to match the merged DataFrame (e.g., 'TD Def.' becomes 'TD Def._f2')
    required_cols = [target_metric, 'Str. Def_f2', 'TD Def._f2'] # Example opponent defense stats
    fights_df.dropna(subset=required_cols, inplace=True)

    # Define features (opponent's defense stats) and target (fighter 1's metric)
    features = [
        'Str. Def_f2', 'TD Def._f2', # Opponent's defense stats (corrected name)
        'SLpM_f1', 'Str. Acc._f1', 'SApM_f1', 'Str. Def_f1', 'TD Avg._f1', 'TD Acc._f1', 'TD Def_f1', 'Sub. Avg._f1', 'Age_f1', # Fighter 1's own stats
        'SLpM_f2', 'Str. Acc._f2', 'SApM_f2', 'TD Avg._f2', 'TD Acc._f2', 'Sub. Avg._f2', 'Age_f2', # Opponent's other stats
    ]
    
    # Ensure all features exist and fill NaNs
    for feature in features:
        if feature not in fights_df.columns:
            fights_df[feature] = np.nan # Add missing features as NaN
        fights_df[feature] = pd.to_numeric(fights_df[feature], errors='coerce').fillna(0) # Convert to numeric and fill NaNs

    X = fights_df[features]
    y = fights_df[target_metric]

    return X, y, fights_df

def train_and_evaluate_regressor(X, y):
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)

    model = LinearRegression()
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)

    print(f"\nMean Squared Error: {mean_squared_error(y_test, y_pred):.2f}")
    print(f"R-squared: {r2_score(y_test, y_pred):.2f}")

    return model

def save_model(model, filename):
    """Saves the trained model to a file."""
    model_dir = 'quanticon/quant_bet/models'
    os.makedirs(model_dir, exist_ok=True)
    filepath = os.path.join(model_dir, filename)
    joblib.dump(model, filepath)
    print(f"Model saved to {filepath}")

if __name__ == '__main__':
    base_dir = 'quanticon/quant_bet/crawler/pages'
    
    fighters_df, fights_df = load_and_process_data(base_dir)
    
    if not fights_df.empty:
        # Example: Predict 'Str 1' (significant strikes for Fighter 1)
        X_str, y_str, processed_fights_df_str = feature_engineer_regression(fighters_df, fights_df, target_metric='Str 1')
        if not X_str.empty and not y_str.empty:
            print("\n--- Predicting Significant Strikes (Str 1) ---")
            model_str = train_and_evaluate_regressor(X_str, y_str)
            save_model(model_str, 'ufc_regressor_str_model.joblib') # Save the trained model
            print("Successfully trained and evaluated the regression model for Significant Strikes.")
        else:
            print("Not enough data after feature engineering for Significant Strikes.")

        # Example: Predict 'Td 1' (takedowns for Fighter 1)
        X_td, y_td, processed_fights_df_td = feature_engineer_regression(fighters_df, fights_df, target_metric='Td 1')
        if not X_td.empty and not y_td.empty:
            print("\n--- Predicting Takedowns (Td 1) ---")
            model_td = train_and_evaluate_regressor(X_td, y_td)
            save_model(model_td, 'ufc_regressor_td_model.joblib') # Save the trained model
            print("Successfully trained and evaluated the regression model for Takedowns.")
        else:
            print("Not enough data after feature engineering for Takedowns.")
    else:
        print("No fight history data extracted to build a predictive model.")
