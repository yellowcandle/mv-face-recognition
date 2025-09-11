#!/usr/bin/env python3
"""
Batch processing script for MV Face Recognition, adapted for Modal.com.

This script offloads the heavy video processing to Modal's cloud infrastructure,
allowing you to leverage powerful GPUs on-demand.

**First-Time Setup:**

1.  **Install Modal Client:**
    ```bash
    pip install modal
    ```

2.  **Set up Modal:**
    ```bash
    modal setup
    ```

3.  **Create a Persistent Volume:**
    This is a one-time setup to create a network file system for your data.
    ```bash
    modal volume create mv-face-recognition-data
    ```

4.  **Sync Your Source Data to the Volume:**
    You only need to do this once, or whenever you update your source videos/photos.
    This command copies your local `source` and `config.json` to the volume.
    ```bash
    modal volume put mv-face-recognition-data ./source /source
    modal volume put mv-face-recognition-data ./config.json /config.json
    ```
    *Note: This assumes your `config.json` points to paths inside `/source`.*
    *You may need to edit `config.json` to use absolute paths like `/source/videos`.*

**How to Run:**

-   **Process all videos:**
    ```bash
    modal run modal_batch_processor.py
    ```

-   **Force re-processing of all videos:**
    ```bash
    modal run modal_batch_processor.py --force-reprocess
    ```

-   **Process a single video:**
    ```bash
    modal run modal_batch_processor.py --single-video "video_name.mp4"
    ```

-   **Run with a different similarity threshold:**
    ```bash
    modal run modal_batch_processor.py --similarity-threshold 0.3
    ```

**How to Get Your Processed Files Back:**

-   List the contents of the output directory on the volume:
    ```bash
    modal volume ls mv-face-recognition-data /processed_videos
    ```

-   Download all processed files to a local `output` directory:
    ```bash
    modal volume get mv-face-recognition-data /processed_videos ./output/
    modal volume get mv-face-recognition-data /metadata ./output/
    modal volume get mv-face-recognition-data /clips ./output/
    """

import sys
import time
import json
from pathlib import Path

from modal import App, Image, Volume, method

# --- Modal Configuration ---

# Define the Modal App (app name)
app = App("mv-face-recognition")

# Define the Docker image environment for the remote job
# This installs all necessary Python libraries and system dependencies like ffmpeg
modal_image = (
    Image.debian_slim(python_version="3.11")
    .apt_install("git", "ffmpeg", "sqlite3")
    .pip_install_from_requirements("requirements.txt")
    .pip_install("pysqlite3-binary")  # Newer SQLite for ChromaDB
    .pip_install("onnxruntime-gpu")  # Install ONNXRuntime with CUDA support
    .add_local_dir("src", "/src")
)

# Define the persistent data volume
# This gives our remote job a place to read source files and write output
volume = Volume.from_name("mv-face-recognition-data", create_if_missing=True)
VOL_MOUNT_PATH = Path("/data")

# --- Main Processing Logic ---

