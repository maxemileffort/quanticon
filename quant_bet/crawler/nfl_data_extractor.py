import os
import re
from bs4 import BeautifulSoup
import pandas as pd

PAGES_DIR = r"C:\Users\Max\Desktop\projects\quanticon\quant_bet\crawler\pages"

def get_team_full_name(team_abbr):
    """
    Returns the full team name for a given abbreviation.
    """
    team_name_map = {
        'crd': 'Arizona Cardinals'
        ,'az': 'Arizona Cardinals'
, 'atl': 'Atlanta Falcons'
, 'rav': 'Baltimore Ravens'
, 'bal': 'Baltimore Ravens',
        'buf': 'Buffalo Bills'
, 'car': 'Carolina Panthers'
, 'chi': 'Chicago Bears',
        'cin': 'Cincinnati Bengals'
, 'cle': 'Cleveland Browns'
, 'dal': 'Dallas Cowboys',
        'den': 'Denver Broncos'
, 'det': 'Detroit Lions'
, 'gnb': 'Green Bay Packers'
, 'gb': 'Green Bay Packers',
        'htx': 'Houston Texans'
, 'clt': 'Indianapolis Colts'
, 'ind': 'Indianapolis Colts'
, 'jax': 'Jacksonville Jaguars',
        'kan': 'Kansas City Chiefs'
, 'rai': 'Las Vegas Raiders'
, 'lv': 'Las Vegas Raiders'
, 'sdg': 'Los Angeles Chargers'
, 'lac': 'Los Angeles Chargers',
        'ram': 'Los Angeles Rams',
        'lar': 'Los Angeles Rams'
, 'mia': 'Miami Dolphins'
, 'min': 'Minnesota Vikings',
        'nwe': 'New England Patriots',
        'ne': 'New England Patriots'
, 'nor': 'New Orleans Saints'
, 'no': 'New Orleans Saints'
, 'nyg': 'New York Giants',
        'nyj': 'New York Jets'
, 'phi': 'Philadelphia Eagles'
, 'pit': 'Pittsburgh Steelers',
        'sfo': 'San Francisco 49ers'
, 'sea': 'Seattle Seahawks'
, 'tam': 'Tampa Bay Buccaneers',
        'oti': 'Tennessee Titans',
        'ten': 'Tennessee Titans'
, 'was': 'Washington Commanders'
    }
    return team_name_map.get(team_abbr, team_abbr.upper())

