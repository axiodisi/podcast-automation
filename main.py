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
import json
import re
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


def authenticate_gspread():
    creds = None
    token_file = 'token.json'

    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secret_file, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_file, 'w') as token:
            token.write(creds.to_json())

    return gspread.authorize(creds)


# Set up gspread authentication
client = authenticate_gspread()
spreadsheet_key = '1p2pRyckjg0kgzwDjxV7fPOhNQh2YvxFSjRpeDJVXWpA'
spreadsheet = client.open_by_key(spreadsheet_key)
sheet = spreadsheet.worksheet('rad-pod-tit-soc-db')


def upload_to_bucket(file_path):
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(os.path.basename(file_path))

    print(f"Uploading {file_path} to Google Cloud bucket {BUCKET_NAME}...")
    blob.upload_from_filename(file_path)
    print(f"File {file_path} uploaded successfully to {BUCKET_NAME}.")


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

    try:
        rough_string = ET.tostring(root, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        with open(rss_file_path, 'w', encoding='utf-8') as f:
            f.write(reparsed.toprettyxml(indent="    "))
        print(f"RSS feed updated with episode: {episode_title}")
    except Exception as e:
        print(f"Error writing to RSS feed file: {e}")


def commit_to_git():
    try:
        subprocess.run(['git', 'add', rss_file_path], check=True)
        subprocess.run(
            ['git', 'commit', '-m', 'Update RSS feed with new podcast episode'], check=True)
        subprocess.run(['git', 'push'], check=True)
        print("RSS feed changes committed to Git successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error committing changes to Git: {e}")


def add_track_to_queue(unix_style_path):
    HOST = "127.0.0.1"
    PORT = 1234
    MAX_RETRIES = 3

    for attempt in range(MAX_RETRIES):
        tn = None
        try:
            print(f"\nAttempt {attempt + 1} to queue track...")
            tn = telnetlib.Telnet(HOST, PORT, timeout=5)

            # First check queue status
            tn.write(b'radio_queue.length\n')
            queue_length = tn.read_until(b"END", timeout=5).decode('utf-8')
            print(f"Current queue length: {queue_length}")

            # Send the push command
            command = f'radio_queue.push {unix_style_path}\n'
            print(f"Sending command: {command.strip()}")
            tn.write(command.encode('utf-8'))

            # Wait for proper confirmation
            response = tn.read_until(b"END", timeout=5).decode('utf-8')
            print(f"Initial response: {response}")

            # Verify the track was actually queued
            tn.write(b'radio_queue.length\n')
            new_length = tn.read_until(b"END", timeout=5).decode('utf-8')
            print(f"New queue length: {new_length}")

            if "error" in response.lower():
                raise Exception(f"Liquidsoap reported error: {response}")

            print(f"Successfully queued: {unix_style_path}")
            return True

        except Exception as e:
            print(f"Queue attempt {attempt + 1} failed: {str(e)}")
            if attempt == MAX_RETRIES - 1:
                print(f"Failed to queue track after {MAX_RETRIES} attempts")
                return False
            time.sleep(2)  # Wait before retry

        finally:
            if tn:
                try:
                    tn.close()
                except:
                    pass


class NewFileHandler(FileSystemEventHandler):
    def __init__(self):
        self.processing = False

    def on_created(self, event):
        if self.processing:
            print("Already processing a file, skipping...")
            return

        if event.is_directory:
            return

        # Update this check since filename will now be like 'stitched_audio_20241031_123456.mp3'
        if event.src_path.endswith(".mp3") and 'stitched_audio_' in event.src_path:
            try:
                self.processing = True
                print(f"\nNew file detected: {event.src_path}")
                time.sleep(COPY_DELAY)
                # Instead of adding timestamp (since it's already there), just process the file
                process_audio_file(event.src_path)
            finally:
                self.processing = False


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


def process_audio_file(file_path):
    try:
        print(f"\nProcessing file: {file_path}")

        # Extract timestamp from filename
        base_name = os.path.basename(file_path)
        # === ADD THIS NEW SECTION HERE ===
        processed_urls_path = 'C:/Users/rocco.DESKTOP-E207F2C/OneDrive/Documents/projects/radioai/XFeedData/pup/processed_urls.json'
        track_urls_path = 'C:/Users/rocco.DESKTOP-E207F2C/OneDrive/Documents/projects/radioai/XFeedData/pup/track_urls.json'

        # Get most recent URL from processed_urls.json
        with open(processed_urls_path, 'r') as f:
            processed_urls = json.load(f)
            latest_url = processed_urls[-1] if processed_urls else None

        if latest_url:
            # Map it to this audio file in track_urls.json
            try:
                with open(track_urls_path, 'r') as f:
                    track_urls = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                track_urls = {}

            track_urls[base_name] = latest_url
            with open(track_urls_path, 'w') as f:
                json.dump(track_urls, f, indent=2)
            print(f"Mapped {base_name} to {latest_url}")
            # === END NEW SECTION ===

        match = re.search(r'\d{8}_\d{6}', base_name)
        if match:
            timestamp = match.group(0)
            print(f"Extracted timestamp: {timestamp}")
        else:
            print("No timestamp found in filename")
            return None

        # Move to archive folder
        new_file_path = os.path.join(archive_folder, base_name)

        os.makedirs(archive_folder, exist_ok=True)

        # Move file to archive
        shutil.copy2(file_path, new_file_path)
        os.remove(file_path)
        print(f"Moved file to archive: {new_file_path}")

        # Convert path for Liquidsoap
        unix_style_path = new_file_path.replace(
            "\\", "/").replace("C:", "/mnt/c")

        # Save mapping with existing timestamp
        print(f"Saved file mapping with timestamp: {timestamp}")

        # Add to Liquidsoap queue
        add_track_to_queue(unix_style_path)

        try:
            # Process for RSS and cloud storage
            upload_to_bucket(new_file_path)
            title = sheet.acell('A1').value or "Untitled Episode"
            description = sheet.acell('B1').value or "No description available"
            audio_url = f"http://storage.googleapis.com/{BUCKET_NAME}/{os.path.basename(new_file_path)}"
            print(f"Updated URL mapping for timestamp: {timestamp}")
            update_rss_feed(title, description, audio_url)
            commit_to_git()
            print(f"Completed processing for {base_name}")
            return new_file_path

        except Exception as e:
            print(f"Error in processing phase: {str(e)}")
            return None

    except Exception as e:
        print(f"Critical error: {str(e)}")
        return None


if __name__ == "__main__":
    monitor_output_folder()
