import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo # Standard in Python 3.9+

def fetch_high_impact_news(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        
        # Header (Updated label to CST)
        print(f"{'DATE':<12} | {'TIME (CST)':<10} | {'CUR':<4} | {'EVENT'}")
        print("-" * 70)

        event_count = 0
        for event in root.findall('event'):
            impact = event.find('impact').text.strip() if event.find('impact') is not None else ""
            
            if impact == "High":
                title = event.find('title').text.strip() if event.find('title') is not None else "N/A"
                country = event.find('country').text.strip() if event.find('country') is not None else "N/A"
                date_str = event.find('date').text.strip() if event.find('date') is not None else ""
                time_str = event.find('time').text.strip() if event.find('time') is not None else ""

                # --- TIMEZONE FIX START ---
                try:
                    # 1. Combine and parse (assuming format '01-28-2026' and '9:00am')
                    # Note: You may need to adjust the format string if the XML uses different separators
                    full_dt_str = f"{date_str} {time_str}"
                    utc_dt = datetime.strptime(full_dt_str, "%m-%d-%Y %I:%M%p").replace(tzinfo=ZoneInfo("UTC"))
                    
                    # 2. Convert to Central Time (handles CST/CDT automatically)
                    cst_dt = utc_dt.astimezone(ZoneInfo("America/Chicago"))

                    if cst_dt < datetime.today():
                        continue
                    
                    # 3. Format back to strings for printing
                    display_date = cst_dt.strftime("%m-%d-%Y")
                    display_time = cst_dt.strftime("%I:%M%p").lower()
                except Exception:
                    # Fallback if parsing fails
                    display_date, display_time = date_str, time_str
                # --- TIMEZONE FIX END ---
                
                print(f"{display_date:<12} | {display_time:<10} | {country:<4} | {title}")
                event_count += 1

        if event_count == 0:
            print("No high impact news found for this week.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
    fetch_high_impact_news(FF_URL)