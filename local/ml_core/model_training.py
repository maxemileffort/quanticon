import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

def train_xgboost_model(X_train, y_train, params=None):
    """
    Trains an XGBoost classifier.

    Args:
        X_train (pd.DataFrame): Training features.
        y_train (pd.Series): Training labels.
        params (dict, optional): XGBoost model hyperparameters. Defaults to None.

    Returns:
        xgb.Classifier: The trained XGBoost model.
    """
    if params is None:
        # Default parameters if none are provided
        params = {
            'objective': 'binary:logistic',
            'eval_metric': 'logloss',
            # 'use_label_encoder': False # Removed to suppress warning
        }

    model = xgb.XGBClassifier(**params)
    model.fit(X_train, y_train)
    return model

# Hyperparameter tuning logic will be added later

def tune_xgboost_hyperparameters(X_train, y_train, param_grid, cv=3):
    """
    Tunes XGBoost hyperparameters using GridSearchCV.

    Args:
        X_train (pd.DataFrame): Training features.
        y_train (pd.Series): Training labels.
        param_grid (dict): Dictionary with parameters names (string) as keys
                           and lists of parameter settings to try as values.
        cv (int): Number of folds in cross validation.

    Returns:
        xgb.Classifier: The best trained XGBoost model found during tuning.
        dict: The best hyperparameters found.
    """
    model = xgb.XGBClassifier(use_label_encoder=False, eval_metric='logloss') # Suppress warning and set eval_metric
    grid_search = GridSearchCV(estimator=model, param_grid=param_grid, cv=cv, scoring='accuracy')
    grid_search.fit(X_train, y_train)

    print(f"Best parameters found: {grid_search.best_params_}")
    print(f"Best cross-validation score: {grid_search.best_score_}")

    return grid_search.best_estimator_, grid_search.best_params_
