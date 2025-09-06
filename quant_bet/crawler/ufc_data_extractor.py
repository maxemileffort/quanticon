import os
from bs4 import BeautifulSoup
import pandas as pd

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

def get_ufc_html_files(directory_path):
    ufc_files = []
    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.startswith('ufcstats.com--fighter-details') and file.endswith('.html'):
                ufc_files.append(os.path.join(root, file))
    return ufc_files

if __name__ == '__main__':
    base_path = 'quanticon/quant_bet/crawler/pages'
    
    # Get all UFC fighter detail HTML files
    ufc_html_files = get_ufc_html_files(base_path)

    if ufc_html_files:
        print(f"Found {len(ufc_html_files)} UFC fighter detail files.")
        # Process the first file as an example
        file_path = ufc_html_files[0]
        print(f"\nProcessing file: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        fighter_details = extract_fighter_details(html_content)
        print("\nFighter Details:")
        for key, value in fighter_details.items():
            print(f"{key}: {value}")

        fight_history_df = extract_fight_history(html_content)
        print("\nFight History:")
        # Use to_string() with a wider display to prevent truncation
        print(fight_history_df.to_string(index=False, max_colwidth=50))
    else:
        print(f"No UFC fighter detail HTML files found in {base_path}")
