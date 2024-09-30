import os
import glob
import cv2
from tqdm import tqdm


def create_mp4_from_frames(frame_paths, output_mp4_path, fps=5):
    """Create an MP4 video from a list of frame paths."""
    if not frame_paths:
        print("No frames to process.")
        return

    # Read the first frame to get dimensions
    first_frame = cv2.imread(frame_paths[0])
    height, width, layers = first_frame.shape

    # Define the codec and create VideoWriter object
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_mp4_path, fourcc, fps, (width, height))

    for frame_path in tqdm(frame_paths, desc="Processing frames"):
        frame = cv2.imread(frame_path)
        out.write(frame)

    out.release()
    print(f"MP4 saved to {output_mp4_path}")


def generate_mp4s():
    # Get the absolute path of the current script
    current_script_path = os.path.abspath(__file__)
    project_root = os.path.dirname(current_script_path)

    # Directory paths
    output_frames_dir = os.path.join(project_root, "output_frames")
    output_mp4s_dir = os.path.join(project_root, "output_mp4s")

    # Create output_mp4s directory if it doesn't exist
    os.makedirs(output_mp4s_dir, exist_ok=True)

    # Get all video directories in output_frames
    video_dirs = [
        d
        for d in os.listdir(output_frames_dir)
        if os.path.isdir(os.path.join(output_frames_dir, d))
    ]

    for video_dir in video_dirs:
        print(f"Processing frames for video: {video_dir}")

        # Get all frame paths for the current video
        frame_paths = sorted(
            glob.glob(os.path.join(output_frames_dir, video_dir, "*.jpg"))
        )

        if frame_paths:
            # Create MP4 for this video
            mp4_output_path = os.path.join(output_mp4s_dir, f"{video_dir}_labeled.mp4")
            create_mp4_from_frames(frame_paths, mp4_output_path)
        else:
            print(f"No labeled frames found for video: {video_dir}")


if __name__ == "__main__":
    generate_mp4s()
