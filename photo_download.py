import instaloader
import os
from itertools import islice

ig_profiles = ['taniackc', 'yokhyo_', 'hsiaksueudidi', '10.09.c', 'yannyhaha']
POSTS_TO_DOWNLOAD = 3  # Number of posts to download per profile

def download_photo(username, output_path):
    L = instaloader.Instaloader(
        download_pictures=True,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False
    )
    
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        posts = profile.get_posts()
        
        for post in islice(posts, POSTS_TO_DOWNLOAD):
            try:
                L.download_post(post, target=output_path)
                print(f"Downloaded post from {username}")
            except Exception as e:
                print(f"Failed to download post from {username}: {str(e)}")
    
    except instaloader.exceptions.ProfileNotExistsException:
        print(f"Profile {username} does not exist")
    except Exception as e:
        print(f"An error occurred while processing {username}: {str(e)}")

# Create the base output directory
base_output_dir = os.path.join('source', 'photos')
os.makedirs(base_output_dir, exist_ok=True)

for profile in ig_profiles:
    output_path = os.path.join(base_output_dir, profile)
    os.makedirs(output_path, exist_ok=True)
    download_photo(profile, output_path)
