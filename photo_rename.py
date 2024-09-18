import os
from pathlib import Path
import argparse

def extract_xxx(filename):
    parts = filename.split('_')
    return int(parts[0])

def rename_images(base_dir, dry_run=False):
    for folder_name in range(1, 97):
        folder_path = Path(base_dir) / str(folder_name)
        if not folder_path.exists():
            print(f"Folder {folder_name} not found")
            continue

        images = list(folder_path.glob('*.[jp][pn]g'))
        if len(images) != 2:
            print(f"Expected 2 images in folder {folder_name}, found {len(images)}")
            continue

        xxx_values = [extract_xxx(img.stem) for img in images]
        sorted_images = sorted(zip(xxx_values, images))

        for i, (_, img) in enumerate(sorted_images, start=1):
            new_name = f"{folder_name}-{i}{img.suffix}"
            if dry_run:
                print(f"Would rename {img.name} to {new_name}")
            else:
                img.rename(folder_path / new_name)
                print(f"Renamed {img.name} to {new_name}")

def main():
    parser = argparse.ArgumentParser(description="Rename images in contestant folders.")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without actually renaming files")
    args = parser.parse_args()

    base_dir = Path("source/photo/contestants")
    rename_images(base_dir, dry_run=args.dry_run)
    print("Image renaming complete." if not args.dry_run else "Dry run complete.")

if __name__ == "__main__":
    main()
