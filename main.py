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

# Define the scopes for Google Sheets and Drive access
SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
          'https://www.googleapis.com/auth/drive']

# Path to OAuth2 client credentials JSON file
client_secret_file = 'C:/Users/rocco.DESKTOP-E207F2C/OneDrive/Documents/projects/radioai/podcast-automation/client_secrets.json'

# Path to the folder to monitor
music_folder = r'C:\Users\rocco.DESKTOP-E207F2C\OneDrive\Documents\projects\radioai\output'
archive_folder = os.path.join(music_folder, 'archive')  # Archive folder
# Corrected RSS feed path
rss_file_path = r'C:\Users\rocco.DESKTOP-E207F2C\OneDrive\Documents\projects\radioai\podcast-automation\rss.xml'
COPY_DELAY = 10  # Adjust the delay as needed (in seconds)

# Google Cloud Bucket details
BUCKET_NAME = 'audio-upload-queue'

# Authenticate using OAuth2 flow


def authenticate_gspread():
    flow = InstalledAppFlow.from_client_secrets_file(
        client_secret_file, SCOPES)
    # This will open a browser for authentication
    creds = flow.run_local_server(port=0)
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
    # Initialize a Google Cloud Storage client
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(os.path.basename(file_path))

    # Upload the file to the bucket
    print(f"Uploading {file_path} to Google Cloud bucket {BUCKET_NAME}...")
    blob.upload_from_filename(file_path)
    print(f"File {file_path} uploaded successfully to {BUCKET_NAME}.")

# Function to update the RSS feed (rss.xml)


def update_rss_feed(file_path, title, description, length):
    # Load the existing rss.xml file from the correct location
    tree = ET.parse(rss_file_path)
    root = tree.getroot()

    # Create a new item
    item = ET.Element('item')

    # Add title, description, enclosure, pubDate, and guid to the item
    title_element = ET.SubElement(item, 'title')
    title_element.text = title

    description_element = ET.SubElement(item, 'description')
    description_element.text = description

    enclosure_element = ET.SubElement(item, 'enclosure', {
        'url': f"http://storage.googleapis.com/{BUCKET_NAME}/{os.path.basename(file_path)}",
        'length': str(length),
        'type': 'audio/mpeg'
    })

    pub_date_element = ET.SubElement(item, 'pubDate')
    pub_date_element.text = time.strftime(
        "%a, %d %b %Y %H:%M:%S GMT", time.gmtime())

    guid_element = ET.SubElement(item, 'guid')
    guid_element.text = f"http://storage.googleapis.com/{BUCKET_NAME}/{os.path.basename(file_path)}"

    # Add the new item to the channel
    channel = root.find('channel')
    channel.append(item)

    # Save the updated rss.xml file to the correct path
    tree.write(rss_file_path)
    print(f"RSS feed updated with {title}")

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
    # Define the new file path with a timestamp
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    dir_name, base_name = os.path.split(file_path)
    new_file_name = f"{base_name.split('.')[0]}_{timestamp}.mp3"
    new_file_path = os.path.join(dir_name, new_file_name)

    # Delay to allow queue_stream to complete its process
    print(
        f"Delaying for {COPY_DELAY} seconds to allow queue_stream to complete.")
    time.sleep(COPY_DELAY)

    # Fetch the title from cell A1 and description from cell B1
    title = sheet.acell('A1').value
    description = sheet.acell('B1').value

    # Calculate the file length (size in bytes)
    length = os.path.getsize(file_path)

    # Try renaming the file and uploading it to the bucket
    try:
        # Rename the file with a timestamp
        shutil.move(file_path, new_file_path)
        print(f"Moved file to {new_file_path}")

        # Upload the renamed file to the bucket
        upload_to_bucket(new_file_path)

        # Update RSS feed
        update_rss_feed(new_file_path, title, description, length)

        # Commit changes to Git
        commit_to_git()

        # Move the file to the archive after uploading to the bucket
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

        # Only process mp3 files that start with 'stitched_audio'
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
            time.sleep(1)  # Keep the script running
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    monitor_output_folder()
