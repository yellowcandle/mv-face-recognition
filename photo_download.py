import os
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm  # Import tqdm for progress bar
import time

def download_photo(url, filename, album_dir):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx and 5xx)
        filepath = os.path.join(album_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded: {filename} to {album_dir}")
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err} - {url}")
    except Exception as err:
        print(f"Other error occurred: {err} - {url}")

def extract_photos_from_html_files(html_files):
    # Base directory for all photos
    base_photo_dir = './source/photo/raw'
    os.makedirs(base_photo_dir, exist_ok=True)
    
    for html_file in html_files:
        # Derive album name from the HTML file name (e.g., 'album1.html' -> 'album1')
        album_name = os.path.splitext(os.path.basename(html_file))[0]
        album_dir = os.path.join(base_photo_dir, album_name)
        os.makedirs(album_dir, exist_ok=True)
        
        with open(html_file, 'r', encoding='utf-8') as file:
            content = file.read()
        
        soup = BeautifulSoup(content, 'html.parser')
        # Find all img tags
        image_tags = soup.find_all('img')
        for img in tqdm(image_tags, desc=f"Downloading photos from {album_name}"):
            image_url = img.get('src')
            if image_url:
                # Remove query parameters from filename
                filename = image_url.split('/')[-1].split('?')[0]
                download_photo(image_url, filename, album_dir)

# HTML files path
html_files = ['album1.html', 'album2.html']

# Extract photos from the HTML files
extract_photos_from_html_files(html_files)
def extract_photos_from_html_files(html_files):
    # Base directory for all photos
    base_photo_dir = './source/photo/raw'
    os.makedirs(base_photo_dir, exist_ok=True)
    
    for html_file in html_files:
        # Derive album name from the HTML file name (e.g., 'album1.html' -> 'album1')
        album_name = os.path.splitext(os.path.basename(html_file))[0]
        album_dir = os.path.join(base_photo_dir, album_name)
        os.makedirs(album_dir, exist_ok=True)
        
        with open(html_file, 'r', encoding='utf-8') as file:
            content = file.read()
        
        soup = BeautifulSoup(content, 'html.parser')
        # Find all img tags
        image_tags = soup.find_all('img')
        for img in tqdm(image_tags, desc=f"Downloading photos from {album_name}"):
            image_url = img.get('src')
            if image_url:
                # Remove query parameters from filename
                filename = image_url.split('/')[-1].split('?')[0]
                download_photo(image_url, filename, album_dir)

# HTML files path
html_files = ['album1.html', 'album2.html']

# Extract photos from the HTML files
extract_photos_from_html_files(html_files)
