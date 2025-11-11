from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time, re
from urllib.parse import urlparse, parse_qs, unquote, urlunparse
import json
import csv
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# Google Sheets Configuration
# You need to:
# 1. Create a Google Cloud Project
# 2. Enable Google Sheets API
# 3. Create a service account and download the JSON key file
# 4. Share your Google Sheet with the service account email
# 5. Set these variables:
GOOGLE_SHEETS_CREDENTIALS_FILE = 'credentials.json'  # Path to your service account JSON file
GOOGLE_SHEET_NAME = 'Log Data'  # Name of your Google Sheet
GOOGLE_WORKSHEET_NAME = 'Vali0'  # Name of the worksheet/tab

def init_google_sheets():
    """Initialize Google Sheets connection"""
    print("\n--- Initializing Google Sheets Connection ---")
    try:
        # Check if credentials file exists
        import os
        if not os.path.exists(GOOGLE_SHEETS_CREDENTIALS_FILE):
            print(f"❌ ERROR: Credentials file '{GOOGLE_SHEETS_CREDENTIALS_FILE}' not found!")
            print("Please create a service account and download the JSON key file.")
            return None
        
        print(f"✓ Found credentials file: {GOOGLE_SHEETS_CREDENTIALS_FILE}")
        
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        print("Loading credentials...")
        creds = Credentials.from_service_account_file(GOOGLE_SHEETS_CREDENTIALS_FILE, scopes=scope)
        print("✓ Credentials loaded successfully")
        
        print("Authorizing with Google Sheets API...")
        client = gspread.authorize(creds)
        print("✓ Authorization successful")
        
        print(f"Opening Google Sheet: '{GOOGLE_SHEET_NAME}'...")
        spreadsheet = client.open(GOOGLE_SHEET_NAME)
        print(f"✓ Sheet found: {spreadsheet.title}")
        
        print(f"Opening worksheet: '{GOOGLE_WORKSHEET_NAME}'...")
        sheet = spreadsheet.worksheet(GOOGLE_WORKSHEET_NAME)
        print(f"✓ Worksheet found: {sheet.title}")
        
        # Test read access
        try:
            test_values = sheet.get_all_values()
            print(f"✓ Test read successful. Sheet has {len(test_values)} rows")
        except Exception as e:
            print(f"⚠ Warning: Could not read sheet data: {e}")
        
        print("✓✓✓ Google Sheets initialized successfully! ✓✓✓\n")
        return sheet
        
    except FileNotFoundError:
        print(f"❌ ERROR: Credentials file '{GOOGLE_SHEETS_CREDENTIALS_FILE}' not found!")
        print("Please create a service account and download the JSON key file.")
        return None
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"❌ ERROR: Google Sheet '{GOOGLE_SHEET_NAME}' not found!")
        print("Please check:")
        print("1. The sheet name is correct (case-sensitive)")
        print("2. The sheet is shared with the service account email")
        return None
    except gspread.exceptions.WorksheetNotFound:
        print(f"❌ ERROR: Worksheet '{GOOGLE_WORKSHEET_NAME}' not found in '{GOOGLE_SHEET_NAME}'!")
        print("Please check the worksheet name (case-sensitive)")
        return None
    except Exception as e:
        print(f"❌ ERROR initializing Google Sheets: {e}")
        import traceback
        traceback.print_exc()
        print("\nTroubleshooting:")
        print("1. Make sure credentials.json exists and is valid")
        print("2. Verify the Google Sheet is shared with the service account email")
        print("3. Check that GOOGLE_SHEET_NAME and GOOGLE_WORKSHEET_NAME are correct")
        return None

def get_last_timestamp_from_sheet(sheet):
    """Get the timestamp from the last row in Google Sheets"""
    try:
        # Get all values from the sheet
        all_values = sheet.get_all_values()
        if len(all_values) <= 1:  # Only header row or empty
            return None
        
        # Timestamp is in column index 1 (2nd column)
        # Get the last row (excluding header)
        last_row = all_values[-1]
        if len(last_row) > 1 and last_row[1]:  # If timestamp column has a value
            return last_row[1].strip()
        return None
    except Exception as e:
        print(f"Error reading last timestamp: {e}")
        return None