@app.cls(
    image=modal_image,
    volumes={str(VOL_MOUNT_PATH): volume},
    gpu="T4",  # Request a T4 GPU. Can be changed to A10G for more power.
    timeout=7200,  # Set a 2-hour timeout for the job
    scaledown_window=300, # Keep container warm for 5 mins
)
class ModalProcessor:
    """
    A Modal class that encapsulates the video processing logic and runs it remotely.
    """
    def __enter__(self):
        """
        Load models and initialize the processor when the container starts.
        This runs once per container, making subsequent calls faster.
        """
        # Fix SQLite version for ChromaDB
        import os
        import sys
        
        # Use pysqlite3 instead of sqlite3 if available
        try:
            import pysqlite3
            sys.modules['sqlite3'] = pysqlite3
            print("✅ Using pysqlite3 for ChromaDB compatibility")
        except ImportError:
            print("⚠️ pysqlite3 not available, using system sqlite3")
        
        # Add src to path inside the container - handle different path scenarios
        if os.path.exists('/src') and '/src' not in sys.path:
            sys.path.insert(0, '/src')
        # Also handle local development paths
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        src_path = os.path.join(project_root, 'src')
        if os.path.exists(src_path) and src_path not in sys.path:
            sys.path.insert(0, src_path)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from src.services.enhanced_video_processor import EnhancedVideoProcessor
        from src.core.hardware_acceleration import HardwareAccelerator

        print("🚀 Initializing EnhancedVideoProcessor in Modal...")

        # The config file is on our volume
        config_path = str(VOL_MOUNT_PATH / "config.json")

        # IMPORTANT: We must update the paths in the config to point to the volume
        with open(config_path, 'r') as f:
            config = json.load(f)

        config["paths"]["videos_dir"] = str(VOL_MOUNT_PATH / "source/videos")
        config["paths"]["contestants_dir"] = str(VOL_MOUNT_PATH / "source/photo/contestants")
        config["paths"]["chroma_db_path"] = str(VOL_MOUNT_PATH / "data/chroma_db")
        
        # Ensure output directories are also on the volume
        config["paths"]["processed_videos_dir"] = str(VOL_MOUNT_PATH / "processed_videos")
        config["paths"]["metadata_dir"] = str(VOL_MOUNT_PATH / "metadata")
        config["paths"]["clips_dir"] = str(VOL_MOUNT_PATH / "clips")

        # Save the modified config to a temporary file
        modified_config_path = str(VOL_MOUNT_PATH / "modified_config.json")
        with open(modified_config_path, 'w') as f:
            json.dump(config, f, indent=2)

        # Instantiate the processor with the modified config path
        self.processor = EnhancedVideoProcessor(config_path=modified_config_path)

        # Verify hardware acceleration on the remote GPU
        print("🔍 Checking GPU availability in Modal container...")
        
        # Check nvidia-smi
        import subprocess
        try:
            result = subprocess.run(['nvidia-smi'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print("✅ nvidia-smi available:")
                print(result.stdout)
            else:
                print(f"❌ nvidia-smi failed: {result.stderr}")
        except Exception as e:
            print(f"❌ nvidia-smi not available: {e}")
        
        accelerator = HardwareAccelerator()
        print("✅ Modal container hardware info:")
        accelerator.print_hardware_info()
        
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup when the container exits."""
        pass

    @method()
    def run_batch_processing(
        self,
        force_reprocess: bool = False,
        single_video: str = None,
        similarity_threshold: float = 0.25,
    ):
        """
        The main processing function that runs on a remote Modal GPU container.
        """
        from tqdm import tqdm

        print("="*60)
        print("STARTING MODAL BATCH PROCESSING")
        print(f"Force reprocess: {force_reprocess}")
        print(f"Single video: {single_video}")
        print(f"Similarity threshold: {similarity_threshold}")
        print("="*60)

        start_time = time.time()

        try:
            # Initialize the processor if not already done
            if not hasattr(self, 'processor'):
                self.__enter__()
            
            self.processor.set_similarity_threshold(similarity_threshold)
            videos = self.processor.get_available_videos()

            if not videos:
                print("❌ No videos found in /source/videos on the volume.")
                return

            print(f"Found {len(videos)} videos on volume: {videos}")

            if single_video:
                if single_video in videos:
                    videos_to_process = [single_video]
                    print(f"Processing single video: {single_video}")
                else:
                    print(f"❌ Video '{single_video}' not found on volume.")
                    return
            else:
                videos_to_process = videos

            def overall_progress_callback(video_idx, total_videos, video_name, step, total_steps, step_desc):
                """Callback for overall batch progress updates."""
                tqdm.write(f"[{video_idx+1}/{total_videos}] {video_name}: {step_desc} ({step}/{total_steps})")

            if single_video:
                print(f"\n🎬 Processing single video: {single_video}")
                result = self.processor.process_video_comprehensive(single_video)
                results = {single_video: result}
            else:
                print(f"\n🎬 Starting batch processing of {len(videos_to_process)} videos")
                results = self.processor.batch_process_all_videos(force_reprocess, overall_progress_callback)

            total_time = time.time() - start_time
            print_processing_summary(results, total_time)

            # The report is saved to the persistent volume
            generate_processing_report(self.processor, results, total_time)

            # Generate dense metadata for enhanced video player synchronization
            print("\n" + "="*60)
            print("🚀 GENERATING DENSE METADATA FOR ENHANCED VIDEO PLAYER")
            print("="*60)
            print("Generating 6x more timeline data for smooth real-time synchronization...")
            
            dense_metadata_results = self._generate_dense_metadata_for_processed_videos()
            
            print("="*60)
            print("✅ MODAL BATCH PROCESSING COMPLETE")
            print("="*60)

        except Exception as e:
            print(f"❌ Error during batch processing: {e}")
            import traceback
            traceback.print_exc()

    def _generate_dense_metadata_for_processed_videos(self):
        """Generate dense metadata for all processed videos."""
        from src.services.realtime_video_processor import create_dense_metadata_for_video
        
        processed_videos_dir = VOL_MOUNT_PATH / "processed_videos"
        dense_results = {}
        
        if not processed_videos_dir.exists():
            print("⚠️ No processed videos directory found, skipping dense metadata generation")
            return dense_results
        
        # Find all processed videos
        processed_videos = list(processed_videos_dir.glob("*_annotated.mp4"))
        
        if not processed_videos:
            print("⚠️ No processed videos found, skipping dense metadata generation")
            return dense_results
        
        print(f"Found {len(processed_videos)} processed videos for dense metadata generation")
        
        for video_path in processed_videos:
            video_name = video_path.name
            print(f"\n🎯 Generating dense metadata for: {video_name}")
            
            try:
                # Create dense metadata
                result = create_dense_metadata_for_video(str(video_path))
                
                if result["success"]:
                    dense_results[video_name] = {
                        "success": True,
                        "metadata_file": result["metadata_file"],
                        "processing_stats": result["processing_stats"],
                        "contestants_detected": result["contestants_detected"]
                    }
                    
                    print("✅ Dense metadata generated successfully!")
                    print(f"   📊 Processing stats: {result['processing_stats']}")
                    print(f"   👥 Contestants detected: {len(result['contestants_detected'])}")
                else:
                    dense_results[video_name] = {
                        "success": False,
                        "error": result.get("error", "Unknown error")
                    }
                    print(f"❌ Failed to generate dense metadata: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                dense_results[video_name] = {
                    "success": False,
                    "error": str(e)
                }
                print(f"❌ Exception generating dense metadata for {video_name}: {e}")
        
        # Summary
        successful_dense = len([r for r in dense_results.values() if r.get("success", False)])
        total_dense = len(dense_results)
        
        print("\n📈 Dense Metadata Generation Summary:")
        print(f"   Total videos: {total_dense}")
        print(f"   Successful: {successful_dense}")
        print(f"   Failed: {total_dense - successful_dense}")
        
        if successful_dense > 0:
            print(f"✅ Enhanced timeline data generated for {successful_dense} videos!")
            print("   Videos now have 6x more timeline data for smooth video player synchronization")
        
        return dense_results


# --- Local Entrypoint ---

@app.local_entrypoint()
def main(
    force_reprocess: bool = False,
    single_video: str = None,
    similarity_threshold: float = 0.25,
    dry_run: bool = False, # Dry run is not supported in Modal version
):
    """
    This is the function that runs on your local machine.
    It takes your command-line arguments and calls the remote Modal class.
    """
    if dry_run:
        print("Note: --dry-run is not applicable for Modal execution and will be ignored.")
        print("The script will connect to Modal but not run the job if you wish to proceed.")

    # Validate similarity threshold locally
    if not 0.0 <= similarity_threshold <= 1.0:
        print("Error: Similarity threshold must be between 0.0 and 1.0", file=sys.stderr)
        sys.exit(1)

    # Instantiate the remote class
    processor = ModalProcessor()

    # Call the remote method, which runs the batch processing in the cloud
    processor.run_batch_processing.remote(
        force_reprocess=force_reprocess,
        single_video=single_video,
        similarity_threshold=similarity_threshold,
    )


# --- Helper Functions (copied from batch_process_videos.py) ---
# These functions are used to print the summary after the job is done.
# They are included here to avoid circular dependencies and keep the script self-contained.

def print_processing_summary(results, total_time):
    """Print a summary of processing results."""
    print("\n" + "="*60)
    print("🎬 PROCESSING SUMMARY")
    print("="*60)

    successful = [video for video, result in results.items() if "error" not in result]
    failed = [video for video, result in results.items() if "error" in result]

    print(f"📊 Total videos processed: {len(results)}")
    print(f"✅ Successful: {len(successful)}")
    print(f"❌ Failed: {len(failed)}")
    print(f"⏱️  Total processing time: {total_time/60:.1f} minutes")

    if successful:
        print("\n✓ Successfully processed:")
        for video in successful:
            result = results[video]
            stats = result.get('stats', {})
            print(f"  📹 {video}")
            print(f"    👥 Faces detected: {stats.get('total_faces_detected', 0)}")
            print(f"    ✅ Faces recognized: {stats.get('total_faces_recognized', 0)}")
            print(f"    ⏱️  Processing time: {result.get('processing_time', 0):.1f}s")

    if failed:
        print("\n✗ Failed to process:")
        for video in failed:
            error = results[video].get('error', 'Unknown error')
            print(f"  {video}: {error}")

def generate_processing_report(processor, results, total_time):
    """Generate a detailed processing report on the persistent volume."""
    from datetime import datetime
    report_file = VOL_MOUNT_PATH / "batch_processing_report.json"
    print(f"Generating detailed report to: {report_file}")

    report = {
        "timestamp": datetime.now().isoformat(),
        "processing_time_minutes": total_time / 60,
        "summary": {
            "total_videos": len(results),
            "successful": len([r for r in results.values() if "error" not in r]),
            "failed": len([r for r in results.values() if "error" in r]),
        },
        "detailed_results": results
    }
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, default=str)
    print("✅ Report saved successfully.")
