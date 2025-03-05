from config.config import Config, DetectionConfig, SegmentationConfig, RecognitionConfig
from detection.face_detector import FaceDetector
from recognition.face_recognizer import FaceRecognizer
from utils.image_utils import load_image
import os
import pandas as pd
import cv2
import numpy as np
from tqdm import tqdm

def select_items(items, item_type):
    """
    Allow user to select specific items from a list.
    
    Args:
        items (list): List of items to select from
        item_type (str): Type of items (for display purposes)
        
    Returns:
        list: Selected items
    """
    if not items:
        print(f"No {item_type} found.")
        return []
        
    print(f"\nAvailable {item_type}:")
    for i, item in enumerate(items, 1):
        print(f"{i}. {item}")
        
    while True:
        try:
            selection = input(f"\nEnter numbers of {item_type} to process (comma-separated, or 'all'): ").strip()
            if selection.lower() == 'all':
                return items
                
            indices = [int(x.strip()) - 1 for x in selection.split(',')]
            selected = [items[i] for i in indices if 0 <= i < len(items)]
            
            if not selected:
                print("No valid selections made. Please try again.")
                continue
                
            return selected
            
        except (ValueError, IndexError):
            print("Invalid input. Please enter comma-separated numbers or 'all'.")

def validate_video_file(video_path):
    """
    Validate if a video file can be opened and read properly.
    
    Args:
        video_path: Path to video file
        
    Returns:
        tuple: (is_valid, error_message)
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return False, "Failed to open video file"
        
    # Read first frame to verify video stream
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        return False, "Failed to read video stream"
        
    return True, None

def annotate_image(image_path, face_recognizer, known_embeddings, config):
    """
    Annotate faces in a single image.
    
    Args:
        image_path: Path to the image file
        face_recognizer: Initialized FaceRecognizer instance
        known_embeddings: Dictionary of known face embeddings
        config: Configuration object
        
    Returns:
        Annotated image with detected faces
    """
    try:
        # Load and process image
        image = load_image(image_path)
        faces = face_recognizer.detect_and_embed(image)
        
        # Create copy for annotation
        annotated_image = image.copy()
        
        # Process each detected face
        results = []
        for face_embedding, bbox in faces:
            best_match = None
            best_confidence = -1
            
            # Compare with known embeddings
            for nickname, known_embs in known_embeddings.items():
                for known_emb in known_embs:
                    confidence = face_recognizer.compute_similarity(
                        face_embedding,
                        known_emb
                    )
                    if confidence > config.recognition.similarity_threshold:
                        if confidence > best_confidence:
                            best_match = nickname
                            best_confidence = confidence
            
            # Draw bounding box and label if match found
            if best_match:
                x1, y1, x2, y2 = bbox
                cv2.rectangle(
                    annotated_image,
                    (int(x1), int(y1)),
                    (int(x2), int(y2)),
                    (0, 255, 0),
                    2
                )
                cv2.putText(
                    annotated_image,
                    f"{best_match} ({best_confidence:.2f})",
                    (int(x1), int(y1) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2
                )
                results.append({
                    'nickname': best_match,
                    'confidence': best_confidence,
                    'bbox': bbox
                })
        
        return annotated_image, results
    except Exception as e:
        print(f"Error processing image {image_path}: {str(e)}")
        return None, []

def main():
    # Initialize paths - go up one level from src directory
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    contestants_dir = os.path.join(project_root, "source", "photo", "contestants")
    images_dir = os.path.join(project_root, "source", "images")
    contestant_info_path = os.path.join(project_root, "contestant_info.csv")
    
    # Create images directory if it doesn't exist
    os.makedirs(images_dir, exist_ok=True)

    # Load contestant information
    try:
        contestant_info = pd.read_csv(contestant_info_path)
        # Ensure 編號 is string type for directory matching
        contestant_info['編號'] = contestant_info['編號'].astype(str)
    except Exception as e:
        print(f"Error reading contestant info CSV: {e}")
        return

    # Initialize configuration with model paths
    config = Config(
        detection=DetectionConfig(
            model_path=os.path.join(project_root, "models", "face_detection_yunet.onnx")
        ),
        segmentation=SegmentationConfig(model_path=""),  # Not used currently
        recognition=RecognitionConfig(model_path="")  # Using pre-computed embeddings
    )
    
    # Initialize components
    face_detector = FaceDetector(
        confidence_threshold=config.detection.confidence_threshold
    )
    
    face_recognizer = FaceRecognizer(
        recognition_model_path="",
        face_detector=face_detector,
        similarity_threshold=0.15  # Lower threshold for HOG-based embeddings
    )

    # Load pre-computed contestant embeddings
    known_embeddings = {}
    for _, contestant in contestant_info.iterrows():
        nickname = contestant['暱稱']
        embedding = face_recognizer.get_embedding(nickname)
        if embedding is not None:
            known_embeddings[nickname] = [embedding]  # Keep list format for compatibility

    print(f"Successfully loaded embeddings for {len(known_embeddings)} contestants")
    
    # Allow user to select specific videos to process
    videos_dir = os.path.join(project_root, "source", "videos")
    os.makedirs(videos_dir, exist_ok=True)
    
    video_files = [f for f in os.listdir(videos_dir) if f.lower().endswith(('.mp4', '.avi'))]
    if not video_files:
        print(f"No video files found in {videos_dir}")
        return
        
    selected_videos = select_items(video_files, "videos")
    if not selected_videos:
        print("No videos selected for processing")
        return

    # Create output directories
    frames_dir = os.path.join(project_root, "output_frames")
    videos_dir_out = os.path.join(project_root, "output_mp4s")
    os.makedirs(frames_dir, exist_ok=True)
    os.makedirs(videos_dir_out, exist_ok=True)

    all_results = []
    
    for video_file in selected_videos:
        print(f"\nProcessing video: {video_file}")
        video_path = os.path.join(videos_dir, video_file)
        
        # Create output directory for frames
        video_frames_dir = os.path.join(frames_dir, video_file.split('.')[0])
        os.makedirs(video_frames_dir, exist_ok=True)
        
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"Failed to open video: {video_file}")
                continue
                
            # Get video properties
            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Create video writer for annotated video
            output_video_path = os.path.join(videos_dir_out, f"{video_file}_labeled.mp4")
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_video_path, fourcc, fps, (frame_width, frame_height))
            
            frame_count = 0
            with tqdm(total=total_frames, desc="Processing frames") as pbar:
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                        
                    frame_count += 1
                    pbar.update(1)
                    
                    # Process every 5th frame
                    if frame_count % 5 == 0:
                        try:
                            # Get face embeddings from current frame
                            faces = face_recognizer.detect_and_embed(frame)
                            
                            # Create copy for annotation
                            frame_with_boxes = frame.copy()
                            
                            # Process each detected face
                            frame_results = []
                            for face_embedding, bbox in faces:
                                best_match = None
                                best_confidence = -1
                                
                                # Compare with known embeddings
                                for nickname, known_embs in known_embeddings.items():
                                    for known_emb in known_embs:
                                        confidence = face_recognizer.compute_similarity(
                                            face_embedding,
                                            known_emb
                                        )
                                        # Print similarity scores for debugging
                                        print(f"\nSimilarity with {nickname}: {confidence:.4f}")
                                        if confidence > config.recognition.similarity_threshold:
                                            if confidence > best_confidence:
                                                best_match = nickname
                                                best_confidence = confidence
                                
                                # Always draw bounding box and label
                                x1, y1, x2, y2 = bbox
                                cv2.rectangle(
                                    frame_with_boxes,
                                    (int(x1), int(y1)),
                                    (int(x2), int(y2)),
                                    (0, 255, 0),
                                    2
                                )
                                label = f"{best_match} ({best_confidence:.2f})" if best_match else "Unknown"
                                cv2.putText(
                                    frame_with_boxes,
                                    label,
                                    (int(x1), int(y1) - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    1.0,  # Increased font size
                                    (0, 255, 0),
                                    2
                                )
                                
                                # Print detection in terminal
                                print(f"\nFrame {frame_count}: Detected {label} at coordinates ({int(x1)}, {int(y1)}, {int(x2)}, {int(y2)})")
                                if best_match:
                                    frame_results.append({
                                        'nickname': best_match,
                                        'confidence': best_confidence,
                                        'bbox': bbox
                                    })
                            
                            # Save annotated frame
                            frame_path = os.path.join(video_frames_dir, f"frame_{frame_count:04d}.jpg")
                            cv2.imwrite(frame_path, frame_with_boxes)
                            
                            # Add results to overall results
                            timestamp = frame_count / fps
                            for result in frame_results:
                                all_results.append({
                                    'video': video_file,
                                    'frame': frame_count,
                                    'timestamp': timestamp,
                                    'nickname': result['nickname'],
                                    'confidence': result['confidence']
                                })
                        except Exception as e:
                            print(f"\nError processing frame {frame_count}: {str(e)}")
                            continue
                    
                    # Write frame to output video
                    out.write(frame_with_boxes if 'frame_with_boxes' in locals() else frame)
            
            cap.release()
            out.release()
            
        except Exception as e:
            print(f"Error processing video {video_file}: {str(e)}")
            if 'cap' in locals():
                cap.release()
            if 'out' in locals():
                out.release()
            continue
    
    # Save results to CSV if any faces were detected
    if all_results:
        results_df = pd.DataFrame(all_results)
        output_csv = os.path.join(project_root, "video_recognition_results.csv")
        results_df.to_csv(output_csv, index=False)
        print(f"\nResults saved to {output_csv}")
        
        # Print summary
        print("\nRecognition Summary:")
        summary = results_df.groupby(['video', 'nickname']).size().unstack(fill_value=0)
        print(summary)

if __name__ == "__main__":
    main()