def compare_timestamps(timestamp1, timestamp2):
    """Compare two timestamps. Returns True if timestamp1 > timestamp2 (timestamp1 is newer)"""
    if not timestamp1 or not timestamp2:
        return True  # If either is missing, allow upload
    
    try:
        # Parse timestamps in format: YYYY-MM-DD HH:MM:SS.mmm
        from datetime import datetime
        # Remove milliseconds for comparison if present
        ts1_clean = timestamp1.split('.')[0] if '.' in timestamp1 else timestamp1
        ts2_clean = timestamp2.split('.')[0] if '.' in timestamp2 else timestamp2
        
        dt1 = datetime.strptime(ts1_clean, '%Y-%m-%d %H:%M:%S')
        dt2 = datetime.strptime(ts2_clean, '%Y-%m-%d %H:%M:%S')
        
        return dt1 >= dt2
    except Exception as e:
        print(f"Error comparing timestamps: {e}")
        # If parsing fails, allow upload to be safe
        return True

def should_skip_message(message):
    """Check if message should be skipped based on content"""
    if not message:
        return False
    
    skip_patterns = [
        "Compression data successfully sent to dashboard",
        "Updating miner manager with 5 compression miner scores after synthetic requests processing",
        "Synthetic compression scoring results for 5 miners",
        "Uids:"
    ]
    
    for pattern in skip_patterns:
        if pattern in message:
            return True
    return False

def upload_single_result_to_google_sheets(sheet, result, last_timestamp=None):
    """Upload a single result to Google Sheets immediately, checking if timestamp is newer than last row"""
    if sheet is None:
        return False
    
    if result is None:
        return False
    
    try:
        line_number = str(result['line_number'])
        current_timestamp = str(result['timestamp']) if result['timestamp'] else ''
        full_text = str(result['full_text']) if result['full_text'] else ''
        message = str(result.get('message', ''))
        
        # Check if message should be skipped
        if should_skip_message(message):
            print(f"  ⏭ Skipping line {line_number} - message type not needed: {message[:60]}...")
            return False
        
        # Get last timestamp from sheet if not provided
        if last_timestamp is None:
            last_timestamp = get_last_timestamp_from_sheet(sheet)
        
        # Check if current timestamp is newer than last timestamp
        if last_timestamp:
            if not compare_timestamps(current_timestamp, last_timestamp):
                print(f"  ⏭ Skipping line {line_number} - timestamp {current_timestamp} is not newer than last row ({last_timestamp})")
                return False
        
        # Prepare row data
        row = [
            line_number,
            current_timestamp,
            str(result['compression_id']) if result['compression_id'] else '',
            str(result['message']) if result['message'] else '',
            full_text,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Upload timestamp
        ]
        
        # Check if sheet is empty and add header
        all_values = sheet.get_all_values()
        if len(all_values) == 0:
            header = ['Line Number', 'Timestamp', 'Compression ID', 'Message', 'Full Text', 'Uploaded At']
            sheet.append_row(header)
        
        # Upload the single row
        sheet.append_row(row)
        
        print(f"  ✓ Uploaded line {line_number} (timestamp: {current_timestamp}) to Google Sheets")
        return True
        
    except Exception as e:
        print(f"  ❌ Error uploading line {result.get('line_number', 'unknown')} to Google Sheets: {e}")
        return False

