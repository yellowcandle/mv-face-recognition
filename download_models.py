import os
import urllib.request
import ssl

def download_file(url: str, filepath: str):
    """Download a file from a URL to a local path."""
    print(f"Downloading {url} to {filepath}...")
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    try:
        # Use requests instead of urllib for better error handling
        import requests
        response = requests.get(url, verify=True, stream=True)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        print(f"Successfully downloaded to {filepath}")
    except Exception as e:
        print(f"Error downloading {url}: {str(e)}")
        raise

def main():
    # Create models directory
    os.makedirs('models', exist_ok=True)
    
    # FCN model for segmentation
    fcn_url = "https://github.com/onnx/models/releases/download/vision/fcn/fcn-resnet50-12.onnx"
    fcn_path = os.path.join('models', 'fcn.onnx')
    
    # ArcFace model for face recognition
    arcface_url = "https://github.com/onnx/models/releases/download/vision/arcface/arcface-resnet100-8.onnx"
    arcface_path = os.path.join('models', 'arcface.onnx')
    
    # Download models
    for url, path in [(fcn_url, fcn_path), (arcface_url, arcface_path)]:
        if not os.path.exists(path):
            download_file(url, path)
        else:
            print(f"Model already exists at {path}")

if __name__ == "__main__":
    main()
