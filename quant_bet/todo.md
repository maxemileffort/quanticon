# QuantBet TODO List and Improvement Ideas

This document outlines unfinished features, potential improvements, and areas for refactoring within the QuantBet sports analytics and betting prediction system.

## General Improvements

- [ ] **Create `requirements.txt`:** Generate a `requirements.txt` file to manage Python dependencies.
- [ ] **Enhanced Error Handling:** Implement more robust error handling across all scripts, especially for API calls, file I/O, and data processing.
- [ ] **Logging System:** Replace `print()` statements with a proper logging system (e.g., Python's `logging` module) for better debugging, monitoring, and control over output verbosity.
- [ ] **Centralized Configuration:** Move hardcoded values (e.g., API keys, base URLs, model/data paths, season/week numbers, team mappings) into a dedicated configuration file (e.g., `config.ini`, `config.json`, or a `config.py` module) for easier management and flexibility.
- [ ] **Refactor Code Duplication:** Identify and refactor common code patterns (e.g., data loading, date/time feature engineering, sample weighting) into shared utility functions or modules to reduce redundancy, improve maintainability, and ensure consistency. This applies to both NFL and UFC model training scripts.
- [ ] **Automated Data Refresh:** Implement a more sophisticated mechanism for checking data freshness (e.g., checking for new games/weeks, not just file age) and triggering data extraction/updates.

## NFL Specific Improvements

### Data Extraction & Preprocessing
- [ ] **Dynamic Data Freshness Check:** Improve `find_nfl_dataframe` in `nfl_predict_game.py` to dynamically check if data for the *current* season and week is available and up-to-date, rather than just a fixed 5-day old check.
- [ ] **Robust Player Data Extraction:** Review and enhance `crawler/nfl_player_data_extractor.py` for robust data validation and error handling, similar to game data.

### Feature Engineering
- [ ] **Refine Player Regressor Features:** Conduct thorough feature selection and engineering for `nfl_player_regressor.py` to optimize individual player stat predictions.
- [ ] **Advanced Game Prediction Features:**
    - Replace simplified "average historical data" in `get_team_stats_for_prediction` with more sophisticated methods (e.g., rolling averages, opponent-adjusted stats, strength of schedule, recent form).
    - Explore interaction features between offensive and defensive statistics.
- [ ] **Categorical Feature Encoding:** Investigate alternative categorical encoding techniques (e.g., target encoding, embedding layers) for the `opponent` feature to handle sparsity and potentially improve model performance.
- [ ] **Granular Time Features:** Explore more granular time-based features (e.g., time of day, specific day of month) or interaction features with other game parameters.

### Model Improvements
- [ ] **Explore Alternative Models:** Evaluate other machine learning models (e.g., Gradient Boosting, Random Forests, Neural Networks) for both prediction and regression tasks to potentially achieve higher accuracy.
- [ ] **Hyperparameter Tuning:** Implement systematic hyperparameter tuning (e.g., GridSearchCV, RandomizedSearchCV) for all models to optimize their performance.
- [ ] **Cross-validation:** Incorporate k-fold cross-validation for more robust model evaluation and to reduce overfitting.
- [ ] **Probabilistic Forecasting:** Further explore and implement advanced probabilistic forecasting methods for better uncertainty quantification in predictions.

### `run_nfl_stats.py` Enhancements
- [ ] **Dynamic Season/Week:** Make `SEASON` and `WEEK` variables dynamic, either through command-line arguments or configuration.
- [ ] **Dynamic League Selection:** Ensure `league_index` is dynamically determined or configurable to correctly select NFL odds.
- [ ] **Plotting Output:** Implement functionality to save generated plots to files (e.g., PNG, JPEG) instead of just commenting out `plt.show()`.
- [ ] **Structured Prediction Output:** Save prediction results in a more structured format (e.g., JSON, CSV) for easier programmatic access and analysis, rather than plain text files.
- [ ] **Dynamic Team Abbreviation Mapping:** Load `team_abrev_map` from a configuration file or dynamically generate it.

## UFC Specific Improvements

### Data Extraction & Preprocessing
- [ ] **Optimized Fighter Data Retrieval:** Optimize `get_fighter_data` in `ufc_predict_fight.py` by creating a mapping of fighter names to file paths or implementing a more targeted search to avoid iterating through all HTML files.
- [ ] **Robust HTML Parsing:** Enhance `extract_fighter_details` and `extract_fight_history` in `crawler/ufc_data_extractor.py` with robust error handling for malformed HTML structures.

### Feature Engineering
- [ ] **Improved Dummy Data for Future Fights:** Develop more sophisticated methods to infer or estimate features for future fights in `preprocess_fighter_data_for_prediction`, moving beyond simple dummy values.
- [ ] **Advanced Fighter Features:** Explore additional feature engineering for fighter statistics, such as recent performance trends, opponent strength adjustments, and fight camp changes.
- [ ] **Categorical Fighter Features:** Consider incorporating fighter names or other categorical fighter attributes into the models using appropriate encoding techniques.

### Model Improvements
- [ ] **Explore Alternative Models:** Evaluate other machine learning models for both UFC prediction and regression tasks.
- [ ] **Hyperparameter Tuning:** Implement systematic hyperparameter tuning for UFC models.
- [ ] **Uncertainty Quantification:** Provide confidence intervals for regression predictions and probability distributions for classification outcomes.

### `ufc_predict_fight.py` Enhancements
- [ ] **Command-Line Arguments for Fighters:** Allow fighter names to be passed as command-line arguments instead of being hardcoded.
- [ ] **Robust Feature Matching:** Implement more robust handling for cases where features might be missing or mismatched between training and prediction data.
