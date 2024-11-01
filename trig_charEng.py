import time
import gspread
from google_auth_oauthlib.flow import InstalledAppFlow
import requests
import pickle
import os


class GoogleSheetsHandler:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        self.token_path = 'token.pickle'
        self.client_secrets_path = 'client_secrets.json'
        self.spreadsheet_id = '1p2pRyckjg0kgzwDjxV7fPOhNQh2YvxFSjRpeDJVXWpA'
        self.webhook_url = "https://hook.us2.make.com/q65bb1myb56hxep1dpbq3we96tbdtfu6"

    def get_credentials(self):
        creds = None
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                creds = pickle.load(token)
        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(
                self.client_secrets_path, self.SCOPES)
            creds = flow.run_local_server(port=0)
            with open(self.token_path, 'wb') as token:
                pickle.dump(creds, token)
        return creds

    def initialize_sheet(self):
        creds = self.get_credentials()
        sheets_client = gspread.authorize(creds)
        return sheets_client.open_by_key(self.spreadsheet_id).sheet1

    def check_ready_signal(self, sheet):
        return sheet.acell('D1').value == 'ready'

    def send_to_make(self, row_data, row_index):  # Added row_index parameter
        payload = {
            "column_a": row_data[0] if len(row_data) > 0 else "",
            "column_b": row_data[1] if len(row_data) > 1 else "",
            "column_c": row_data[2] if len(row_data) > 2 else "",
            "row_number": row_index  # Add row number to payload
        }
        response = requests.post(self.webhook_url, json=payload, headers={
                                 'Content-Type': 'application/json'})
        return response.status_code == 200

    def clear_sheet(self, sheet):
        sheet.clear()


def send_to_make(self, row_data, row_index):  # Added row_index parameter
    payload = {
        "column_a": row_data[0] if len(row_data) > 0 else "",
        "column_b": row_data[1] if len(row_data) > 1 else "",
        "column_c": row_data[2] if len(row_data) > 2 else "",
        "row_number": row_index  # Add row number to payload
    }
    response = requests.post(self.webhook_url, json=payload, headers={
        'Content-Type': 'application/json'})
    return response.status_code == 200


def monitor_and_process(sheet_handler):
    sheet = sheet_handler.initialize_sheet()
    while True:
        if sheet_handler.check_ready_signal(sheet):
            print("Found 'ready' signal. Processing sheet data...")
            data = sheet.get_all_values()
            if len(data) > 1:
                # Start from 2 to account for header
                for index, row in enumerate(data[1:], start=2):
                    if any(row[:3]):  # Check if there's content in columns A-C
                        success = sheet_handler.send_to_make(row[:3], index)
                        if success:
                            print(f"Data sent successfully for row {index}")
                        else:
                            print(f"Failed to send data for row {index}")
                sheet_handler.clear_sheet(sheet)
                print("Sheet cleared.")
            else:
                print("No data to process.")
        else:
            print("Waiting for 'ready' signal in D1.")
        time.sleep(15)


if __name__ == "__main__":
    handler = GoogleSheetsHandler()
    monitor_and_process(handler)
