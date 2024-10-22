import os
import time
import shutil
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from google.cloud import storage
import gspread
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from xml.etree import ElementTree as ET
from google.auth.transport.requests import Request
import datetime
from xml.dom import minidom
import xml.etree.ElementTree as ET

# Define the scopes for Google Sheets and Drive access
SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
          'https://www.googleapis.com/auth/drive']

# Path to OAuth2 client credentials JSON file
client_secret_file = 'C:/Users/rocco.DESKTOP-E207F2C/OneDrive/Documents/projects/radioai/podcast-automation/client_secrets.json'

# Path to the folder to monitor
music_folder = r'C:\Users\rocco.DESKTOP-E207F2C\OneDrive\Documents\projects\radioai\output'
archive_folder = os.path.join(music_folder, 'archive')  # Archive folder
rss_file_path = r'C:\Users\rocco.DESKTOP-E207F2C\OneDrive\Documents\projects\radioai\podcast-automation\rss.xml'
COPY_DELAY = 10  # Adjust the delay as needed (in seconds)

# Google Cloud Bucket details
BUCKET_NAME = 'audio-upload-queue'

# Authenticate using OAuth2 flow

# Function to authenticate using OAuth2 and store tokens


def authenticate_gspread():
    creds = None
    token_file = 'token.json'

    # Check if token.json file exists and load credentials
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    # If there are no valid credentials, or the token has expired, refresh or prompt for login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Refresh the token using the refresh token
            creds.refresh(Request())
        else:
            # Authenticate using OAuth flow
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secret_file, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for future use
        with open(token_file, 'w') as token:
            token.write(creds.to_json())

    # Return the authenticated gspread client
    return gspread.authorize(creds)


# Set up gspread authentication
client = authenticate_gspread()

# Use the spreadsheet key from the URL
spreadsheet_key = '1_ecgQw3FI7NoMQwIlaG4OCgbb4zxw4RrHMUeF7FiNho'

# Open the spreadsheet by key and access the correct sheet by name
spreadsheet = client.open_by_key(spreadsheet_key)
# Access the "rad-pod-tit-soc-db" sheet
sheet = spreadsheet.worksheet('rad-pod-tit-soc-db')

# Function to upload file to Google Cloud Storage bucket


def upload_to_bucket(file_path):
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(os.path.basename(file_path))

    print(f"Uploading {file_path} to Google Cloud bucket {BUCKET_NAME}...")
    blob.upload_from_filename(file_path)
    print(f"File {file_path} uploaded successfully to {BUCKET_NAME}.")

# Function to update the RSS feed (rss.xml)


def update_rss_feed(episode_title, episode_description, audio_url):
    try:
        tree = ET.parse(rss_file_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"RSS feed file '{rss_file_path}' not found.")

    root = tree.getroot()
    channel = root.find('channel')

    if channel is None:
        raise ValueError("Invalid RSS format: 'channel' element not found.")

    item = ET.SubElement(channel, 'item')
    title = ET.SubElement(item, 'title')
    title.text = episode_title
    description = ET.SubElement(item, 'description')
    description.text = episode_description
    enclosure = ET.SubElement(
        item, 'enclosure', url=audio_url, length="12345678", type="audio/mpeg")
    pubDate = ET.SubElement(item, 'pubDate')
    pubDate.text = datetime.datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
    guid = ET.SubElement(item, 'guid')
    guid.text = audio_url

    # Write the updated XML back to the file with pretty print
    try:
        rough_string = ET.tostring(root, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        with open(rss_file_path, 'w', encoding='utf-8') as f:
            f.write(reparsed.toprettyxml(indent="    "))
        print(f"RSS feed updated with episode: {episode_title}")
    except Exception as e:
        print(f"Error writing to RSS feed file: {e}")
# Function to commit the updated RSS feed to Git


def commit_to_git():
    try:
        subprocess.run(['git', 'add', rss_file_path], check=True)
        subprocess.run(
            ['git', 'commit', '-m', 'Update RSS feed with new podcast episode'], check=True)
        subprocess.run(['git', 'push'], check=True)
        print("RSS feed changes committed to Git successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error committing changes to Git: {e}")

# Function to add a timestamp, upload to bucket, update RSS feed, and archive the file


def add_timestamp_and_archive(file_path):
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    dir_name, base_name = os.path.split(file_path)
    new_file_name = f"{base_name.split('.')[0]}_{timestamp}.mp3"
    new_file_path = os.path.join(dir_name, new_file_name)

    print(
        f"Delaying for {COPY_DELAY} seconds to allow queue_stream to complete.")
    time.sleep(COPY_DELAY)

    title = sheet.acell('A1').value
    description = sheet.acell('B1').value

    try:
        shutil.move(file_path, new_file_path)
        print(f"Moved file to {new_file_path}")

        upload_to_bucket(new_file_path)
        update_rss_feed(
            title, description, f"http://storage.googleapis.com/{BUCKET_NAME}/{os.path.basename(new_file_path)}")
        commit_to_git()

        shutil.move(new_file_path, os.path.join(
            archive_folder, os.path.basename(new_file_path)))
        print(f"Archived file to {archive_folder}")
    except Exception as e:
        print(f"Error moving, uploading, or archiving file: {e}")

# Event handler for new files in the directory


class NewFileHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(".mp3") and 'stitched_audio' in event.src_path:
            print(f"New file detected: {event.src_path}")
            add_timestamp_and_archive(event.src_path)

# Function to monitor the folder for new files


def monitor_output_folder():
    event_handler = NewFileHandler()
    observer = Observer()
    observer.schedule(event_handler, music_folder, recursive=False)
    observer.start()

    print(f"Monitoring {music_folder} for new files...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    monitor_output_folder()
