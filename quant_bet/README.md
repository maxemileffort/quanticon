# QuantBet: Sports Analytics and Betting Prediction System

QuantBet is a collection of Python scripts designed for sports analytics and betting predictions, currently focusing on NFL and UFC. The system encompasses data extraction, preprocessing, machine learning model training, and prediction generation, with an emphasis on providing insights for betting.

## Features

### NFL Prediction System
- **Data Extraction:** Utilizes web crawlers (`crawler/nfl_data_extractor.py`, `crawler/nfl_player_data_extractor.py`) to gather historical game and player statistics from sources like Pro-Football-Reference.
- **Model Training:**
    - `nfl_predictor.py`: Trains a Logistic Regression model to predict NFL game winners (home team win/loss).
    - `nfl_regressor.py`: Trains Linear Regression models to predict various game statistics such as team score, opponent score, offensive passing yards, and offensive rushing yards.
    - `nfl_player_regressor.py`: Trains Linear Regression models to predict individual player statistics like rushing yards, receiving yards, passing yards, tackles, and sacks.
- **Game Prediction:**
    - `nfl_predict_game.py`: Offers two modes for game prediction:
        - **Basic Prediction:** Provides a single predicted winner and score/yardage estimates.
        - **Enhanced Prediction (Monte Carlo Simulation):** Leverages residual standard deviations from regressor models to simulate numerous game outcomes, providing win probabilities and percentile ranges for scores and yardage.
- **Odds Integration:**
    - `run_nfl_stats.py`: Fetches real-time NFL betting odds from an external API (Odds API), processes the data, and integrates with the prediction system to generate and save game predictions. It also includes basic data visualization for odds comparison across bookmakers.

### UFC Prediction System
- **Data Extraction:** Employs web crawlers (`crawler/ufc_data_extractor.py`) to extract fighter details and fight history from sources like UFCStats.com.
- **Model Training:**
    - `ufc_predictor.py`: Trains a Logistic Regression model to predict the winner of a UFC fight.
    - `ufc_regressor.py`: Trains Linear Regression models to predict specific fighter metrics within a fight, such as significant strikes and takedowns.
- **Fight Prediction:**
    - `ufc_predict_fight.py`: Uses the trained UFC models to predict the outcome (win/loss probability) and key statistics (e.g., significant strikes, takedowns) for a given fight between two fighters.

### Core Components
- **`crawler/` directory:** Contains various web scraping and data extraction utilities for NFL and UFC data.
- **`models/` directory:** Stores the trained machine learning models (`.joblib` files) for both NFL and UFC predictions.
- **`dataframes/` directory:** Used for caching processed dataframes (e.g., `nfl_temp.csv`) to avoid frequent re-crawling.
- **`odds_data/` directory:** Stores raw and processed odds data fetched from external APIs.
- **`nfl_pred_outs/` directory:** Stores the output of NFL game predictions.

## Setup and Usage

### Prerequisites
- Python 3.x
- `pip` for package installation

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/your-repo/quanticon.git
   cd quanticon/quant_bet
   ```
2. Install required Python packages:
   ```bash
   pip install -r requirements.txt # Assuming a requirements.txt exists or create one
   ```
   *(Note: A `requirements.txt` file is not explicitly present in the provided file list, but would be necessary for dependency management.)*

3. **API Key Configuration:**
   - Obtain an API key for the Odds API (or similar sports odds provider).
   - Create a `.env` file in the `quanticon/quant_bet` directory with your API key and base URL:
     ```
     ODDS_API_KEY=your_api_key_here
     ODDS_API_BASE_URL=https://api.the-odds-api.com
     ```

### Running NFL Predictions
1. **Train NFL Models:**
   ```bash
   python nfl_predictor.py
   python nfl_regressor.py
   python nfl_player_regressor.py
   ```
2. **Fetch Odds and Make Predictions:**
   - Modify `SEASON` and `WEEK` variables in `run_nfl_stats.py` as needed.
   - Run the script:
     ```bash
     python run_nfl_stats.py
     ```
   - This will fetch odds, make predictions, and save them to `nfl_pred_outs/`.

3. **Predict a Specific NFL Game:**
   ```bash
   python nfl_predict_game.py <team1_abbr> <team2_abbr> <year> <week> [--enhanced --simulations <num>]
   # Example:
   python nfl_predict_game.py kan den 2025 3 --enhanced --simulations 5000
   ```

### Running UFC Predictions
1. **Train UFC Models:**
   ```bash
   python ufc_predictor.py
   python ufc_regressor.py
   ```
2. **Predict a Specific UFC Fight:**
   ```bash
   python ufc_predict_fight.py "Fighter Name 1" "Fighter Name 2"
   # Example:
   python ufc_predict_fight.py "Islam Makhachev" "Charles Oliveira"
   ```

## Project Structure

```
quanticon/quant_bet/
├── .env                      # Environment variables (e.g., API keys)
├── baseball_odds_api_explorer.ipynb # Jupyter notebook for baseball odds exploration
├── football_odds_api_explorer.ipynb # Jupyter notebook for football odds exploration
├── libraries.md              # Documentation for libraries used
├── mma_odds_api_explorer.ipynb    # Jupyter notebook for MMA odds exploration
├── nfl_player_regressor.py   # Trains NFL player stat regression models
├── nfl_predict_game.py       # Predicts NFL game outcomes and stats
├── nfl_predictor.py          # Trains NFL game winner prediction model
├── nfl_regressor.py          # Trains NFL game stat regression models
├── run_nfl_stats.py          # Fetches NFL odds, runs predictions, and saves results
├── sportsipy_api_explorer.ipynb # Jupyter notebook for sportsipy API exploration
├── ufc_predict_fight.py      # Predicts UFC fight outcomes and stats
├── ufc_predictor.py          # Trains UFC fight winner prediction model
├── ufc_regressor.py          # Trains UFC fight stat regression models
├── crawler/                  # Web scraping and data extraction utilities
│   ├── crawler_v2.py
│   ├── crawler.py
│   ├── html_to_md.py
│   ├── link_manager.py
│   ├── nfl_data_extractor.py      # Extracts NFL game data
│   ├── nfl_player_data_extractor.py # Extracts NFL player data
│   ├── organize_html_files.py
│   ├── organize_md_files.py
│   ├── ufc_data_extractor.py      # Extracts UFC fighter and fight data
│   ├── links_crawled/        # Stores crawled links
│   ├── md/                   # Markdown output from HTML conversion
│   └── pages/                # Raw HTML pages from crawling
├── dataframes/               # Stores processed dataframes (e.g., nfl_temp.csv)
├── ext_api_docs/             # External API documentation (e.g., odds_api.md)
├── models/                   # Trained machine learning models
│   ├── nfl_predictor_win_model.joblib
│   ├── nfl_regressor_opp_score_model.joblib
│   ├── nfl_regressor_pass_yds_off_model.joblib
│   ├── nfl_regressor_rush_yds_off_model.joblib
│   ├── nfl_regressor_team_score_model.joblib
│   ├── nfl_player_regressor_pass_yds_model.joblib
│   ├── nfl_player_regressor_rec_yds_model.joblib
│   ├── nfl_player_regressor_rush_yds_model.joblib
│   ├── nfl_player_regressor_sacks_model.joblib
│   └── nfl_player_regressor_tackles_model.joblib
├── nfl_pred_outs/            # NFL prediction output files
├── odds_data/                # Raw and processed odds data
└── results_data/             # General results data
