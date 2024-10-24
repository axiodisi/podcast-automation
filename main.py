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
import telnetlib

# Define the scopes for Google Sheets and Drive access
SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
          'https://www.googleapis.com/auth/drive']

# Path to OAuth2 client credentials JSON file
client_secret_file = 'C:/Users/rocco.DESKTOP-E207F2C/OneDrive/Documents/projects/radioai/podcast-automation/client_secrets.json'

# Path to the folder to monitor
music_folder = r'C:\Users\rocco.DESKTOP-E207F2C\OneDrive\Documents\projects\radioai\output'
archive_folder = os.path.join(music_folder, 'archive')  # Archive folder
rss_file_path = r'C:\Users\rocco.DESKTOP-E207F2C\OneDrive\Documents\projects\radioai\podcast-automation\rss.xml'
COPY_DELAY = 1  # Adjust the delay as needed (in seconds)

# Google Cloud Bucket details
BUCKET_NAME = 'audio-upload-queue'

# Authenticate using OAuth2 flow


def authenticate_gspread():
    creds = None
    token_file = 'token.json'

    # Check if token.json file exists and load credentials
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    # If there are no valid credentials, or the token has expired, refresh or prompt for login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
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
spreadsheet_key = '1p2pRyckjg0kgzwDjxV7fPOhNQh2YvxFSjRpeDJVXWpA'

# Open the spreadsheet by key and access the correct sheet by name
spreadsheet = client.open_by_key(spreadsheet_key)
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

# Function to add track to Liquidsoap queue


def add_track_to_queue(unix_style_path):
    HOST = "127.0.0.1"  # Telnet server address
    PORT = 1234         # Port defined in Liquidsoap script
    # PASSWORD = "your_secure_password"  # Uncomment if you set a password in Liquidsoap
    try:
        tn = telnetlib.Telnet(HOST, PORT)
        # Uncomment the following lines if you set a password
        # tn.read_until(b"Password: ")
        # tn.write((PASSWORD + "\n").encode('utf-8'))
        command = f'radio_queue.push {unix_style_path}\n'
        tn.write(command.encode('utf-8'))
        tn.close()
        print(f"Added {unix_style_path} to Liquidsoap queue")
    except Exception as e:
        print(f"Error adding track to Liquidsoap queue: {e}")

# Function to move file to archive with timestamp and process further


def add_timestamp_and_archive(file_path):
    # Add timestamp to the filename immediately to prevent overwriting
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    dir_name, base_name = os.path.split(file_path)
    new_file_name = f"{base_name.split('.')[0]}_{timestamp}.mp3"
    new_file_path = os.path.join(archive_folder, new_file_name)

    # Immediately move the file to the archive folder with the new name
    move_successful = False
    while not move_successful:
        try:
            shutil.move(file_path, new_file_path)
            print(f"Moved file to {new_file_path}")
            move_successful = True
        except Exception as e:
            print(f"File is still in use, retrying... Error: {e}")
            time.sleep(1)

    # Convert the Windows path to Unix-style for Liquidsoap
    unix_style_path = new_file_path.replace("\\", "/").replace("C:", "/mnt/c")

    # Add the track to the Liquidsoap queue
    add_track_to_queue(unix_style_path)

    # Proceed to upload the file to the bucket and perform other actions
    try:
        # Upload file to Google Cloud bucket
        upload_to_bucket(new_file_path)

        # Get metadata information from Google Sheet
        title = sheet.acell('A1').value
        description = sheet.acell('B1').value

        # Update RSS feed
        update_rss_feed(
            title, description, f"http://storage.googleapis.com/{BUCKET_NAME}/{os.path.basename(new_file_path)}")

        # Commit changes to Git
        commit_to_git()

        print(f"Archive processing complete for {new_file_path}")

    except Exception as e:
        print(f"Error uploading or processing file: {e}")

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