def upload_to_google_sheets(sheet, new_results):
    """Upload new results to Google Sheets"""
    if sheet is None:
        print("ERROR: Google Sheets not initialized. Cannot upload.")
        return
    
    if not new_results:
        print("No new data to upload.")
        return
    
    try:
        print(f"\n--- Google Sheets Upload Process ---")
        print(f"Total results to check: {len(new_results)}")
        
        # Get last timestamp from Google Sheets
        print("Reading last timestamp from Google Sheets...")
        last_timestamp = get_last_timestamp_from_sheet(sheet)
        if last_timestamp:
            print(f"Last timestamp in sheet: {last_timestamp}")
        else:
            print("Sheet is empty or has no timestamp. Will upload all results.")
        
        # Filter results - only upload if timestamp is newer than last row and message is not skipped
        to_upload = []
        for r in new_results:
            message = str(r.get('message', ''))
            # Skip unwanted message types
            if should_skip_message(message):
                continue
            
            current_ts = str(r.get('timestamp', '')).strip()
            if not last_timestamp or compare_timestamps(current_ts, last_timestamp):
                to_upload.append(r)
        
        if not to_upload:
            print("All data already exists in Google Sheets. No new entries to upload.")
            return
        
        print(f"Found {len(to_upload)} new entries to upload (out of {len(new_results)} total)")
        
        # Prepare data for upload
        rows_to_add = []
        for result in to_upload:
            row = [
                str(result['line_number']),
                str(result['timestamp']) if result['timestamp'] else '',
                str(result['compression_id']) if result['compression_id'] else '',
                str(result['message']) if result['message'] else '',
                str(result['full_text']) if result['full_text'] else '',
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Upload timestamp
            ]
            rows_to_add.append(row)
        
        # Check if sheet is empty and add header
        all_values = sheet.get_all_values()
        if len(all_values) == 0:
            print("Sheet is empty. Adding header row...")
            header = ['Line Number', 'Timestamp', 'Compression ID', 'Message', 'Full Text', 'Uploaded At']
            sheet.append_row(header)
            print("Header added successfully.")
        
        # Append new rows in batches (Google Sheets has limits)
        batch_size = 100
        total_uploaded = 0
        
        for i in range(0, len(rows_to_add), batch_size):
            batch = rows_to_add[i:i+batch_size]
            print(f"Uploading batch {i//batch_size + 1} ({len(batch)} rows)...")
            sheet.append_rows(batch)
            total_uploaded += len(batch)
            print(f"  ✓ Uploaded {total_uploaded}/{len(rows_to_add)} rows")
            time.sleep(0.5)  # Small delay between batches
        
        print(f"\n✓✓✓ SUCCESS: Uploaded {total_uploaded} new entries to Google Sheets ✓✓✓")
        
    except Exception as e:
        print(f"\n❌ ERROR uploading to Google Sheets: {e}")
        import traceback
        traceback.print_exc()
        print("\nTroubleshooting tips:")
        print("1. Check if credentials.json exists and is valid")
        print("2. Verify the Google Sheet is shared with the service account email")
        print("3. Check that GOOGLE_SHEET_NAME and GOOGLE_WORKSHEET_NAME are correct")

