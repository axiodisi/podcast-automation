import os
import time
import shutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from google.cloud import storage

# Adjust this value based on the time it takes for queue_stream to copy a file
COPY_DELAY = 10  # 10 seconds delay (adjust as needed)

# Path to the folder to monitor
music_folder = r'C:\Users\rocco.DESKTOP-E207F2C\OneDrive\Documents\projects\radioai\output'
archive_folder = os.path.join(music_folder, 'archive')  # Archive folder

# Google Cloud Bucket details
BUCKET_NAME = 'audio-upload-queue'

# Function to upload file to Google Cloud Storage bucket


def upload_to_bucket(file_path):
    # Initialize a Google Cloud Storage client
    storage_client = storage.Client()

    # Get the bucket
    bucket = storage_client.bucket(BUCKET_NAME)

    # Create a blob for the file
    blob = bucket.blob(os.path.basename(file_path))

    # Upload the file to the bucket
    print(f"Uploading {file_path} to Google Cloud bucket {BUCKET_NAME}...")
    blob.upload_from_filename(file_path)
    print(f"File {file_path} uploaded successfully to {BUCKET_NAME}.")

# Function to add a timestamp, upload to bucket, and archive the file


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

    # Try renaming the file and uploading it to the bucket
    try:
        # Rename the file with a timestamp
        shutil.move(file_path, new_file_path)
        print(f"Moved file to {new_file_path}")

        # Upload the renamed file to the bucket
        upload_to_bucket(new_file_path)

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

        # Only process mp3 files that are not 'now_playing'
        if event.src_path.endswith(".mp3") and 'now_playing' not in event.src_path:
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
