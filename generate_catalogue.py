import os
import csv
from collections import defaultdict
import glob

# Paths
CSV_PATH = "video_recognition_results.csv"
OUTPUT_FRAMES_DIR = "output_frames"
DOCS_DIR = "docs"
CATALOGUE_MD = os.path.join(DOCS_DIR, "catalogue.md")
CONTESTANT_INFO_PATH = "contestant_info.csv"  # New path for contestant info
IMAGE_URL_PREFIX = "https://media.githubusercontent.com/media/yellowcandle/mv-face-recognition/refs/heads/main/output_frames"  # URL prefix for deep links


def load_recognition_results(csv_path):
    """Load recognition results from CSV.

    Args:
        csv_path (_type_): _description_

    Returns:
        _type_: _description_
    """
    contestants = defaultdict(list)
    with open(csv_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            video = row["Video"]
            frame = int(row["Frame"])
            name = row["Name"]

            # Generate the new filename pattern
            frame_pattern = f"frame_*.jpg"

            # Get all frame files in the video directory
            video_dir = os.path.join(OUTPUT_FRAMES_DIR, video)
            all_frames = sorted(glob.glob(os.path.join(video_dir, frame_pattern)))

            if all_frames:
                # Find the nearest frame
                nearest_frame = min(
                    all_frames,
                    key=lambda x: abs(int(x.split("_")[-1].split(".")[0]) - frame),
                )

                # Generate the new filename
                new_frame_number = int(nearest_frame.split("_")[-1].split(".")[0])
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
    """_summary_

    Args:
        path (_type_): _description_

    Returns:
        _type_: _description_
    """
    contestant_info = {}
    with open(path, newline="", encoding="utf-8-sig") as csvfile:  # Updated encoding
        reader = csv.DictReader(csvfile)
        print("CSV Headers:", reader.fieldnames)  # Debugging: Print headers to verify
        for row in reader:
            nickname = row["暱稱"]
            contestant_info[nickname] = {"編號": row["編號"], "姓名": row["姓名"]}
    return contestant_info


def generate_markdown(contestants, output_md, contestant_info):
    """_summary_

    Args:
        contestants (_type_): _description_
        output_md (_type_): _description_
        contestant_info (_type_): _description_
    """
    with open(output_md, "w", encoding="utf-8") as md_file:
        md_file.write("# Contestants Appearance Catalog\n\n")
        # Add Index section with a searchable and sortable table
        md_file.write("## Index\n\n")
        md_file.write("Use your browser's built-in search function (usually Ctrl+F or Cmd+F) to search for contestants.\n\n")
        md_file.write("| 編號 | 暱稱 |\n")
        md_file.write("|------|------|\n")
        for nickname, info in sorted(contestant_info.items(), key=lambda x: int(x[1]["編號"])):
            number = info.get("編號", "N/A")
            md_file.write(f"| {number} | [{nickname}](#{number}) |\n")
        md_file.write("\n")

        # Generate the main catalogue
        for nickname, info in sorted(contestant_info.items(), key=lambda x: int(x[1]["編號"])):
            number = info.get("編號", "N/A")
            full_name = info.get("姓名", "N/A")
            md_file.write(f"## {number}. {nickname}\n\n")
            md_file.write(f"**編號**: {number}, **姓名**: {full_name}\n\n")
            if nickname in contestants:
                for image in contestants[nickname]:
                    relative_path = os.path.relpath(image, OUTPUT_FRAMES_DIR)
                    image_url = f"{IMAGE_URL_PREFIX}/{relative_path}"
                    md_file.write(f"![{nickname}]({image_url})\n\n")
            else:
                md_file.write("No images found for this contestant.\n\n")
            md_file.write("---\n\n")
        for name, images in sorted(contestants.items(), key=lambda x: int(contestant_info.get(x[0], {}).get("編號", "999"))):
            info = contestant_info.get(name, {})
            number = info.get("編號", "N/A")
            full_name = info.get("姓名", "N/A")
            md_file.write(f"## {name}\n\n")
            md_file.write(f"**編號**: {number}, **姓名**: {full_name}\n\n")
            for image in images:
                relative_path = os.path.relpath(image, OUTPUT_FRAMES_DIR)
                image_url = f"{IMAGE_URL_PREFIX}/{relative_path}"
                md_file.write(f"![{name}]({image_url})\n\n")
            md_file.write("---\n\n")


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
