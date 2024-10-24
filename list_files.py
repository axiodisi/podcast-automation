import os
import time

# Print at the very start so we know the script is running
print("Script is starting...")
time.sleep(1)  # Add a small delay so we can see the output

# Path to the archive folder
folder = r'C:\Users\rocco.DESKTOP-E207F2C\OneDrive\Documents\projects\radioai\output\archive'
print(f"Checking folder: {folder}")
time.sleep(1)

# Basic checks
try:
    print("Does folder exist?", os.path.exists(folder))
    print("Is it a directory?", os.path.isdir(folder))

    # Try to list files
    print("\nTrying to list files...")
    files = os.listdir(folder)
    print(f"Found {len(files)} items:")
    for file in files:
        print(f"- {file}")

except Exception as e:
    print(f"Error occurred: {str(e)}")

print("\nScript finished.")
input("Press Enter to exit...")
