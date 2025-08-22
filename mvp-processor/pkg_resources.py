"""
Workaround for pkg_resources import issue in face_recognition_models
"""

import os
import sys
from importlib.metadata import files
from importlib.resources import files as resource_files

def resource_filename(package, resource):
    """Workaround for pkg_resources.resource_filename"""
    try:
        # Try to find the package files
        pkg_files = files(package)
        if pkg_files is not None:
            resource_path = pkg_files / resource
            if resource_path.exists():
                return str(resource_path)
    except Exception:
        pass

    # Fallback to searching in site-packages
    for site_dir in sys.path:
        if 'site-packages' in site_dir:
            potential_path = os.path.join(site_dir, package, resource)
            if os.path.exists(potential_path):
                return potential_path

    raise FileNotFoundError(f"Resource {resource} not found in package {package}")

# Add this to the path so face_recognition_models can import it
sys.modules['pkg_resources'] = sys.modules[__name__]
