import os
import time
import xml.etree.ElementTree as ET
import datetime
import gspread
from google.cloud import storage
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Google Cloud Storage and RSS feed settings
# Replace with your Google Cloud bucket name
BUCKET_NAME = 'audio-upload-queue'
# Replace with the path to your RSS feed file
RSS_FEED_FILE = r'C:\Users\rocco.DESKTOP-E207F2C\OneDrive\Documents\projects\radioai\rss\rss.xml'
# Replace with the directory where your audio files are stored
AUDIO_DIRECTORY = r'C:\Users\rocco.DESKTOP-E207F2C\OneDrive\Documents\projects\radioai\output'
# Replace with your Google Sheet ID
SHEET_ID = '19R0p9Ps-4A3_9eU_dy5ZiGyF_FwLyued9TsZpYkZVpg'
WORKSHEET_NAME = 'Sheet1'  # Replace with your worksheet name

# Google Sheets API setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']


def get_google_sheets_credentials():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secrets.json', SCOPES)
            creds = flow.run_local_server(port=0)

        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds

# Function to get title and description from Google Sheets


def get_title_and_description():
    creds = get_google_sheets_credentials()
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet(WORKSHEET_NAME)

    # Assuming title is in A1 and description is in B1
    title = sheet.acell('A1').value
    description = sheet.acell('B1').value

    return title, description

# Function to upload audio file to Google Cloud Storage


def upload_audio_to_gcs(bucket_name, local_audio_path):
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    # Use the file's basename as the GCS object name
    filename = os.path.basename(local_audio_path)
    blob = bucket.blob(filename)

    # Upload the file to GCS
    blob.upload_from_filename(local_audio_path)
    print(f"Uploaded {filename} to Google Cloud Storage.")

    # Return the public URL of the uploaded file
    return f"http://storage.googleapis.com/{bucket_name}/{filename}"

# Function to update the RSS feed with the new episode


def update_rss_feed(episode_title, episode_description, audio_url):
    # Parse the existing RSS feed file
    try:
        tree = ET.parse(RSS_FEED_FILE)
    except FileNotFoundError:
        raise FileNotFoundError(f"RSS feed file '{RSS_FEED_FILE}' not found.")

    root = tree.getroot()
    channel = root.find('channel')

    # Create a new <item> for the episode
    item = ET.SubElement(channel, 'item')

    # Add title
    title = ET.SubElement(item, 'title')
    title.text = episode_title

    # Add description
    description = ET.SubElement(item, 'description')
    description.text = episode_description

    # Add enclosure with audio URL
    enclosure = ET.SubElement(
        item, 'enclosure', url=audio_url, length="12345678", type="audio/mpeg")

    # Add pubDate
    pubDate = ET.SubElement(item, 'pubDate')
    pubDate.text = datetime.datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')

    # Add guid
    guid = ET.SubElement(item, 'guid')
    guid.text = audio_url

    # Save the updated RSS feed
    tree.write(RSS_FEED_FILE, encoding='utf-8', xml_declaration=True)
    print(f"RSS feed updated with episode: {episode_title}")

# Function to find the most recent audio file in the directory based on timestamp


def get_latest_audio_file(directory, file_extension=".mp3"):
    files = [f for f in os.listdir(directory) if f.endswith(file_extension)]
    if not files:
        raise ValueError("No audio files found in the directory.")
    latest_file = max(files, key=lambda f: os.path.getmtime(
        os.path.join(directory, f)))
    return os.path.join(directory, latest_file)

# Function to monitor the directory for new files


def monitor_directory(directory, check_interval=10):
    print(f"Monitoring directory: {directory} for new audio files...")
    previous_files = set(os.listdir(directory))

    while True:
        time.sleep(check_interval)  # Wait before checking again
        current_files = set(os.listdir(directory))
        new_files = current_files - previous_files

        if new_files:
            latest_audio_file = max(
                new_files, key=lambda f: os.path.getmtime(os.path.join(directory, f)))
            if latest_audio_file.endswith(".mp3"):
                print(f"New audio file detected: {latest_audio_file}")
                return os.path.join(directory, latest_audio_file)

        previous_files = current_files

# Main workflow


def main():
    # Step 1: Monitor the directory for new audio files
    try:
        latest_audio_file = monitor_directory(AUDIO_DIRECTORY)
        print(f"Latest audio file detected: {latest_audio_file}")
    except ValueError as e:
        print(f"Error: {e}")
        return

    # Step 2: Upload the audio file to Google Cloud Storage
    try:
        audio_url = upload_audio_to_gcs(BUCKET_NAME, latest_audio_file)
        print(f"Audio file uploaded to: {audio_url}")
    except Exception as e:
        print(f"Error uploading file to Google Cloud: {e}")
        return

    # Step 3: Fetch the title and description from Google Sheets
    try:
        episode_title, episode_description = get_title_and_description()
        print(f"Fetched title and description from Google Sheets.")
    except Exception as e:
        print(f"Error fetching title and description: {e}")
        return

    # Step 4: Update the RSS feed
    try:
        update_rss_feed(episode_title, episode_description, audio_url)
    except Exception as e:
        print(f"Error updating RSS feed: {e}")


if __name__ == "__main__":
    main()
