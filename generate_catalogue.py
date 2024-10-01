import os
import csv
from collections import defaultdict

# Paths
CSV_PATH = 'video_recognition_results.csv'
OUTPUT_FRAMES_DIR = 'output_frames'
DOCS_DIR = 'docs'
CATALOGUE_MD = os.path.join(DOCS_DIR, 'catalogue.md')
CONTESTANT_INFO_PATH = 'contestant_info.csv'  # New path for contestant info

def load_recognition_results(csv_path):
    contestants = defaultdict(list)
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            video = row['Video']
            frame = row['Frame']
            name = row['Name']
            # Updated image filename and path to match new folder structure and naming convention
            image_filename = f"frame_{int(frame):04d}.jpg"
            image_path = os.path.join(OUTPUT_FRAMES_DIR, video, image_filename)
            if os.path.exists(image_path):
                contestants[name].append(image_path)
            else:
                print(f"Warning: Image {image_path} does not exist.")
    return contestants

def load_contestant_info(path):
    """Load contestant information from CSV."""
    contestant_info = {}
    with open(path, newline='', encoding='utf-8-sig') as csvfile:  # Updated encoding
        reader = csv.DictReader(csvfile)
        for row in reader:
            name = row['姓名']
            contestant_info[name] = {
                '編號': row['編號'],
                '暱稱': row['暱稱'],
                '年齡': row['年齡']
            }
    return contestant_info

def generate_markdown(contestants, output_md, contestant_info):
    with open(output_md, 'w', encoding='utf-8') as md_file:
        md_file.write('# Contestants Appearance Catalog\n\n')
        # Add Index section at the top of the catalogue
        md_file.write('## Index\n\n')
        for name in sorted(contestants.keys()):
            anchor = name.lower().replace(" ", "-")
            md_file.write(f'- [{name}](#{anchor})\n')
        md_file.write('\n---\n\n')
        for name, images in sorted(contestants.items()):
            info = contestant_info.get(name, {})
            number = info.get('編號', 'N/A')
            nickname = info.get('暱稱', 'N/A')
            age = info.get('年齡', 'N/A')
            md_file.write(f'## {name}\n\n')
            md_file.write(f"**編號**: {number}, **暱稱**: {nickname}, **年齡**: {age}\n\n")
            for image in images:
                relative_path = os.path.relpath(image, DOCS_DIR)
                md_file.write(f'![{name}]({relative_path})\n\n')
            md_file.write('---\n\n')

def main():
    print("Loading recognition results...")
    contestants = load_recognition_results(CSV_PATH)
    print(f"Found {len(contestants)} contestants.")
    
    print("Loading contestant information...")
    contestant_info = load_contestant_info(CONTESTANT_INFO_PATH)
    
    print("Generating Markdown catalog...")
    generate_markdown(contestants, CATALOGUE_MD, contestant_info)
    print(f"Catalog generated at {CATALOGUE_MD}")

if __name__ == "__main__":
    main()