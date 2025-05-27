import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from finta import TA # Assuming finta is needed for feature generation

def time_series_split(data, test_size=0.2):
    """
    Splits data into train and test sets while preserving time series order.

    Args:
        data (pd.DataFrame): The input data.
        test_size (float): The proportion of the data to include in the test split.

    Returns:
        tuple: (train_data, test_data)
    """
    if not isinstance(data.index, pd.DatetimeIndex):
         # Assuming the index is not DatetimeIndex, sort by index before splitting
         data = data.sort_index()

    n_samples = len(data)
    n_test = int(n_samples * test_size)
    train_data = data.iloc[:n_samples - n_test]
    test_data = data.iloc[n_samples - n_test:]
    return train_data, test_data

# Function for feature and label generation will be added next

def generate_features_and_labels(data, indicators_params, target_roi):
    """
    Generates technical indicator features and the target label.

    Args:
        data (pd.DataFrame): The input data (OHLCV).
        indicators_params (dict): A dictionary where keys are indicator names
                                  and values are dictionaries of their parameters.
        target_roi (float): The target ROI for generating the target label.

    Returns:
        pd.DataFrame: Data with technical indicators as features and the target label.
    """
    data_with_features = data.copy()

    # Define available indicators and their corresponding finta functions
    available_indicators = {
        "SMA": {"func": TA.SMA},
        "EMA": {"func": TA.EMA},
        "RSI": {"func": TA.RSI},
        "MACD": {"func": TA.MACD},
        "BBANDS": {"func": TA.BBANDS},
        "ADX": {"func": TA.ADX},
        "ATR": {"func": TA.ATR},
        "STOCH": {"func": TA.STOCH},
        "STOCHD": {"func": TA.STOCHD},
    }

    for indicator_name, params in indicators_params.items():
        if indicator_name in available_indicators:
            indicator_info = available_indicators[indicator_name]
            try:
                # Apply the indicator using finta
                indicator_data = indicator_info["func"](data_with_features, **params)

                # finta returns Series or DataFrame, need to add to main DataFrame
                if isinstance(indicator_data, pd.Series):
                    data_with_features[indicator_name] = indicator_data
                elif isinstance(indicator_data, pd.DataFrame):
                    # For indicators returning multiple columns (like BBANDS, MACD, STOCH)
                    for col in indicator_data.columns:
                        data_with_features[f"{indicator_name}_{col}"] = indicator_data[col]

            except Exception as e:
                print(f"Could not apply indicator {indicator_name} with params {params}: {e}")
                continue
        else:
            print(f"Unknown indicator: {indicator_name}")


    # Generate target label (simplified from app.py)
    # This is a simplified target labeling strategy.
    # A more sophisticated approach would involve looking for specific patterns
    # or using machine learning models.
    data_with_features['Price_Change'] = data_with_features['Close'].pct_change() * 100
    # Create a binary label: 1 if the price increases by target_roi% in the next 5 periods, 0 otherwise
    # Using .rolling() with a future window is not standard, a loop or shift is needed
    # Let's use a shift for a simplified future lookahead
    future_window = 5 # Look 5 periods into the future
    data_with_features['Future_Max_Close'] = data_with_features['Close'].shift(-future_window).rolling(future_window).max()
    data_with_features['Target_Hit'] = (data_with_features['Future_Max_Close'] >= data_with_features['Close'] * (1 + target_roi / 100)).astype(int)

    # Drop rows with NaN in Future_Max_Close and Target_Hit before dropping helper columns
    data_with_features = data_with_features.dropna(subset=['Future_Max_Close', 'Target_Hit']).copy()

    # Drop the helper columns
    data_with_features = data_with_features.drop(columns=['Price_Change', 'Future_Max_Close'])

    return data_with_features
