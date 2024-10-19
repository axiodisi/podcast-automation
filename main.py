import os
import time
import xml.etree.ElementTree as ET
import datetime
import subprocess
import gspread
from google.cloud import storage
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Google Cloud Storage and RSS feed settings
BUCKET_NAME = 'audio-upload-queue'
RSS_FEED_FILE = r'C:\Users\rocco.DESKTOP-E207F2C\OneDrive\Documents\projects\radioai\podcast-automation\rss.xml'
AUDIO_DIRECTORY = r'C:\Users\rocco.DESKTOP-E207F2C\OneDrive\Documents\projects\radioai\output'
SHEET_ID = '1xVPYIAivLMGqKKveirS3CVNyftNMz6c6CQG0beULjtI'
WORKSHEET_NAME = 'rad-pod-tit-soc-db'

# Google Sheets API setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

# Set to keep track of processed files in memory
processed_files = set()


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


def get_title_and_description():
    creds = get_google_sheets_credentials()
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet(WORKSHEET_NAME)
    title = sheet.acell('A1').value
    description = sheet.acell('B1').value
    return title, description


def upload_audio_to_gcs(bucket_name, local_audio_path):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    filename = os.path.basename(local_audio_path)
    blob = bucket.blob(filename)
    blob.upload_from_filename(local_audio_path)
    print(f"Uploaded {filename} to Google Cloud Storage.")
    return f"http://storage.googleapis.com/{bucket_name}/{filename}"


def update_rss_feed(episode_title, episode_description, audio_url):
    try:
        tree = ET.parse(RSS_FEED_FILE)
    except FileNotFoundError:
        raise FileNotFoundError(f"RSS feed file '{RSS_FEED_FILE}' not found.")

    root = tree.getroot()
    channel = root.find('channel')

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

    tree.write(RSS_FEED_FILE, encoding='utf-8', xml_declaration=True)
    print(f"RSS feed updated with episode: {episode_title}")


def get_latest_audio_file(directory, file_extension=".mp3"):
    files = [f for f in os.listdir(directory) if f.endswith(
        file_extension) and not f.endswith('.processed')]
    if not files:
        return None
    latest_file = max(files, key=lambda f: os.path.getmtime(
        os.path.join(directory, f)))
    return os.path.join(directory, latest_file)


def commit_rss_to_git():
    try:
        subprocess.run(['git', '-C', r'C:\Users\rocco.DESKTOP-E207F2C\OneDrive\Documents\projects\radioai\podcast-automation',
                        'add', RSS_FEED_FILE], check=True)
        subprocess.run(['git', '-C', r'C:\Users\rocco.DESKTOP-E207F2C\OneDrive\Documents\projects\radioai\podcast-automation',
                        'commit', '-m', 'Update RSS feed with new episode'], check=True)
        subprocess.run(
            ['git', '-C', r'C:\Users\rocco.DESKTOP-E207F2C\OneDrive\Documents\projects\radioai\podcast-automation', 'push'], check=True)
        print("Committed and pushed RSS feed to Git repository.")
    except subprocess.CalledProcessError as e:
        print(f"Error during git operations: {e}")


def main():
    print("Monitoring directory for new audio files...")

    while True:
        latest_audio_file = get_latest_audio_file(AUDIO_DIRECTORY)

        if latest_audio_file and latest_audio_file not in processed_files:
            print(f"Latest audio file detected: {latest_audio_file}")

            # Mark file as processed
            processed_files.add(latest_audio_file)

            # Upload the audio file to Google Cloud Storage
            try:
                audio_url = upload_audio_to_gcs(BUCKET_NAME, latest_audio_file)
                print(f"Audio file uploaded to: {audio_url}")
            except Exception as e:
                print(f"Error uploading file to Google Cloud: {e}")
                continue

            # Fetch the title and description from Google Sheets
            try:
                episode_title, episode_description = get_title_and_description()
                print(f"Fetched title and description from Google Sheets.")
            except Exception as e:
                print(f"Error fetching title and description: {e}")
                continue

            # Update the RSS feed
            try:
                update_rss_feed(episode_title, episode_description, audio_url)
            except Exception as e:
                print(f"Error updating RSS feed: {e}")
                continue

            # Commit the RSS feed to Git
            try:
                commit_rss_to_git()
            except Exception as e:
                print(f"Error committing RSS feed to Git: {e}")

        else:
            print(
                "No new unprocessed audio files detected. Checking again in 10 seconds...")

        time.sleep(10)


if __name__ == "__main__":
    main()
