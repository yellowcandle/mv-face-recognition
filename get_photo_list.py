import re
<<<<<<< HEAD
import os

def extract_img_urls(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
=======


def extract_img_urls(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()

>>>>>>> 1a133fbbf851daf8fd8aa1727558be5751dcb891
    pattern = r'https://scontent-[^"]+\.(?:jpg|png)'
    urls = re.findall(pattern, content)
    return urls

<<<<<<< HEAD
album1_urls = extract_img_urls('album1.html')
album2_urls = extract_img_urls('album2.html')
=======

album1_urls = extract_img_urls("album1.html")
album2_urls = extract_img_urls("album2.html")
>>>>>>> 1a133fbbf851daf8fd8aa1727558be5751dcb891

all_urls = album1_urls + album2_urls

print("Image URLs found:")
for url in all_urls:
    print(url)

print(f"\nTotal number of image URLs found: {len(all_urls)}")

# Save all URLs to two text files
<<<<<<< HEAD
with open('source/photo/raw/album1_image_urls.txt', 'w', encoding='utf-8') as output_file:
    for url in album1_urls:
        output_file.write(url + '\n')

with open('source/photo/raw/album2_image_urls.txt', 'w', encoding='utf-8') as output_file:
    for url in album2_urls:
        output_file.write(url + '\n')
=======
with open(
    "source/photo/raw/album1_image_urls.txt", "w", encoding="utf-8"
) as output_file:
    for url in album1_urls:
        output_file.write(url + "\n")

with open(
    "source/photo/raw/album2_image_urls.txt", "w", encoding="utf-8"
) as output_file:
    for url in album2_urls:
        output_file.write(url + "\n")
>>>>>>> 1a133fbbf851daf8fd8aa1727558be5751dcb891
