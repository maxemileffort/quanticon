import os
import re
from bs4 import BeautifulSoup
import pandas as pd

PAGES_DIR = r"C:\Users\Max\Desktop\projects\quanticon\quant_bet\crawler\pages"

def get_player_full_name(player_id):
    """
    Returns the full player name for a given player ID.
    This would ideally be a lookup from a database or a more comprehensive map.
    For now, we'll just return the player_id as a placeholder.
    """
    return player_id # Placeholder for actual name lookup

def extract_nfl_player_details(html_content, player_id, year_from_filename): # year_from_filename can be None
    """
    Extracts details from a pro-football-reference.com player season HTML page.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find the main content div, which usually contains the player's stats tables
    content_div = soup.find('div', {'id': 'content'})
    if not content_div:
        return []

    tables_to_process = [
        {'id': 'rushing_and_receiving', 'type': 'rushing_receiving'},
        {'id': 'passing', 'type': 'passing'},
        {'id': 'defense', 'type': 'defense'},
        {'id': 'kicking', 'type': 'kicking'},
        # Add other tables as needed
    ]

    # A dictionary to hold player data for the current player, merged by year
    player_yearly_stats = {}

    for table_info in tables_to_process:
        current_table = content_div.find('table', {'id': table_info['id']})
        if current_table:
            rows = current_table.find('tbody').find_all('tr')
            for row in rows:
                if 'full_table' in row.get('class', []) or 'thead' in row.get('class', []) or 'over_header' in row.get('class', []):
                    continue
                
                try:
                    row_year_elem = row.find('th', {'data-stat': 'year_id'})
                    row_year = row_year_elem.get_text(strip=True) if row_year_elem else None

                    if not row_year or not row_year.isdigit(): # Skip if year is not found or not a digit (e.g., career totals)
                        continue

                    current_year_key = int(row_year)

                    if current_year_key not in player_yearly_stats:
                        player_yearly_stats[current_year_key] = {
                            'player_id': player_id,
                            'year': current_year_key,
                            'age': None, 'team': None, 'pos': None, 'games': None, 'games_started': None,
                            'rush_att': None, 'rush_yds': None, 'rush_td': None,
                            'rec': None, 'rec_yds': None, 'rec_td': None,
                            'pass_cmp': None, 'pass_att': None, 'pass_yds': None,
                            'pass_td': None, 'pass_int': None,
                            'def_int': None, 'def_int_yds': None, 'def_int_td': None,
                            'sacks': None, 'tackles_solo': None, 'tackles_assists': None,
                            'fgm': None, 'fga': None, 'xpm': None, 'xpa': None,
                        }
                    
                    # Extract common fields if not already set for the year
                    if player_yearly_stats[current_year_key]['age'] is None:
                        age_elem = row.find('td', {'data-stat': 'age'})
                        player_yearly_stats[current_year_key]['age'] = int(age_elem.get_text(strip=True)) if age_elem and age_elem.get_text(strip=True).isdigit() else None
                    if player_yearly_stats[current_year_key]['team'] is None:
                        team_elem = row.find('td', {'data-stat': 'team'})
                        player_yearly_stats[current_year_key]['team'] = team_elem.get_text(strip=True) if team_elem else None
                    if player_yearly_stats[current_year_key]['pos'] is None:
                        pos_elem = row.find('td', {'data-stat': 'pos'})
                        player_yearly_stats[current_year_key]['pos'] = pos_elem.get_text(strip=True) if pos_elem else None
                    if player_yearly_stats[current_year_key]['games'] is None:
                        games_elem = row.find('td', {'data-stat': 'g'})
                        player_yearly_stats[current_year_key]['games'] = int(games_elem.get_text(strip=True)) if games_elem and games_elem.get_text(strip=True).isdigit() else None
                    if player_yearly_stats[current_year_key]['games_started'] is None:
                        gs_elem = row.find('td', {'data-stat': 'gs'})
                        player_yearly_stats[current_year_key]['games_started'] = int(gs_elem.get_text(strip=True)) if gs_elem and gs_elem.get_text(strip=True).isdigit() else None

                    # Extract stats specific to the current table type
                    if table_info['type'] == 'rushing_receiving':
                        player_yearly_stats[current_year_key].update({
                            'rush_att': int(row.find('td', {'data-stat': 'rush_att'}).get_text(strip=True)) if row.find('td', {'data-stat': 'rush_att'}) and row.find('td', {'data-stat': 'rush_att'}).get_text(strip=True).isdigit() else None,
                            'rush_yds': int(row.find('td', {'data-stat': 'rush_yds'}).get_text(strip=True)) if row.find('td', {'data-stat': 'rush_yds'}) and row.find('td', {'data-stat': 'rush_yds'}).get_text(strip=True).isdigit() else None,
                            'rush_td': int(row.find('td', {'data-stat': 'rush_td'}).get_text(strip=True)) if row.find('td', {'data-stat': 'rush_td'}) and row.find('td', {'data-stat': 'rush_td'}).get_text(strip=True).isdigit() else None,
                            'rec': int(row.find('td', {'data-stat': 'rec'}).get_text(strip=True)) if row.find('td', {'data-stat': 'rec'}) and row.find('td', {'data-stat': 'rec'}).get_text(strip=True).isdigit() else None,
                            'rec_yds': int(row.find('td', {'data-stat': 'rec_yds'}).get_text(strip=True)) if row.find('td', {'data-stat': 'rec_yds'}) and row.find('td', {'data-stat': 'rec_yds'}).get_text(strip=True).isdigit() else None,
                            'rec_td': int(row.find('td', {'data-stat': 'rec_td'}).get_text(strip=True)) if row.find('td', {'data-stat': 'rec_td'}) and row.find('td', {'data-stat': 'rec_td'}).get_text(strip=True).isdigit() else None,
                        })
                    elif table_info['type'] == 'passing':
                        player_yearly_stats[current_year_key].update({
                            'pass_cmp': int(row.find('td', {'data-stat': 'pass_cmp'}).get_text(strip=True)) if row.find('td', {'data-stat': 'pass_cmp'}) and row.find('td', {'data-stat': 'pass_cmp'}).get_text(strip=True).isdigit() else None,
                            'pass_att': int(row.find('td', {'data-stat': 'pass_att'}).get_text(strip=True)) if row.find('td', {'data-stat': 'pass_att'}) and row.find('td', {'data-stat': 'pass_att'}).get_text(strip=True).isdigit() else None,
                            'pass_yds': int(row.find('td', {'data-stat': 'pass_yds'}).get_text(strip=True)) if row.find('td', {'data-stat': 'pass_yds'}) and row.find('td', {'data-stat': 'pass_yds'}).get_text(strip=True).isdigit() else None,
                            'pass_td': int(row.find('td', {'data-stat': 'pass_td'}).get_text(strip=True)) if row.find('td', {'data-stat': 'pass_td'}) and row.find('td', {'data-stat': 'pass_td'}).get_text(strip=True).isdigit() else None,
                            'pass_int': int(row.find('td', {'data-stat': 'pass_int'}).get_text(strip=True)) if row.find('td', {'data-stat': 'pass_int'}) and row.find('td', {'data-stat': 'pass_int'}).get_text(strip=True).isdigit() else None,
                        })
                    elif table_info['type'] == 'defense':
                        player_yearly_stats[current_year_key].update({
                            'def_int': int(row.find('td', {'data-stat': 'def_int'}).get_text(strip=True)) if row.find('td', {'data-stat': 'def_int'}) and row.find('td', {'data-stat': 'def_int'}).get_text(strip=True).isdigit() else None,
                            'def_int_yds': int(row.find('td', {'data-stat': 'def_int_yds'}).get_text(strip=True)) if row.find('td', {'data-stat': 'def_int_yds'}) and row.find('td', {'data-stat': 'def_int_yds'}).get_text(strip=True).isdigit() else None,
                            'def_int_td': int(row.find('td', {'data-stat': 'def_int_td'}).get_text(strip=True)) if row.find('td', {'data-stat': 'def_int_td'}) and row.find('td', {'data-stat': 'def_int_td'}).get_text(strip=True).isdigit() else None,
                            'sacks': float(row.find('td', {'data-stat': 'sacks'}).get_text(strip=True)) if row.find('td', {'data-stat': 'sacks'}) and row.find('td', {'data-stat': 'sacks'}).get_text(strip=True).replace('.', '', 1).isdigit() else None,
                            'tackles_solo': int(row.find('td', {'data-stat': 'tackles_solo'}).get_text(strip=True)) if row.find('td', {'data-stat': 'tackles_solo'}) and row.find('td', {'data-stat': 'tackles_solo'}).get_text(strip=True).isdigit() else None,
                            'tackles_assists': int(row.find('td', {'data-stat': 'tackles_assists'}).get_text(strip=True)) if row.find('td', {'data-stat': 'tackles_assists'}) and row.find('td', {'data-stat': 'tackles_assists'}).get_text(strip=True).isdigit() else None,
                        })
                    elif table_info['type'] == 'kicking':
                        player_yearly_stats[current_year_key].update({
                            'fgm': int(row.find('td', {'data-stat': 'fgm'}).get_text(strip=True)) if row.find('td', {'data-stat': 'fgm'}) and row.find('td', {'data-stat': 'fgm'}).get_text(strip=True).isdigit() else None,
                            'fga': int(row.find('td', {'data-stat': 'fga'}).get_text(strip=True)) if row.find('td', {'data-stat': 'fga'}) and row.find('td', {'data-stat': 'fga'}).get_text(strip=True).isdigit() else None,
                            'xpm': int(row.find('td', {'data-stat': 'xpm'}).get_text(strip=True)) if row.find('td', {'data-stat': 'xpm'}) and row.find('td', {'data-stat': 'xpm'}).get_text(strip=True).isdigit() else None,
                            'xpa': int(row.find('td', {'data-stat': 'xpa'}).get_text(strip=True)) if row.find('td', {'data-stat': 'xpa'}) and row.find('td', {'data-stat': 'xpa'}).get_text(strip=True).isdigit() else None,
                        })

                except Exception as e:
                    print(f"Error parsing {table_info['type']} row for {player_id} in {row_year}: {e}")
                    continue
    
    player_data = list(player_yearly_stats.values())
    return player_data

def get_nfl_player_html_files(base_dir=PAGES_DIR):
    """
    Walks through the directory and finds pro-football-reference.com player season HTML files.
    """
    nfl_html_files = []
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            # Check for player season pages based on the naming convention
            # Example: 'www.pro-football-reference.com--players-B/BradyTo00-2020.htm-1757140863-378af2b3.html'
            # Or: 'www.pro-football-reference.com--players-a-achade00.htm-1757734101-e87e3ce2.html'
            if "pro-football-reference.com--players-" in file and file.endswith(".html"):
                nfl_html_files.append(os.path.join(root, file))
    return nfl_html_files

def create_nfl_player_dataframe():
    """
    Creates a pandas DataFrame from extracted NFL player details.
    """
    all_player_data = []
    nfl_player_files = get_nfl_player_html_files()
    
    if not nfl_player_files:
        print(f"No NFL player HTML files found in {PAGES_DIR}. Please ensure files are present.")
        return pd.DataFrame()

    for file_path in nfl_player_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Extract player ID using regex, accounting for different path structures
            # The player ID is typically after '--players-' and before '.htm'
            # It can be in formats like 'B/BradyTo00' or 'a-achade00'
            player_id_match = re.search(r'--players-(?:[a-zA-Z]/)?([a-zA-Z0-9-]+)\.htm(?:-[0-9]+-[a-f0-9]+)?\.html', file_path)
            if player_id_match:
                player_id = player_id_match.group(1) # Get the actual ID part, e.g., 'BradyTo00' from 'B/BradyTo00' or 'achade00' from 'a-achade00'
            else:
                print(f"Could not extract player ID from {file_path}")
                continue

            player_full_name = get_player_full_name(player_id)

            # Pass None for year, as it will be extracted from the HTML content per row
            player_details_list = extract_nfl_player_details(html_content, player_full_name, None)
            if player_details_list:
                all_player_data.extend(player_details_list)
        except Exception as e:
            print(f"Error processing file {file_path}: {e}")
            
    df = pd.DataFrame(all_player_data)

    # Convert relevant columns to numeric, coercing errors to NaN
    numeric_cols = [
        'age', 'games', 'games_started', 'rush_att', 'rush_yds', 'rush_td',
        'rec', 'rec_yds', 'rec_td', 'pass_cmp', 'pass_att', 'pass_yds',
        'pass_td', 'pass_int', 'def_int', 'def_int_yds', 'def_int_td',
        'sacks', 'tackles_solo', 'tackles_assists', 'fgm', 'fga', 'xpm', 'xpa'
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Impute missing numerical values with the mean of their respective columns
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].mean())

    return df

if __name__ == "__main__":
    # Example usage:
    nfl_player_df = create_nfl_player_dataframe()
    if not nfl_player_df.empty:
        print(nfl_player_df.head())
        print(f"Total NFL player seasons extracted: {len(nfl_player_df)}")
    else:
        print("No NFL player data to display.")
