import os
import re
from bs4 import BeautifulSoup
import pandas as pd

PAGES_DIR = r"C:\Users\Max\Desktop\projects\quanticon\quant_bet\crawler\pages"

def extract_fighter_details(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')

    fighter_name = soup.find('span', class_='b-content__title-highlight').text.strip()
    record = soup.find('span', class_='b-content__title-record').text.replace('Record:', '').strip()

    details = {
        'Fighter Name': fighter_name,
        'Record': record
    }

    # Extract physical attributes
    info_box_small = soup.find('div', class_='b-list__info-box_style_small-width')
    if info_box_small:
        for item in info_box_small.find_all('li', class_='b-list__box-list-item_type_block'):
            title = item.find('i', class_='b-list__box-item-title').text.strip().replace(':', '')
            value = item.text.replace(item.find('i').text, '').strip()
            details[title] = value

    # Extract career statistics
    info_box_middle = soup.find('div', class_='b-list__info-box_style_middle-width')
    if info_box_middle:
        for item in info_box_middle.find_all('li', class_='b-list__box-list-item_type_block'):
            title_tag = item.find('i', class_='b-list__box-item-title')
            if title_tag and title_tag.text.strip(): # Ensure title_tag exists and has text
                title = title_tag.text.strip().replace(':', '')
                value = item.text.replace(title_tag.text, '').strip()
                details[title] = value

    return details

def extract_fight_history(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    fight_table = soup.find('table', class_='b-fight-details__table')

    if not fight_table:
        return pd.DataFrame()

    # Manually define the expected headers for clarity and consistency
    expected_headers = [
        'W/L', 'Fighter 1', 'Fighter 2', 'Kd 1', 'Kd 2', 'Str 1', 'Str 2',
        'Td 1', 'Td 2', 'Sub 1', 'Sub 2', 'Event Name', 'Event Date',
        'Method', 'Round', 'Time'
    ]

    data = []
    rows = fight_table.find('tbody').find_all('tr', class_='b-fight-details__table-row')
    for row in rows:
        if 'b-statistics__table-row' in row.get('class', []): # Skip empty row
            continue
        
        cols = row.find_all('td', class_='b-fight-details__table-col')
        if not cols:
            continue

        row_data = []
        
        # W/L
        wl_tag = cols[0].find('a', class_='b-flag')
        wl_text = wl_tag.find('i', class_='b-flag__text').text.strip() if wl_tag else ''
        row_data.append(wl_text)

        # Fighters
        fighter_links = cols[1].find_all('a', class_=['b-link_style_white', 'b-link_style_black'])
        row_data.append(fighter_links[0].text.strip() if len(fighter_links) > 0 else '')
        row_data.append(fighter_links[1].text.strip() if len(fighter_links) > 1 else '')

        # Check if it's a 'Matchup Preview' row (where Kd, Str, Td, Sub are not present)
        matchup_preview_col = cols[3].find('p', class_='b-fight-details__table-text')
        is_matchup_preview = matchup_preview_col and 'Matchup' in matchup_preview_col.text

        if is_matchup_preview:
            # Fill Kd, Str, Td, Sub with empty strings
            row_data.extend([''] * 8) 
            
            # Event Name and Date
            event_links = cols[6].find_all('a', class_=['b-link_style_white', 'b-link_style_black'])
            event_name = event_links[0].text.strip() if len(event_links) > 0 else ''
            event_date_tag = cols[6].find('p', class_='b-fight-details__table-text', recursive=False)
            event_date = event_date_tag.text.strip() if event_date_tag else ''
            row_data.extend([event_name, event_date])
            
            # Method, Round, Time
            row_data.extend(['', '', ''])
        else:
            # Regular fight row
            # Kd
            kd_texts = cols[2].find_all('p', class_='b-fight-details__table-text')
            row_data.append(kd_texts[0].text.strip() if len(kd_texts) > 0 else '')
            row_data.append(kd_texts[1].text.strip() if len(kd_texts) > 1 else '')

            # Str
            str_texts = cols[3].find_all('p', class_='b-fight-details__table-text')
            row_data.append(str_texts[0].text.strip() if len(str_texts) > 0 else '')
            row_data.append(str_texts[1].text.strip() if len(str_texts) > 1 else '')

            # Td
            td_texts = cols[4].find_all('p', class_='b-fight-details__table-text')
            row_data.append(td_texts[0].text.strip() if len(td_texts) > 0 else '')
            row_data.append(td_texts[1].text.strip() if len(td_texts) > 1 else '')

            # Sub
            sub_texts = cols[5].find_all('p', class_='b-fight-details__table-text')
            row_data.append(sub_texts[0].text.strip() if len(sub_texts) > 0 else '')
            row_data.append(sub_texts[1].text.strip() if len(sub_texts) > 1 else '')

            # Event Name and Date
            event_links = cols[6].find_all('a', class_=['b-link_style_white', 'b-link_style_black'])
            event_name = event_links[0].text.strip() if len(event_links) > 0 else ''
            
            # Extract event date more robustly
            event_date = ''
            event_date_p_tags = cols[6].find_all('p', class_='b-fight-details__table-text')
            for p_tag in event_date_p_tags:
                text = p_tag.text.strip()
                if any(month in text for month in ['Jan.', 'Feb.', 'Mar.', 'Apr.', 'May.', 'Jun.', 'Jul.', 'Aug.', 'Sep.', 'Oct.', 'Nov.', 'Dec.']):
                    event_date = text
                    break
            row_data.extend([event_name, event_date])

            # Method
            method_texts = [p.text.strip() for p in cols[7].find_all('p', class_='b-fight-details__table-text') if p.text.strip()]
            method = method_texts[0] if len(method_texts) > 0 else ''
            method_details = method_texts[1] if len(method_texts) > 1 else ''
            row_data.append(f"{method} ({method_details})" if method_details else method)

            # Round
            round_text = cols[8].find('p', class_='b-fight-details__table-text').text.strip() if cols[8].find('p', class_='b-fight-details__table-text') else ''
            row_data.append(round_text)

            # Time
            time_text = cols[9].find('p', class_='b-fight-details__table-text').text.strip() if cols[9].find('p', class_='b-fight-details__table-text') else ''
            row_data.append(time_text)
        
        data.append(row_data)

    df = pd.DataFrame(data, columns=expected_headers)
    return df

def get_ufc_html_files(base_dir=PAGES_DIR):
    """
    Walks through the directory and finds ufcstats.com fighter detail HTML files.
    """
    ufc_html_files = []
    for root, dirs, files in os.walk(base_dir):
        print(f'Root: {dirs}')
        for file in files:
            # Check for fighter detail pages based on the naming convention
            # Example: 'ufcstats.com--fighter-details-0aa74d04c196800c-1757309158-a1daad04.md'
            if "ufcstats.com--fighter-details-" in file and file.endswith(".html"):
                ufc_html_files.append(os.path.join(root, file))
    return ufc_html_files

def create_ufc_dataframe():
    """
    Creates a pandas DataFrame from extracted UFC fighter details and fight history.
    """
    all_fighter_details = []
    all_fight_history = []
    ufc_files = get_ufc_html_files()

    if not ufc_files:
        print(f"No UFC HTML files found in {PAGES_DIR}. Please ensure files are present.")
        return pd.DataFrame(), pd.DataFrame() # Return two empty DataFrames

    for file_path in ufc_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            fighter_details = extract_fighter_details(html_content)
            if fighter_details:
                all_fighter_details.append(fighter_details)

            fight_history_df = extract_fight_history(html_content)
            if not fight_history_df.empty:
                # Add fighter name to each row of fight history for context
                fighter_name = fighter_details.get('Fighter Name', 'Unknown Fighter')
                fight_history_df['Fighter Name'] = fighter_name
                all_fight_history.append(fight_history_df)

        except Exception as e:
            print(f"Error processing file {file_path}: {e}")
            
    fighters_df = pd.DataFrame(all_fighter_details)
    
    # Concatenate all fight history DataFrames
    if all_fight_history:
        fights_df = pd.concat(all_fight_history, ignore_index=True)
    else:
        fights_df = pd.DataFrame()

    # Convert relevant columns to numeric in fights_df, coercing errors to NaN
    numeric_cols_fights = ['Kd 1', 'Kd 2', 'Str 1', 'Str 2', 'Td 1', 'Td 2', 'Sub 1', 'Sub 2', 'Round']
    for col in numeric_cols_fights:
        if col in fights_df.columns:
            fights_df[col] = pd.to_numeric(fights_df[col], errors='coerce')
            # Impute missing numerical values with 0 for fight stats
            fights_df[col] = fights_df[col].fillna(0)

    return fighters_df, fights_df

if __name__ == '__main__':
    # Example usage:
    ufc_fighters_df, ufc_fights_df = create_ufc_dataframe()
    if not ufc_fighters_df.empty:
        print("\nUFC Fighter Details DataFrame:")
        print(ufc_fighters_df.head())
        print(f"Total UFC fighters extracted: {len(ufc_fighters_df)}")
    else:
        print("No UFC fighter data to display.")

    if not ufc_fights_df.empty:
        print("\nUFC Fight History DataFrame:")
        print(ufc_fights_df.head())
        print(f"Total UFC fights extracted: {len(ufc_fights_df)}")
    else:
        print("No UFC fight history data to display.")
