import os
import csv
from collections import defaultdict
import glob

# Paths
CSV_PATH = 'video_recognition_results.csv'
OUTPUT_FRAMES_DIR = 'output_frames'
DOCS_DIR = 'docs'
CATALOGUE_MD = os.path.join(DOCS_DIR, 'catalogue.md')
CONTESTANT_INFO_PATH = 'contestant_info.csv'  # New path for contestant info
IMAGE_URL_PREFIX = 'https://media.githubusercontent.com/media/yellowcandle/mv-face-recognition/refs/heads/main/output_frames'  # URL prefix for deep links

def load_recognition_results(csv_path):
    contestants = defaultdict(list)
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            video = row['Video']
            frame = int(row['Frame'])
            name = row['Name']
            
            # Generate the new filename pattern
            frame_pattern = f"frame_*.jpg"
            
            # Get all frame files in the video directory
            video_dir = os.path.join(OUTPUT_FRAMES_DIR, video)
            all_frames = sorted(glob.glob(os.path.join(video_dir, frame_pattern)))
            
            if all_frames:
                # Find the nearest frame
                nearest_frame = min(all_frames, key=lambda x: abs(int(x.split('_')[-1].split('.')[0]) - frame))
                
                # Generate the new filename
                new_frame_number = int(nearest_frame.split('_')[-1].split('.')[0])
                new_image_filename = f"frame_{new_frame_number:04d}.jpg"
                new_image_path = os.path.join(video_dir, new_image_filename)
                
                # Rename if necessary
                if nearest_frame != new_image_path:
                    os.rename(nearest_frame, new_image_path)
                
                contestants[name].append(new_image_path)
            else:
                print(f"Warning: No frames found for video {video}")
    
    return contestants

def load_contestant_info(path):
    """Load contestant information from CSV."""
    contestant_info = {}
    with open(path, newline='', encoding='utf-8-sig') as csvfile:  # Updated encoding
        reader = csv.DictReader(csvfile)
        print("CSV Headers:", reader.fieldnames)  # Debugging: Print headers to verify
        for row in reader:
            nickname = row['暱稱']
            contestant_info[nickname] = {
                '編號': row['編號'],
                '姓名': row['姓名']
            }
    return contestant_info

def generate_markdown(contestants, output_md, contestant_info):
    with open(output_md, 'w', encoding='utf-8') as md_file:
        md_file.write('# Contestants Appearance Catalog\n\n')
        # Add Index section with a searchable and sortable table
        md_file.write('## Index\n\n')
        md_file.write('<input type="text" id="searchInput" onkeyup="searchTable()" placeholder="Search for names..">\n')
        md_file.write('<table id="contestantTable" class="sortable">\n')
        md_file.write('  <thead>\n')
        md_file.write('    <tr>\n')
        md_file.write('      <th>編號</th>\n')
        md_file.write('      <th>暱稱</th>\n')
        md_file.write('    </tr>\n')
        md_file.write('  </thead>\n')
        md_file.write('  <tbody>\n')
        for nickname, info in sorted(contestant_info.items(), key=lambda x: int(x[1]['編號'])):
            number = info.get('編號', 'N/A')
            anchor = nickname.lower().replace(" ", "-")
            md_file.write(f'    <tr>\n')
            md_file.write(f'      <td>{number}</td>\n')
            md_file.write(f'      <td><a href="#{anchor}">{nickname}</a></td>\n')
            md_file.write(f'    </tr>\n')
        md_file.write('  </tbody>\n')
        md_file.write('</table>\n\n')
        md_file.write('<script src="https://www.kryogenix.org/code/browser/sorttable/sorttable.js"></script>\n')
        md_file.write('<script>\n')
        md_file.write('function searchTable() {\n')
        md_file.write('  var input, filter, table, tr, td, i, txtValue;\n')
        md_file.write('  input = document.getElementById("searchInput");\n')
        md_file.write('  filter = input.value.toUpperCase();\n')
        md_file.write('  table = document.getElementById("contestantTable");\n')
        md_file.write('  tr = table.getElementsByTagName("tr");\n')
        md_file.write('  for (i = 1; i < tr.length; i++) {\n')
        md_file.write('    td = tr[i].getElementsByTagName("td")[1];\n')
        md_file.write('    if (td) {\n')
        md_file.write('      txtValue = td.textContent || td.innerText;\n')
        md_file.write('      if (txtValue.toUpperCase().indexOf(filter) > -1) {\n')
        md_file.write('        tr[i].style.display = "";\n')
        md_file.write('      } else {\n')
        md_file.write('        tr[i].style.display = "none";\n')
        md_file.write('      }\n')
        md_file.write('    }\n')
        md_file.write('  }\n')
        md_file.write('}\n')
        md_file.write('</script>\n')
        md_file.write('<noscript>You need to enable JavaScript to use the sortable and searchable tables.</noscript>\n')
        for name, images in sorted(contestants.items()):
            info = contestant_info.get(name, {})
            number = info.get('編號', 'N/A')
            full_name = info.get('姓名', 'N/A')
            md_file.write(f'## {name}\n\n')
            md_file.write(f"**編號**: {number}, **姓名**: {full_name}\n\n")
            for image in images:
                relative_path = os.path.relpath(image, OUTPUT_FRAMES_DIR)
                image_url = f"{IMAGE_URL_PREFIX}/{relative_path}"
                md_file.write(f'![{name}]({image_url})\n\n')
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