def extract_nfl_game_details(html_content, team_name, year):
    """
    Extracts details from a pro-football-reference.com team season HTML page.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find the 'Schedule & Game Results' table
    games_table = soup.find('table', {'id': 'games'})
    if not games_table:
        return []

    game_data = []
    rows = games_table.find('tbody').find_all('tr')

    for row in rows:
        # Skip rows that are headers or bye weeks
        if 'over_header' in row.get('class', []) or 'thead' in row.get('class', []) or 'bye_week' in row.get('class', []) or 'full_table' in row.get('class', []):
            continue
        
        # Check if it's a bye week row
        opp_cell = row.find('td', {'data-stat': 'opp'})
        if opp_cell and 'Bye Week' in opp_cell.get_text(strip=True):
            continue

        try:
            week_elem = row.find('th', {'data-stat': 'week_num'})
            week = week_elem.get_text(strip=True) if week_elem else None

            date_elem = row.find('td', {'data-stat': 'game_date'})
            date = date_elem.get_text(strip=True) if date_elem else None

            game_location_elem = row.find('td', {'data-stat': 'game_location'})
            game_location = game_location_elem.get_text(strip=True) if game_location_elem else None

            opponent_elem = row.find('td', {'data-stat': 'opp'})
            opponent_link = opponent_elem.find('a') if opponent_elem else None
            opponent = opponent_link.get_text(strip=True) if opponent_link else None
            
            # Scores might be empty for future games
            team_score_str_elem = row.find('td', {'data-stat': 'pts_off'})
            team_score_str = team_score_str_elem.get_text(strip=True) if team_score_str_elem else None
            
            opp_score_str_elem = row.find('td', {'data-stat': 'pts_def'})
            opp_score_str = opp_score_str_elem.get_text(strip=True) if opp_score_str_elem else None
            
            team_score = int(team_score_str) if team_score_str and team_score_str.isdigit() else None
            opp_score = int(opp_score_str) if opp_score_str and opp_score_str.isdigit() else None
            
            game_outcome_elem = row.find('td', {'data-stat': 'game_outcome'})
            game_outcome = game_outcome_elem.get_text(strip=True) if game_outcome_elem else None

            game_details = {
                'week': week,
                'date': date,
                'year': year, # Add year to game details
                'team': team_name,
                'game_location': game_location,
                'opponent': opponent,
                'team_score': team_score,
                'opponent_score': opp_score,
                'game_outcome': game_outcome,
                # Add more stats as needed from the table
                'first_down_off': int(row.find('td', {'data-stat': 'first_down_off'}).get_text(strip=True)) if row.find('td', {'data-stat': 'first_down_off'}) and row.find('td', {'data-stat': 'first_down_off'}).get_text(strip=True) else None,
                'yards_off': int(row.find('td', {'data-stat': 'yards_off'}).get_text(strip=True)) if row.find('td', {'data-stat': 'yards_off'}) and row.find('td', {'data-stat': 'yards_off'}).get_text(strip=True) else None,
                'pass_yds_off': int(row.find('td', {'data-stat': 'pass_yds_off'}).get_text(strip=True)) if row.find('td', {'data-stat': 'pass_yds_off'}) and row.find('td', {'data-stat': 'pass_yds_off'}).get_text(strip=True) else None,
                'rush_yds_off': int(row.find('td', {'data-stat': 'rush_yds_off'}).get_text(strip=True)) if row.find('td', {'data-stat': 'rush_yds_off'}) and row.find('td', {'data-stat': 'rush_yds_off'}).get_text(strip=True) else None,
                'to_off': int(row.find('td', {'data-stat': 'to_off'}).get_text(strip=True)) if row.find('td', {'data-stat': 'to_off'}) and row.find('td', {'data-stat': 'to_off'}).get_text(strip=True) else None,
                'first_down_def': int(row.find('td', {'data-stat': 'first_down_def'}).get_text(strip=True)) if row.find('td', {'data-stat': 'first_down_def'}) and row.find('td', {'data-stat': 'first_down_def'}).get_text(strip=True) else None,
                'yards_def': int(row.find('td', {'data-stat': 'yards_def'}).get_text(strip=True)) if row.find('td', {'data-stat': 'yards_def'}) and row.find('td', {'data-stat': 'yards_def'}).get_text(strip=True) else None,
                'pass_yds_def': int(row.find('td', {'data-stat': 'pass_yds_def'}).get_text(strip=True)) if row.find('td', {'data-stat': 'pass_yds_def'}) and row.find('td', {'data-stat': 'pass_yds_def'}).get_text(strip=True) else None,
                'rush_yds_def': int(row.find('td', {'data-stat': 'rush_yds_def'}).get_text(strip=True)) if row.find('td', {'data-stat': 'rush_yds_def'}) and row.find('td', {'data-stat': 'rush_yds_def'}).get_text(strip=True) else None,
                'to_def': int(row.find('td', {'data-stat': 'to_def'}).get_text(strip=True)) if row.find('td', {'data-stat': 'to_def'}) and row.find('td', {'data-stat': 'to_def'}).get_text(strip=True) else None,
            }
            game_data.append(game_details)
        except Exception as e:
            print(f"Error parsing row in file: {e}")
            continue
            
    return game_data

def get_nfl_html_files(base_dir=PAGES_DIR):
    """
    Walks through the directory and finds pro-football-reference.com team season HTML files.
    """
    nfl_html_files = []
    for root, dirs, files in os.walk(base_dir):
        print(f'Root: {dirs}')
        for file in files:
            # Only process files that are team season pages
            # Check for team season pages based on the new naming convention
            # Example: 'www.pro-football-reference.com--teams-buf-2025.htm-1757140863-378af2b3.html'
            if "pro-football-reference.com--teams-" in file and file.endswith(".html"):
                # Extract the part that contains team abbreviation and year
                parts = file.split('--teams-')
                if len(parts) > 1:
                    team_year_part = parts[1].split('.htm')[0]
                    # Check if it contains a year (e.g., 'buf-2025')
                    if re.search(r'-\d{4}$', team_year_part):
                        nfl_html_files.append(os.path.join(root, file))
    return nfl_html_files
def create_nfl_dataframe():
    """
    Creates a pandas DataFrame from extracted NFL game details.
    """
    all_game_data = []
    nfl_files = get_nfl_html_files()
    
    if not nfl_files:
        print(f"No NFL HTML files found in {PAGES_DIR}. Please ensure files are present.")
        return pd.DataFrame()

    for file_path in nfl_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Extract team name from file path (e.g., 'oti' from 'www.pro-football-reference.com--teams-oti-2025.htm')
            # Extract team abbreviation and year from file path
            parts = file_path.split('--teams-')[1].split('-')
            team_abbr = parts[0]
            year = parts[1].split('.')[0] # Assuming year is always the second part after team_abbr and before .html

            team_full_name = get_team_full_name(team_abbr)

            game_details_list = extract_nfl_game_details(html_content, team_full_name, year)
            if game_details_list:
                # Filter out games with no scores (future games)
                completed_games = [game for game in game_details_list if game['team_score'] is not None and game['opponent_score'] is not None]
                all_game_data.extend(completed_games)
        except Exception as e:
            print(f"Error processing file {file_path}: {e}")
            
    df = pd.DataFrame(all_game_data)

    # Convert relevant columns to numeric, coercing errors to NaN
    numeric_cols = [
        'week', 'team_score', 'opponent_score', 'first_down_off', 'yards_off',
        'pass_yds_off', 'rush_yds_off', 'to_off', 'first_down_def', 'yards_def',
        'pass_yds_def', 'rush_yds_def', 'to_def'
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Impute missing numerical values with the mean of their respective columns
    # This is done after filtering out future games (where scores are None)
    # so imputation is based on completed game statistics.
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].mean())

    return df
if __name__ == "__main__":
    # Example usage:
    nfl_df = create_nfl_dataframe()
    if not nfl_df.empty:
        print(nfl_df.head())
        print(f"Total NFL games extracted: {len(nfl_df)}")
    else:
        print("No NFL data to display.")
