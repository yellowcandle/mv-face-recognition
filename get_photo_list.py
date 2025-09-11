import re


def extract_img_urls(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()

    pattern = r'https://scontent-[^"]+\.(?:jpg|png)'
    urls = re.findall(pattern, content)
    return urls


album1_urls = extract_img_urls("album1.html")
album2_urls = extract_img_urls("album2.html")

all_urls = album1_urls + album2_urls

print("Image URLs found:")
for url in all_urls:
    print(url)

print(f"\nTotal number of image URLs found: {len(all_urls)}")

# Save all URLs to two text files
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
