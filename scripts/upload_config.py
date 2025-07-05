#!/usr/bin/env python3
"""
Upload config.json to Modal volume.

Usage:
    modal run upload_config.py
"""

import json
from pathlib import Path

from modal import App, Image, Volume, Mount

# --- Modal Configuration ---

app = App("upload-config")

# Simple Python image
modal_image = Image.from_registry("python:3.11-slim-bookworm")

volume = Volume.from_name("mv-face-recognition-data", create_if_missing=True)
VOL_MOUNT_PATH = Path("/data")


@app.function(
    image=modal_image,
    volumes={str(VOL_MOUNT_PATH): volume},
    mounts=[Mount.from_local_file("config.json", "/root/config.json")],
    timeout=300,
)
def upload_config_to_volume():
    """Upload config.json to the Modal volume."""
    import os
    
    # Read the local config.json file (it's mounted as part of the function)
    local_config_path = "/root/config.json"
    volume_config_path = VOL_MOUNT_PATH / "config.json"
    
    if os.path.exists(local_config_path):
        with open(local_config_path, 'r') as f:
            config = json.load(f)
        
        # Write to volume
        with open(volume_config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"✅ Successfully uploaded config.json to volume at {volume_config_path}")
        print(f"📋 Config contents:")
        print(json.dumps(config, indent=2))
        
        # Commit the volume changes
        volume.commit()
        print("💾 Volume changes committed")
        
        return {"status": "success", "config": config}
    else:
        print(f"❌ Could not find config.json at {local_config_path}")
        return {"status": "error", "message": "config.json not found"}


@app.local_entrypoint()
def main():
    """Upload config.json to Modal volume."""
    print("🚀 Uploading config.json to Modal volume...")
    
    # Upload config
    result = upload_config_to_volume.remote()
    
    if result["status"] == "success":
        print("✅ Config upload completed successfully!")
    else:
        print(f"❌ Config upload failed: {result.get('message', 'Unknown error')}")


if __name__ == "__main__":
    print("Use 'modal run upload_config.py' to upload config.json")