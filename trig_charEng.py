import time
import gspread
from google_auth_oauthlib.flow import InstalledAppFlow
import requests
import json
from googleapiclient.discovery import build
from google.oauth2 import service_account

# Google Sheets Setup
scope = ["https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive"]
flow = InstalledAppFlow.from_client_secrets_file(
    "client_secrets.json", scopes=scope)
creds = flow.run_local_server(port=0)
client = gspread.authorize(creds)
sheet = client.open_by_key(
    "1p2pRyckjg0kgzwDjxV7fPOhNQh2YvxFSjRpeDJVXWpA").sheet1

# Google Drive Setup
drive_creds = creds
drive_service = build('drive', 'v3', credentials=drive_creds)

# Function to check if 'done' file exists in Google Drive folder


def is_done_file_present(folder_id):
    try:
        query = f"'{folder_id}' in parents and name = 'done' and trashed = false"
        results = drive_service.files().list(q=query).execute()
        files = results.get('files', [])
        print(f"Files in folder: {[file['name'] for file in files]}")
        return len(files) > 0
    except Exception as e:
        print(f"Error checking for 'done' file: {e}")
        return False

# Function to manually trigger a process (Make.com scenario)


def trigger_make_scenario(row_data, row_index):
    try:
        url = "https://hook.us2.make.com/q65bb1myb56hxep1dpbq3we96tbdtfu6"
        payload = {
            "row_number": row_index,
            "column_a": row_data[0] if len(row_data) > 0 else "",
            "column_b": row_data[1] if len(row_data) > 1 else "",
            "row_data": row_data
        }
        json_payload = json.dumps(payload)
        response = requests.post(url, data=json_payload, headers={
                                 'Content-Type': 'application/json'}, timeout=10)
        print(
            f"Make.com scenario response: {response.status_code}, {response.text}")
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"Error triggering Make.com scenario: {e}")
        return False


# Main Loop
folder_id = "1AUhNcZtlc0R5WUAaOfZkU21_TV9NcbeP"

while True:
    try:
        print("Checking for 'done' file in Google Drive...")
        if not is_done_file_present(folder_id):
            print("No 'done' file found, ready for new processing.")
            data = sheet.get_all_values()
            if len(data) > 1:
                for i, row in enumerate(data[1:], start=2):  # Skip header row
                    if any(row):
                        print(
                            f"New data found in row {i}, triggering Make.com scenario...")
                        success = trigger_make_scenario(
                            row, i)  # Pass row index as well
                        if success:
                            print(
                                f"Make.com scenario triggered successfully for row {i}.")
                        else:
                            print(
                                f"Failed to trigger Make.com scenario for row {i}.")
                # Clear the content of the sheet after processing all rows
                sheet.clear()
                print("Sheet content cleared after processing.")
            else:
                print("No new data found in Google Sheet.")
        else:
            print("'done' file found, waiting for it to be deleted...")

    except Exception as e:
        print(f"Error in main loop: {e}")

    # Wait for 15 seconds before checking again
    print("Waiting for the next check...")
    time.sleep(15)
