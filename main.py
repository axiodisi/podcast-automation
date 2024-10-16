from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import gspread
import os

# Scopes for Google Sheets and Drive
SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
          'https://www.googleapis.com/auth/drive.file']

# File to store tokens
TOKEN_FILE = 'token.json'


def get_authenticated_service():
    creds = None
    # Check if token.json exists for storing the OAuth tokens
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # If there are no valid credentials available, log in using OAuth
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Replace 'client_secrets.json' with the OAuth credentials file you download
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secrets.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for future runs
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    return creds


def access_google_sheets(sheet_id, worksheet_name):
    # Authenticate and get access to Google Sheets API
    creds = get_authenticated_service()
    client = gspread.authorize(creds)

    # Open the Google Sheet by ID
    sheet = client.open_by_key(sheet_id).worksheet(worksheet_name)

    # Read the data from A1 and B1
    title = sheet.acell('A1').value
    description = sheet.acell('B1').value

    # If both A1 and B1 have data, process it
    if title and description:
        print(f"Title: {title}\nDescription: {description}")

        # Clear the data from A1 and B1 after reading
        sheet.update([['']], 'A1')
        sheet.update([['']], 'B1')
        print("A1 and B1 have been cleared for the next entry.")
    else:
        print("A1 and B1 are empty. Nothing to process.")


if __name__ == "__main__":
    # Example Google Sheet ID and Worksheet Name
    # Replace with your Google Sheet ID
    SHEET_ID = '19R0p9Ps-4A3_9eU_dy5ZiGyF_FwLyued9TsZpYkZVpg'
    WORKSHEET_NAME = 'Sheet1'  # Replace with your worksheet name

    # Access Google Sheets
    access_google_sheets(SHEET_ID, WORKSHEET_NAME)

    print("Script completed successfully")
