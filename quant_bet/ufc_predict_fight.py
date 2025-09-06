import os
import pandas as pd
import joblib
from datetime import datetime
from crawler.ufc_data_extractor import extract_fighter_details, get_ufc_html_files
from ufc_predictor import feature_engineer as feature_engineer_predictor
from ufc_regressor import feature_engineer_regression

# Define paths for models and data
MODEL_DIR = 'quanticon/quant_bet/models'
PAGES_DIR = 'quanticon/quant_bet/crawler/pages'

def load_models():
    """Loads the trained classification and regression models."""
    predictor_model_path = os.path.join(MODEL_DIR, 'ufc_predictor_model.joblib')
    regressor_str_model_path = os.path.join(MODEL_DIR, 'ufc_regressor_str_model.joblib')
    regressor_td_model_path = os.path.join(MODEL_DIR, 'ufc_regressor_td_model.joblib')

    predictor_model = joblib.load(predictor_model_path)
    regressor_str_model = joblib.load(regressor_str_model_path)
    regressor_td_model = joblib.load(regressor_td_model_path)
    
    return predictor_model, regressor_str_model, regressor_td_model

def get_fighter_data(fighter_name):
    """
    Extracts details for a specific fighter from the HTML files.
    This function assumes fighter HTML files are named in a discoverable way,
    e.g., 'islam-makhachev.html'.
    """
    # Use os.walk to search for fighter data across all subdirectories
    for root, _, files in os.walk(PAGES_DIR):
        for file in files:
            # Only process UFC fighter detail HTML files
            if file.startswith('ufcstats.com--fighter-details') and file.endswith('.html'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                    details = extract_fighter_details(html_content)
                    # Debugging: print extracted fighter name
                    # if details:
                    #     print(f"File: {file_path}, Extracted Name: {details.get('Fighter Name')}")
                    if details and details.get('Fighter Name', '').lower() == fighter_name.lower():
                        return details
                except Exception as e:
                    # Print error only for files that are expected to be UFC fighter details
                    print(f"Error processing UFC fighter file {file_path}: {e}")
                    continue
    return None

def preprocess_fighter_data_for_prediction(fighter1_details, fighter2_details, model_type='predictor'):
    """
    Preprocesses fighter details into a format suitable for prediction.
    This function needs to mimic the feature engineering steps from the training scripts.
    """
    if not fighter1_details or not fighter2_details:
        return None

    # Create a dummy fights_df for feature engineering.
    # The actual fight history is not available for a future fight,
    # so we'll use the fighter details to construct a single row.
    
    # Combine details into a single DataFrame row
    combined_data = {**{f"{k}_f1": v for k, v in fighter1_details.items()},
                     **{f"{k}_f2": v for k, v in fighter2_details.items()}}
    
    # Manually add 'Fighter 1' and 'Fighter 2' for merging logic in feature_engineer
    combined_data['Fighter 1'] = fighter1_details.get('Fighter Name')
    combined_data['Fighter 2'] = fighter2_details.get('Fighter Name')
    
    # Add dummy fight-specific stats that are expected by feature_engineer
    # These will be filled with 0 or NaN as they are unknown for a future fight
    for col in ['Kd 1', 'Kd 2', 'Str 1', 'Str 2', 'Td 1', 'Td 2', 'Sub 1', 'Sub 2', 'Round', 'W/L']:
        if col not in combined_data:
            combined_data[col] = np.nan

    dummy_fights_df = pd.DataFrame([combined_data])
    
    # Create a dummy fighters_df for merging
    dummy_fighters_df = pd.DataFrame([fighter1_details, fighter2_details])
    
    # Apply the same preprocessing steps as in the training scripts
    if model_type == 'predictor':
        # The feature_engineer function from ufc_predictor expects fights_df and fighters_df
        # It will perform the merges internally.
        # We need to ensure the dummy_fights_df has the necessary columns for the merge.
        
        # Ensure 'Fighter Name' exists in dummy_fighters_df for merging
        if 'Fighter Name' not in dummy_fighters_df.columns:
            dummy_fighters_df['Fighter Name'] = dummy_fighters_df.apply(lambda row: row.get('Fighter Name_f1') or row.get('Fighter Name_f2'), axis=1)

        X_processed, _, _ = feature_engineer_predictor(dummy_fighters_df, dummy_fights_df)
        # Ensure the order of columns matches the training data
        # This requires getting the feature names from the trained model
        # For now, we'll assume the order is consistent.
        return X_processed
    elif model_type == 'regressor':
        # The feature_engineer_regression function from ufc_regressor expects fights_df and fighters_df
        # It will perform the merges internally.
        X_processed_str, _, _ = feature_engineer_regression(dummy_fighters_df, dummy_fights_df, target_metric='Str 1')
        X_processed_td, _, _ = feature_engineer_regression(dummy_fighters_df, dummy_fights_df, target_metric='Td 1')
        return X_processed_str, X_processed_td
    
    return None

def predict_fight_outcome(fighter1_name, fighter2_name):
    """
    Predicts the outcome and metrics for a fight between two given fighters.
    """
    print(f"Predicting outcome for {fighter1_name} vs {fighter2_name}...")

    # 1. Load models
    try:
        predictor_model, regressor_str_model, regressor_td_model = load_models()
        print("Models loaded successfully.")
    except Exception as e:
        print(f"Error loading models: {e}. Please ensure models are trained and saved.")
        return

    # 2. Get fighter data
    fighter1_details = get_fighter_data(fighter1_name)
    fighter2_details = get_fighter_data(fighter2_name)

    if not fighter1_details:
        print(f"Could not find data for fighter: {fighter1_name}")
        return
    if not fighter2_details:
        print(f"Could not find data for fighter: {fighter2_name}")
        return

    print(f"Found details for {fighter1_name} and {fighter2_name}.")

    # 3. Preprocess data for predictor model
    X_predictor = preprocess_fighter_data_for_prediction(fighter1_details, fighter2_details, model_type='predictor')
    if X_predictor is None or X_predictor.empty:
        print("Failed to preprocess data for predictor model.")
        return

    # Ensure feature columns match the training data for the predictor
    predictor_features = predictor_model.feature_names_in_
    X_predictor = X_predictor[predictor_features]

    # 4. Make classification prediction
    prediction_proba = predictor_model.predict_proba(X_predictor)[0]
    prediction_class = predictor_model.predict(X_predictor)[0]

    outcome = "Win" if prediction_class == 1 else "Loss"
    win_proba = prediction_proba[1] * 100
    loss_proba = prediction_proba[0] * 100

    print(f"\n--- Classification Prediction ({fighter1_name} vs {fighter2_name}) ---")
    print(f"{fighter1_name} is predicted to {outcome} with {win_proba:.2f}% probability.")
    print(f"{fighter2_name} is predicted to {'Win' if outcome == 'Loss' else 'Loss'} with {loss_proba:.2f}% probability.")

    # 5. Preprocess data for regressor models
    X_regressor_str, X_regressor_td = preprocess_fighter_data_for_prediction(fighter1_details, fighter2_details, model_type='regressor')
    if X_regressor_str is None or X_regressor_str.empty or X_regressor_td is None or X_regressor_td.empty:
        print("Failed to preprocess data for regressor models.")
        return

    # Ensure feature columns match the training data for the regressors
    regressor_str_features = regressor_str_model.feature_names_in_
    regressor_td_features = regressor_td_model.feature_names_in_
    
    X_regressor_str = X_regressor_str[regressor_str_features]
    X_regressor_td = X_regressor_td[regressor_td_features]

    # 6. Make regression predictions
    predicted_str = regressor_str_model.predict(X_regressor_str)[0]
    predicted_td = regressor_td_model.predict(X_regressor_td)[0]

    print(f"\n--- Regression Predictions for {fighter1_name} ---")
    print(f"Predicted Significant Strikes: {predicted_str:.2f}")
    print(f"Predicted Takedowns: {predicted_td:.2f}")

if __name__ == '__main__':
    # Example usage:
    # Ensure you have run ufc_predictor.py and ufc_regressor.py at least once
    # to train and save the models before running this script.
    fighter1 = "Islam Makhachev" # Replace with actual fighter names
    fighter2 = "Charles Oliveira" # Replace with actual fighter names
    predict_fight_outcome(fighter1, fighter2)
