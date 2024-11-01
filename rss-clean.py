# Define the path to your RSS file
file_path = "C:\\Users\\rocco.DESKTOP-E207F2C\\OneDrive\\Documents\\projects\\radioai\\podcast-automation\\rss.xml"

# Read in the RSS file, filter out empty lines, and deduplicate lines
with open(file_path, 'r', encoding='utf-8') as file:
    lines = file.readlines()

# Remove excess whitespace and keep only unique lines
cleaned_lines = []
for line in lines:
    stripped_line = line.strip()
    if stripped_line and stripped_line not in cleaned_lines:
        cleaned_lines.append(line)

# Write the cleaned lines back to the file
with open(file_path, 'w', encoding='utf-8') as file:
    file.writelines(cleaned_lines)

print(f"Cleaned up {file_path}, reducing whitespace and duplicate lines.")