def scrape_data(driver, wait, sheet=None):
    """Scrape data from the webpage and upload to Google Sheets immediately"""
    print("\n" + "="*60)
    print(f"Starting data scrape at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Get last timestamp from Google Sheets for comparison
    last_timestamp = None
    if sheet:
        print("Loading last timestamp from Google Sheets...")
        last_timestamp = get_last_timestamp_from_sheet(sheet)
        if last_timestamp:
            print(f"Last timestamp in sheet: {last_timestamp}")
        else:
            print("Sheet is empty or has no timestamp. Will upload all new entries.")
    
    # Refresh the page
    print("Refreshing page...")
    driver.refresh()
    time.sleep(3)
    
    # Search for the key
    try:
        print("Setting up search...")
        input_element = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[placeholder='Search']")))
        print("Search input found. Clearing and typing...")
        input_element.clear()
        print("Cleared. Typing search query...")
        input_element.send_keys("| INFO     | __main__:score_compressions:")
        print("Search query typed. Waiting for page to update...")
        time.sleep(1)
        
        # Click the "go to next match" button to start
        next_match_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='go to next match']")))
        next_match_button.click()
        time.sleep(2)
    except Exception as e:
        print(f"Error setting up search: {e}")
        return []
    
    results = []
    processed_line_numbers = set()
    match_count = 0
    upload_count = 0
    
    # Loop through all matches by clicking next button
    while True:
        try:
            match_count += 1
            print(f"\nProcessing match #{match_count}...")
            
            # Wait for the page to update
            time.sleep(0.5)
            
            # Find the highlighted element - wait for it before proceeding
            try:
                # Find the highlighted span with the specific background color
                try:
                    current_element = wait.until(
                        EC.presence_of_element_located((By.XPATH, "//span[contains(@style,'background-color:rgb(255,215,0)') and contains(., '__main__:score_compressions:')]"))
                    )
                except Exception:
                    # Fallback: any highlighted span containing the pattern
                    current_element = wait.until(
                        EC.presence_of_element_located((By.XPATH, "//span[contains(@style,'background-color') and contains(., '__main__:score_compressions:')]"))
                    )
                
                # Scroll element into view
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", current_element)
                time.sleep(0.5)
                
                # Get the parent row element
                row_element = current_element.find_element(By.XPATH, "./ancestor::div[@role='row']")
                
                # Extract line number
                line_number_elem = row_element.find_element(By.CSS_SELECTOR, "span[aria-label='line number']")
                line_number = line_number_elem.text.strip()
                
                # Skip if already processed
                if line_number in processed_line_numbers:
                    print(f"Skipping duplicate line {line_number}")
                else:
                    processed_line_numbers.add(line_number)
                    
                    # Extract the full text content
                    text_content = row_element.find_element(By.CSS_SELECTOR, "span.break-all").text.strip()
                    
                    # Replace &nbsp; and non-breaking spaces with regular spaces
                    text_content = text_content.replace('\xa0', ' ').replace('&nbsp;', ' ')
                    
                    # Extract timestamp
                    timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})', text_content)
                    timestamp = timestamp_match.group(1) if timestamp_match else None
                    
                    # Extract the message after the INFO pattern
                    message_match = re.search(r'__main__:score_compressions:(\d+)\s*-\s*(.+)', text_content)
                    compression_id = message_match.group(1) if message_match else None
                    message = message_match.group(2) if message_match else None
                    
                    # Store the result
                    result = {
                        "line_number": line_number,
                        "timestamp": timestamp,
                        "compression_id": compression_id,
                        "message": message,
                        "full_text": text_content
                    }
                    results.append(result)
                    print(f"✓ Extracted line {line_number}: {message[:50] if message else 'N/A'}...")
                    
                    # Check if message should be skipped before uploading
                    if should_skip_message(message):
                        print(f"  ⏭ Skipping line {line_number} - message type not needed: {message[:60]}...")
                    # Upload to Google Sheets immediately (before clicking next)
                    elif sheet:
                        # Check if timestamp is newer than last row
                        current_ts = str(result.get('timestamp', '')).strip()
                        if not last_timestamp or compare_timestamps(current_ts, last_timestamp):
                            uploaded = upload_single_result_to_google_sheets(sheet, result, last_timestamp)
                            if uploaded:
                                upload_count += 1
                                # Update last_timestamp after successful upload
                                last_timestamp = current_ts
                                print(f"  Updated last timestamp to: {last_timestamp}")
                        else:
                            print(f"  ⏭ Skipping line {line_number} - timestamp {current_ts} is not newer than last row ({last_timestamp})")
            
            except Exception as e:
                print(f"Error finding current element: {e}")
            
            # Check match counter to see if we're at the last match
            try:
                match_counter = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "span.ml-8.font-semibold"))
                )
                match_text = match_counter.text.strip()
                print(f"Match counter: {match_text}")
                
                if "/" in match_text:
                    current, total = match_text.split("/")
                    current_num = int(current.strip())
                    total_num = int(total.strip())
                    
                    # If current equals total, we're at the last match
                    if current_num == total_num:
                        print(f"Reached last match ({current_num}/{total_num}). Finished collecting.")
                        break
                    else:
                        print(f"Match {current_num} of {total_num} - continuing...")
            except Exception as counter_error:
                print(f"Warning: Could not find match counter: {counter_error}")
            
            # Click next button to move to next match
            try:
                next_match_button = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "button[aria-label='go to next match']"))
                )
                
                print("Clicking next button...")
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", next_match_button)
                time.sleep(0.3)
                
                try:
                    next_match_button.click()
                except:
                    driver.execute_script("arguments[0].click();", next_match_button)
                
                print("Next button clicked. Waiting for next match...")
                time.sleep(0.5)
                
            except Exception as btn_error:
                print(f"Could not find or click next button: {btn_error}. Finished collecting.")
                break
        
        except Exception as e:
            print(f"Error in loop: {e}")
            break
    
    print(f"\nScraping complete! Found {len(results)} matching elements.")
    if sheet:
        print(f"Uploaded {upload_count} new entries to Google Sheets during scraping.")
    return results

def list_available_sheets():
    """List all available Google Sheets that the service account can access"""
    print("\n" + "="*60)
    print("LISTING AVAILABLE GOOGLE SHEETS")
    print("="*60)
    try:
        import os
        if not os.path.exists(GOOGLE_SHEETS_CREDENTIALS_FILE):
            print(f"❌ ERROR: Credentials file '{GOOGLE_SHEETS_CREDENTIALS_FILE}' not found!")
            return
        
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_file(GOOGLE_SHEETS_CREDENTIALS_FILE, scopes=scope)
        client = gspread.authorize(creds)
        
        print("Fetching all accessible spreadsheets...")
        spreadsheets = client.openall()
        
        if not spreadsheets:
            print("\n❌ No spreadsheets found!")
            print("This means the service account doesn't have access to any sheets.")
            print("\nTo fix this:")
            print("1. Open your Google Sheet")
            print("2. Click 'Share' button")
            print("3. Get the service account email from credentials.json (look for 'client_email')")
            print("4. Share the sheet with that email address")
            return
        
        print(f"\n✓ Found {len(spreadsheets)} accessible spreadsheet(s):\n")
        for i, ss in enumerate(spreadsheets, 1):
            print(f"{i}. '{ss.title}' (ID: {ss.id})")
            try:
                worksheets = ss.worksheets()
                print(f"   Worksheets: {', '.join([ws.title for ws in worksheets])}")
            except:
                print("   (Could not list worksheets)")
            print()
        
        print("\nTo use a sheet, update GOOGLE_SHEET_NAME in video.py with the exact name above.")
        
    except Exception as e:
        print(f"❌ Error listing sheets: {e}")
        import traceback
        traceback.print_exc()

