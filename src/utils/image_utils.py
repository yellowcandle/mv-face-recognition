import cv2
import numpy as np
from typing import Optional

def load_image(path: str, target_size: Optional[tuple] = None) -> np.ndarray:
    """Load an image from path and optionally resize it."""
    image = cv2.imread(path)
    if image is None:
        raise ValueError(f"Failed to load image from {path}")
        
    # Convert BGR to RGB
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    if target_size:
        image = cv2.resize(image, target_size)
        
    return image 