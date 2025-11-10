# Google Sheets Setup Instructions

## Prerequisites
1. A Google account
2. Python 3.7 or higher

## Step 1: Install Required Packages
```bash
pip install -r requirements.txt
```

## Step 2: Create Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Google Sheets API** and **Google Drive API**:
   - Go to "APIs & Services" > "Library"
   - Search for "Google Sheets API" and enable it
   - Search for "Google Drive API" and enable it

## Step 3: Create Service Account
1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "Service Account"
3. Fill in the service account details:
   - Name: `log-scraper` (or any name you prefer)
   - Click "Create and Continue"
   - Skip the optional steps and click "Done"

## Step 4: Create and Download Key
1. Click on the service account you just created
2. Go to the "Keys" tab
3. Click "Add Key" > "Create new key"
4. Select "JSON" format
5. Click "Create" - this will download a JSON file
6. **Rename this file to `credentials.json`** and place it in the same directory as `video.py`

## Step 5: Create Google Sheet
1. Go to [Google Sheets](https://sheets.google.com/)
2. Create a new spreadsheet
3. Name it "Log Data" (or change `GOOGLE_SHEET_NAME` in the code)
4. Note the worksheet name (default is "Sheet1", or change `GOOGLE_WORKSHEET_NAME` in the code)

## Step 6: Share Sheet with Service Account
1. In your Google Sheet, click the "Share" button
2. Get the service account email from the `credentials.json` file:
   - Open `credentials.json`
   - Find the `client_email` field (looks like: `your-service-account@project-id.iam.gserviceaccount.com`)
3. Paste this email in the "Share" dialog
4. Give it "Editor" permissions
5. Click "Send" (you can uncheck "Notify people" if you want)

## Step 7: Configure the Script
Edit `video.py` and update these variables if needed:
```python
GOOGLE_SHEETS_CREDENTIALS_FILE = 'credentials.json'  # Path to your JSON key file
GOOGLE_SHEET_NAME = 'Log Data'  # Name of your Google Sheet
GOOGLE_WORKSHEET_NAME = 'Sheet1'  # Name of the worksheet/tab
```

## Step 8: Run the Script
```bash
python video.py
```

The script will:
- Refresh the page every 5 minutes
- Search for matching elements
- Compare with existing data in Google Sheets
- Upload only new entries (no duplicates)

## Troubleshooting

### "Error initializing Google Sheets"
- Make sure `credentials.json` is in the same directory as the script
- Verify the service account email has access to the sheet
- Check that Google Sheets API and Drive API are enabled

### "Permission denied" errors
- Make sure you shared the Google Sheet with the service account email
- Verify the service account has "Editor" permissions

### "Sheet not found"
- Check that `GOOGLE_SHEET_NAME` matches exactly (case-sensitive)
- Verify the sheet is shared with the service account