def test_google_sheets_connection():
    """Test function to verify Google Sheets connection"""
    print("\n" + "="*60)
    print("TESTING GOOGLE SHEETS CONNECTION")
    print("="*60)
    sheet = init_google_sheets()
    if sheet:
        print("\n✓ Connection test successful!")
        try:
            values = sheet.get_all_values()
            print(f"Current rows in sheet: {len(values)}")
            if len(values) > 0:
                print(f"Header row: {values[0]}")
                if len(values) > 1:
                    print(f"Sample data row: {values[1]}")
        except Exception as e:
            print(f"Could not read sheet data: {e}")
        return True
    else:
        print("\n❌ Connection test failed!")
        print("\nTroubleshooting:")
        print("1. Run: python video.py --list-sheets")
        print("   This will show all sheets accessible to the service account")
        print("2. Make sure the sheet is shared with the service account email")
        print("3. Check that GOOGLE_SHEET_NAME matches exactly (case-sensitive)")
        return False

def main():
    """Main function that runs the scraper in a loop"""
    # Initialize Google Sheets
    print("\n" + "="*60)
    print("STARTING LOG SCRAPER WITH GOOGLE SHEETS INTEGRATION")
    print("="*60)
    
    sheet = init_google_sheets()
    if sheet is None:
        print("\n⚠⚠⚠ WARNING: Google Sheets not initialized. Data will only be saved locally. ⚠⚠⚠")
        print("To enable Google Sheets upload:")
        print("1. Follow the setup instructions in README_GOOGLE_SHEETS_SETUP.md")
        print("2. Make sure credentials.json exists in the same directory")
        print("3. Share your Google Sheet with the service account email\n")
    else:
        print("\n✓ Google Sheets ready for uploads!\n")
    
    # Initialize Selenium
    driver = webdriver.Chrome()
    driver.maximize_window()
    driver.get("https://wandb.ai/vidaio_vidaio/sn85-validators/runs/amd00p3w/logs")
    wait = WebDriverWait(driver, 10)
    
    # Wait for initial page load
    time.sleep(3)
    
    iteration = 0
    while True:
        try:
            iteration += 1
            print(f"\n{'='*60}")
            print(f"ITERATION #{iteration}")
            print(f"{'='*60}")
            
            # Scrape data (uploads to Google Sheets immediately as it finds each element)
            results = scrape_data(driver, wait, sheet)
            
            if results:
                # Save to local JSON file
                with open('info_logs.json', 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
                print(f"Saved {len(results)} entries to info_logs.json")
                
                # Note: Data is already uploaded to Google Sheets during scraping
                # The upload_to_google_sheets function is kept for batch uploads if needed
            
            # Wait 5 minutes before next iteration
            print(f"\nWaiting 30 seconds before next refresh...")
            next_time = datetime.fromtimestamp(datetime.now().timestamp() + 30)
            print(f"Next scrape will start at {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
            time.sleep(30)  # 5 minutes = 300 seconds
            
        except KeyboardInterrupt:
            print("\nStopped by user.")
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            import traceback
            traceback.print_exc()
            print("Waiting 5 minutes before retry...")
            time.sleep(300)
    
    driver.quit()

if __name__ == "__main__":
    import sys
    
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            test_google_sheets_connection()
        elif sys.argv[1] == "--list-sheets":
            list_available_sheets()
        else:
            print(f"Unknown argument: {sys.argv[1]}")
            print("Usage:")
            print("  python video.py           - Run the scraper")
            print("  python video.py --test    - Test Google Sheets connection")
            print("  python video.py --list-sheets - List all accessible sheets")
    else:
        main()
