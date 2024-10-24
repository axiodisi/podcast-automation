import os

# Path to the archive folder - using raw string and normalized path
archive_folder = os.path.normpath(
    r'C:\Users\rocco.DESKTOP-E207F2C\OneDrive\Documents\projects\radioai\output\archive')


def append_streamed_prefix():
    print(f"Starting script... checking folder: {archive_folder}")

    # Check if the archive folder exists
    if not os.path.exists(archive_folder):
        print(f"Error: Archive folder '{archive_folder}' does not exist.")
        return
    else:
        print("Archive folder found!")

    # Get the list of all files in the folder
    try:
        files = os.listdir(archive_folder)
        print(f"Found {len(files)} items in the folder:")
        for f in files:
            print(f"  - {f}")
    except Exception as e:
        print(f"Error listing files: {e}")
        return

    if not files:
        print(f"No files found in '{archive_folder}' to rename.")
        return

    # Loop through each file and add the "streamed_" prefix if needed
    files_renamed = 0
    for filename in files:
        old_file_path = os.path.join(archive_folder, filename)
        # Check if it's a file (not a directory)
        if os.path.isfile(old_file_path):
            # Skip files that already have the "streamed_" prefix
            if not filename.startswith("streamed_"):
                new_filename = f"streamed_{filename}"
                new_file_path = os.path.join(archive_folder, new_filename)
                try:
                    # Rename the file
                    os.rename(old_file_path, new_file_path)
                    files_renamed += 1
                    print(f"Renamed '{filename}' to '{new_filename}'")
                except Exception as e:
                    print(f"Failed to rename '{filename}': {e}")
            else:
                print(f"Skipped '{filename}' (already has 'streamed_' prefix)")
        else:
            print(f"Skipped '{filename}' (not a file)")

    print(f"\nScript completed. Total files renamed: {files_renamed}")


# Direct execution - no if __name__ check
print("Script starting...")
append_streamed_prefix()
input("Press Enter to exit...")  # This keeps the window open
