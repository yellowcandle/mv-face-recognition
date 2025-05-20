# pylint: disable=no-member
from src.core.detector import FaceDetector
from src.recognition.face_recognizer import FaceRecognizer
import os
import cv2
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, List, Optional, Tuple
import argparse # Added for command-line arguments
import matplotlib # For saving plots without UI
matplotlib.use('Agg') # Use a non-interactive backend
import matplotlib.pyplot as plt
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


# scikit-optimize for Bayesian Optimization
try:
    import skopt
    from skopt import gp_minimize, dump, load
    from skopt.space import Real, Integer, Categorical
    from skopt.utils import use_named_args
    from skopt.plots import plot_convergence, plot_objective
    HAS_SKOPT = True
except ImportError:
    HAS_SKOPT = False
    console.print("[yellow]Warning:[/yellow] scikit-optimize (skopt) not found. Bayesian optimization will not be available.")
    console.print("Please install it: [bold]pip install scikit-optimize[/bold]")

# Global variables for paths and ground truth, to be initialized in main
PROJECT_ROOT = None
FONT_PATH = None
GROUND_TRUTH_MAP = None
ARGS = None # To store command line arguments globally for objective function

# Define DIMENSIONS at module level with a subset of models (excluding opencv_dnn)
DIMENSIONS = [
    Real(0.3, 0.9, name='recognition_threshold'),
    Real(0.2, 0.8, name='detection_confidence'),
    Categorical(['sface', 'arcface'], name='recognition_model')
]

def main():
    # Argument parser
    parser = argparse.ArgumentParser(description="Test face recognition on an image with adjustable threshold.")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.4,
        help="Recognition similarity threshold (default: 0.4)",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.5,
        help="Face detection confidence threshold (default: 0.5)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug printing",
    )
    parser.add_argument(
        "--show_similarities",
        action="store_true",
        help="Show all similarity scores in debug output",
    )
    args = parser.parse_args()

    # Debug settings
    DEBUG = args.debug
    SHOW_ALL_SIMILARITIES = args.show_similarities
    SHOW_TIMING = True # Keep timing enabled for now, can be made an arg later
    
    # Recognition settings
    RECOGNITION_THRESHOLD = args.threshold
    CONFIDENCE_THRESHOLD = args.confidence
    
    # Initialize paths
    project_root = os.path.dirname(os.path.abspath(__file__))
    test_image_path = os.path.join(project_root, "source", "images", "test", "original.jpeg")
    # Modify result_path to include the threshold value for unique output files
    result_image_dir = os.path.join(project_root, "source", "images", "test")
    os.makedirs(result_image_dir, exist_ok=True) # Ensure directory exists
    result_path = os.path.join(result_image_dir, f"result_threshold_{RECOGNITION_THRESHOLD:.2f}_confidence_{CONFIDENCE_THRESHOLD:.2f}.jpeg")
    contestant_info_path = os.path.join(project_root, "contestant_info.csv")
    font_path = os.path.join(project_root, "fonts", "SourceHanSansTC-VF.ttf")

    if DEBUG:
        console.print(Panel("[bold cyan]DEBUG MODE ENABLED[/bold cyan]", title="[yellow]Debug Status[/yellow]", expand=False))
        debug_table = Table(show_header=True, header_style="bold magenta")
        debug_table.add_column("Setting", style="dim", width=30)
        debug_table.add_column("Value")
        debug_table.add_row("Current working directory", project_root)
        debug_table.add_row("Test image path", test_image_path)
        debug_table.add_row("Result image will be saved to", result_path)
        console.print(debug_table)

    # Load contestant information
    contestant_info = pd.read_csv(contestant_info_path)
    contestant_info["編號"] = contestant_info["編號"].astype(str)

    # Initialize detector with InsightFace backend
    face_detector = FaceDetector(
        backend=FaceDetector.BACKEND_INSIGHTFACE,
        model_size=(640, 640),
        device="auto",
        confidence_threshold=CONFIDENCE_THRESHOLD
    )

    # Initialize recognizer
    face_recognizer = FaceRecognizer(
        face_detector=face_detector,
        similarity_threshold=RECOGNITION_THRESHOLD,
        use_arcface=True
    )

    if DEBUG:
        console.print(Panel("[bold cyan]CURRENT PARAMETERS[/bold cyan]", title="[yellow]Parameters[/yellow]", expand=False))
        param_table = Table(show_header=True, header_style="bold magenta")
        param_table.add_column("Parameter", style="dim", width=30)
        param_table.add_column("Value")
        param_table.add_row("Detection confidence threshold", str(face_detector.confidence_threshold))
        param_table.add_row("Recognition similarity threshold", str(face_recognizer.similarity_threshold))
        param_table.add_row("Model size", str(face_detector.model_size))
        param_table.add_row("Using ArcFace", str(face_recognizer.use_arcface))
        console.print(param_table)

    # Define the target contestants for focused debugging
    target_contestants_for_debug = ["Tania", "阿妹", "Yanny", "阿 Yo", "Sinnie", "Elka", "Mei Mei", "阿蛋"]
    
    known_embeddings: Dict[str, List[np.ndarray]] = {}
    embeddings_base_dir = os.path.join(project_root, "source", "photo", "contestants", "embeddings")

    if DEBUG:
        console.print(Panel("[bold cyan]LOADING EMBEDDINGS FOR TARGET CONTESTANTS (DEBUGGING FOCUS)[/bold cyan]", title="[yellow]Embeddings[/yellow]", expand=False))
        console.print(f"[dim]Target contestants:[/dim] {', '.join(target_contestants_for_debug)}")
        console.print(f"[dim]Scanning for their embeddings in:[/dim] {embeddings_base_dir}")

    if not os.path.isdir(embeddings_base_dir):
        console.print(f"[red]Error:[/red] Embeddings directory not found at {embeddings_base_dir}")
        return

    loaded_count = 0
    missing_target_embeddings = list(target_contestants_for_debug)

    for contestant_name in target_contestants_for_debug:
        filename = f"{contestant_name}_embedding.npy"
        embedding_path = os.path.join(embeddings_base_dir, filename)
        if os.path.exists(embedding_path):
            try:
                embedding = np.load(embedding_path)
                if embedding.ndim == 2 and embedding.shape[0] == 1:
                    embedding = embedding.flatten()
                elif embedding.ndim > 1:
                    console.print(f"  [yellow]Warning:[/yellow] Embedding for {contestant_name} has unexpected shape {embedding.shape}. Skipping.")
                    continue
                
                known_embeddings[contestant_name] = [embedding]
                loaded_count += 1
                if contestant_name in missing_target_embeddings:
                    missing_target_embeddings.remove(contestant_name)
                if DEBUG:
                    console.print(f"[green]Loaded embedding for {contestant_name}:[/green]")
                    console.print(f"  [dim]Path:[/dim] {embedding_path}")
                    console.print(f"  [dim]Shape:[/dim] {embedding.shape}")
                    console.print(f"  [dim]Norm:[/dim] {np.linalg.norm(embedding):.4f}")
                    console.print(f"  [dim]Min/Max:[/dim] {np.min(embedding):.4f}/{np.max(embedding):.4f}")
            except Exception as e:
                console.print(f"[red]Error loading embedding for {contestant_name} from {embedding_path}:[/red] {e}")
        else:
            if DEBUG:
                console.print(f"[yellow]Embedding file not found for target contestant:[/yellow] {contestant_name} at {embedding_path}")

    if DEBUG:
        console.print(f"\n[bold]Successfully loaded {loaded_count}/{len(target_contestants_for_debug)} target embeddings.[/bold]")
        if missing_target_embeddings:
            console.print(f"[yellow]Warning:[/yellow] Missing embeddings for the following target contestants: {', '.join(missing_target_embeddings)}")
        if not known_embeddings:
            console.print("[yellow]Warning:[/yellow] No target embeddings were loaded. Recognition will not be possible against targets.")
            # return # Optionally exit

    # Add known embeddings to the recognizer's database
    for person_id, embeddings_list in known_embeddings.items():
        if embeddings_list and embeddings_list[0] is not None: # Ensure there's at least one valid embedding
            face_recognizer.add_known_embedding(person_id, embeddings_list[0])
            if DEBUG:
                console.print(f"[cyan]Added {person_id} to face_recognizer's database.[/cyan]")

    # Load test image
    image = cv2.imread(test_image_path)  # pylint: disable=no-member
    if image is None:
        console.print(f"[red]Failed to load test image at {test_image_path}[/red]")
        return

    # Detect and recognize faces
    import time
    start_time = time.time()
    
    if DEBUG:
        console.print(Panel("[bold cyan]FACE DETECTION[/bold cyan]", title="[yellow]Detection Phase[/yellow]", expand=False))
    
    # Get both embeddings and recognition results
    face_data = face_recognizer.detect_and_embed(image)
    # Pass face_data (pre-computed embeddings for detected faces) to identify_face
    results = face_recognizer.identify_face(image, detected_face_embeddings=face_data)
    
    if DEBUG:
        detection_time = time.time() - start_time
        console.print(f"[bold]Detected {len(results)} faces in {detection_time:.2f} seconds[/bold]")
        for i, (face_embedding, result) in enumerate(zip(face_data, results)):
            console.print(f"\n[bold magenta]Face {i+1}:[/bold magenta]")
            
            # Handle different bbox formats
            bbox = result['bbox']
            if hasattr(bbox, 'tolist'):  # If it's a numpy array
                bbox = bbox.tolist()
            elif isinstance(bbox, list) and len(bbox) >= 4:  # If it's already a list
                bbox = bbox[:4]  # Take first 4 elements
            else:
                console.print(f"  [yellow]Warning:[/yellow] Unexpected bbox format: {bbox}")
                continue
                
            console.print(f"  [dim]Bounding box:[/dim] {bbox}")
            console.print(f"  [dim]Confidence:[/dim] {result['confidence']:.4f}")
            if result['person_id']:
                console.print(f"  [green]Recognized as:[/green] {result['person_id']}")
                if SHOW_ALL_SIMILARITIES:
                    console.print("  [bold]Similarity scores:[/bold]")
                    similarity_table = Table(show_header=False, box=None)
                    similarity_table.add_column("Contestant", style="cyan")
                    similarity_table.add_column("Score", style="yellow")
                    for contestant, embeddings_list in known_embeddings.items():
                        for known_emb in embeddings_list: # known_emb is an np.ndarray
                            similarity = face_recognizer._compute_similarity(
                                face_embedding, known_emb
                            )
                            similarity_table.add_row(f"    {contestant}", f"{similarity:.4f}")
                    console.print(similarity_table)
            else:
                console.print("  [yellow]No match found[/yellow]")
                if SHOW_ALL_SIMILARITIES:
                    console.print("  [bold]Similarity scores:[/bold]")
                    similarity_table = Table(show_header=False, box=None)
                    similarity_table.add_column("Contestant", style="cyan")
                    similarity_table.add_column("Score", style="yellow")
                    for contestant, embeddings_list in known_embeddings.items():
                        for known_emb in embeddings_list: # known_emb is an np.ndarray
                            similarity = face_recognizer._compute_similarity(
                                face_embedding, known_emb
                            )
                            similarity_table.add_row(f"    {contestant}", f"{similarity:.4f}")
                    console.print(similarity_table)
    
    # Convert to PIL for better text rendering
    pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))  # pylint: disable=no-member
    draw = ImageDraw.Draw(pil_img)
    font = ImageFont.truetype(font_path, 24)

    # Draw results with face numbering and recognition info
    for i, result in enumerate(results, 1):
        bbox = result["bbox"]
        person_id = result["person_id"]
        confidence = result["confidence"]

        # Convert bbox coordinates to integers
        x1, y1, x2, y2 = map(int, bbox)
        
        # Draw bounding box
        box_color = "green" if person_id else "red"
        draw.rectangle([x1, y1, x2, y2], outline=box_color, width=2)
        
        # Prepare labels
        face_label = f"Face {i}"
        if person_id:
            recognition_label = f"{person_id} ({confidence:.2f})"
        else:
            recognition_label = "Unknown"
        
        # Draw face number (top left)
        draw.rectangle([x1, y1 - 50, x1 + 100, y1], fill=box_color)
        draw.text((x1 + 5, y1 - 45), face_label, font=font, fill="white")
        
        # Draw recognition result (below face number)
        # Adjust text box size dynamically based on label length
        text_width, text_height = draw.textbbox((0,0), recognition_label, font=font)[2:] # Get width and height using textbbox
        
        # Position for recognition label text and its background box
        recognition_text_y_start = y1 - 25 # Start y for the text itself
        recognition_box_y1 = y1 - 30 # Top of the background box for recognition label
        recognition_box_y2 = y1 - 5   # Bottom of the background box for recognition label
        
        # Draw background for recognition label
        draw.rectangle([x1, recognition_box_y1, x1 + text_width + 10, recognition_box_y2], fill=box_color)
        # Draw recognition label text
        draw.text((x1 + 5, recognition_text_y_start), recognition_label, font=font, fill="white")
        
        # Print debug info
        if DEBUG:
            console.print(f"\n[bold magenta]{face_label}:[/bold magenta]")
            console.print(f"  [dim]Position:[/dim] ({x1}, {y1}, {x2}, {y2})")
            if person_id:
                console.print(f"  [green]Recognized as:[/green] {person_id}")
                console.print(f"  [dim]Confidence:[/dim] {confidence:.4f}")
            else:
                console.print("  [yellow]No match found[/yellow]")

    # Save and show result
    pil_img.save(result_path)
    console.print(Panel("[bold cyan]RECOGNITION SUMMARY[/bold cyan]", title="[yellow]Summary[/yellow]", expand=False))
    summary_table = Table(show_header=True, header_style="bold magenta")
    summary_table.add_column("Metric", style="dim", width=30)
    summary_table.add_column("Value")
    summary_table.add_row("Total faces detected", str(len(results)))
    summary_table.add_row("Recognized faces", str(sum(1 for r in results if r['person_id'])))
    summary_table.add_row("Recognition threshold", f"{RECOGNITION_THRESHOLD:.2f}")
    summary_table.add_row("Results saved to", result_path)
    console.print(summary_table)
    
    # Display the result image
    # pil_img.show() # Comment out for automated runs to avoid multiple windows

    return results, known_embeddings # Return results for potential automated evaluation



# This main function is for single runs, not used by the multi-threshold evaluation below.
# It's kept for now but could be refactored or removed if only multi-eval is needed.
# def main_original_single_run():
# ... (original main function content) ...


def evaluate_recognition(results, ground_truth_map, debug=False):
    correct_recognitions = 0
    incorrect_recognitions = 0 # Misidentified known people
    false_positives_on_unknown = 0 # NOT_IN_DATASET identified as known
    missed_known_faces = 0 # Known faces identified as Unknown
    correctly_unidentified_unknowns = 0 # NOT_IN_DATASET identified as Unknown

    # Ensure ground_truth_map keys are 1-indexed if results are processed 1-indexed
    # Or adjust indexing accordingly. Script uses 0-indexed for results list, 1-indexed for display.
    # Let's assume results are 0-indexed internally for processing.

    if debug:
        console.print(Panel("[bold cyan]AUTOMATED EVALUATION[/bold cyan]", title="[yellow]Evaluation[/yellow]", expand=False))
        eval_details_table = Table(title="Face Evaluation Details", show_header=True, header_style="bold magenta")
        eval_details_table.add_column("Face #", style="dim")
        eval_details_table.add_column("Ground Truth")
        eval_details_table.add_column("Recognized As")
        eval_details_table.add_column("Score")

    for i, result in enumerate(results):
        face_idx_1_based = i + 1
        gt_person = ground_truth_map.get(f"Face {face_idx_1_based}")
        recognized_person = result['person_id'] # This will be None if no match above threshold
        score_str = f"{result['confidence']:.4f}" if recognized_person else "N/A"

        if debug:
            eval_details_table.add_row(str(face_idx_1_based), str(gt_person), str(recognized_person), score_str)

        if gt_person == "NOT_IN_DATASET":
            if recognized_person is None: # Correctly not identified
                correctly_unidentified_unknowns += 1
            else: # Incorrectly identified as a known person
                false_positives_on_unknown += 1
        else: # Ground truth is a known person
            if recognized_person == gt_person: # Correctly identified
                correct_recognitions += 1
            elif recognized_person is None: # Should have been identified, but wasn't (below threshold)
                missed_known_faces += 1
            else: # Identified as the wrong known person
                incorrect_recognitions += 1
    
    total_known_gt = sum(1 for name in ground_truth_map.values() if name != "NOT_IN_DATASET")
    total_unknown_gt = sum(1 for name in ground_truth_map.values() if name == "NOT_IN_DATASET")

    summary = {
        "correct_recognitions": correct_recognitions,
        "incorrect_recognitions (misidentified_known)": incorrect_recognitions,
        "false_positives_on_unknown": false_positives_on_unknown,
        "missed_known_faces (FN)": missed_known_faces,
        "correctly_unidentified_unknowns (TN_unknown)": correctly_unidentified_unknowns,
        "total_detected_faces": len(results),
        "total_gt_known_faces_in_image": total_known_gt,
        "total_gt_unknown_faces_in_image": total_unknown_gt,
    }
    if debug:
        console.print(eval_details_table)
        console.print("\n  [bold]Evaluation Summary:[/bold]")
        summary_table = Table(show_header=False, box=None)
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="yellow")
        for key, value in summary.items():
            summary_table.add_row(key, str(value))
        console.print(summary_table)
    return summary

def run_single_evaluation_iteration(current_recognition_threshold, current_detection_confidence, recognition_model_name, cli_args, project_root_path, font_file_path, gt_map):
    # This function will encapsulate one run of the main logic
    DEBUG = cli_args.debug
    SHOW_ALL_SIMILARITIES = cli_args.show_similarities

    test_image_path = os.path.join(project_root_path, "source", "images", "test", "original.jpeg")
    result_image_dir = os.path.join(project_root_path, "source", "images", "test")
    os.makedirs(result_image_dir, exist_ok=True)
    
    # Update result_path to include all relevant parameters
    result_path = os.path.join(result_image_dir, f"result_eval_model_{recognition_model_name}_rec_{current_recognition_threshold:.2f}_det_{current_detection_confidence:.2f}.jpeg")

    if DEBUG:
        console.print(Panel(f"[bold cyan]RUNNING FOR MODEL: {recognition_model_name}, REC_THRESH: {current_recognition_threshold:.2f}, DET_CONF: {current_detection_confidence:.2f}[/bold cyan]", title="[yellow]Evaluation Iteration[/yellow]", expand=False))

    face_detector = FaceDetector( # Detector backend is fixed to InsightFace for now in this script
        backend=FaceDetector.BACKEND_INSIGHTFACE,
        model_size=(640, 640),
        device="auto",
        confidence_threshold=current_detection_confidence 
    )

    # Determine use_arcface based on recognition_model_name
    # This is a simplification. A more robust FaceRecognizer would take model_name directly.
    use_arcface_flag = True # Default for sface, arcface
    if recognition_model_name == 'opencv_dnn':
        use_arcface_flag = False
    # Note: If recognition_model_name is 'sface' or 'arcface', FaceRecognizer's internal logic
    # will try sface.onnx first, then arcface_r50.onnx if use_arcface_flag is True.
    # To strictly test 'arcface' even if 'sface' exists, FaceRecognizer would need modification.

    face_recognizer = FaceRecognizer(
        face_detector=face_detector,
        similarity_threshold=current_recognition_threshold,
        use_arcface=use_arcface_flag # Controls which type of recognizer model path is taken
    )

    target_contestants_for_debug = ["Tania", "阿妹", "Yanny", "阿 Yo", "Sinnie", "Elka", "Mei Mei", "阿蛋"]
    known_embeddings: Dict[str, List[np.ndarray]] = {}
    embeddings_base_dir = os.path.join(project_root_path, "source", "photo", "contestants", "embeddings")
    
    loaded_count = 0
    for contestant_name in target_contestants_for_debug:
        filename = f"{contestant_name}_embedding.npy"
        embedding_path = os.path.join(embeddings_base_dir, filename)
        if os.path.exists(embedding_path):
            try:
                embedding = np.load(embedding_path)
                if embedding.ndim == 2 and embedding.shape[0] == 1: embedding = embedding.flatten()
                elif embedding.ndim > 1: continue
                known_embeddings[contestant_name] = [embedding]
                loaded_count += 1
            except Exception as e:
                if DEBUG: console.print(f"[red]Error loading {contestant_name}:[/red] {e}")
    
    if DEBUG: console.print(f"[cyan]Loaded {loaded_count}/{len(target_contestants_for_debug)} target embeddings for this run.[/cyan]")

    for person_id, embeddings_list in known_embeddings.items():
        if embeddings_list and embeddings_list[0] is not None:
            face_recognizer.add_known_embedding(person_id, embeddings_list[0])

    image_cv = cv2.imread(test_image_path)
    if image_cv is None:
        console.print(f"[red]Failed to load test image at {test_image_path}[/red]")
        return None, {} 

    face_data = face_recognizer.detect_and_embed(image_cv)
    results = face_recognizer.identify_face(image_cv, detected_face_embeddings=face_data)

    if DEBUG and SHOW_ALL_SIMILARITIES:
        console.print(f"\n  [bold]Detailed Similarity Scores (Model: {recognition_model_name}, Rec: {current_recognition_threshold:.2f}, Det: {current_detection_confidence:.2f}):[/bold]")
        for i, (face_embedding, result) in enumerate(zip(face_data, results)):
            console.print(f"  [magenta]Face {i+1}[/magenta] (Recognized: {result['person_id'] if result['person_id'] else 'None'}, Score: {result['confidence']:.4f}):")
            similarity_table = Table(show_header=False, box=None)
            similarity_table.add_column("Contestant", style="cyan")
            similarity_table.add_column("Score", style="yellow")
            for contestant, embeddings_list in known_embeddings.items():
                similarity = face_recognizer._compute_similarity(face_embedding, embeddings_list[0])
                similarity_table.add_row(f"    vs {contestant}", f"{similarity:.4f}")
            console.print(similarity_table)
    
    pil_img = Image.fromarray(cv2.cvtColor(image_cv, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)
    try:
        font = ImageFont.truetype(font_file_path, 24)
    except IOError:
        font = ImageFont.load_default()
        if DEBUG: console.print("[yellow]Warning:[/yellow] Custom font not found. Using default font.")

    for i, result_item in enumerate(results, 1):
        bbox = result_item["bbox"]
        person_id = result_item["person_id"]
        confidence = result_item["confidence"]
        x1, y1, x2, y2 = map(int, bbox)
        box_color = "green" if person_id else "red"
        draw.rectangle([x1, y1, x2, y2], outline=box_color, width=2)
        face_label = f"Face {i}"
        rec_label = f"{person_id} ({confidence:.2f})" if person_id else "Unknown"
        
        text_y_offset = y1 - 10 if y1 - 10 > 0 else y1 + 10 
        draw.text((x1, text_y_offset - 25), face_label, font=font, fill=box_color)
        draw.text((x1, text_y_offset), rec_label, font=font, fill=box_color)

    pil_img.save(result_path)
    if DEBUG: console.print(f"[green]Saved result image for Model: {recognition_model_name}, Rec: {current_recognition_threshold:.2f}, Det: {current_detection_confidence:.2f} to {result_path}[/green]")

    eval_summary = evaluate_recognition(results, gt_map, debug=DEBUG)
    return results, eval_summary

# --- Bayesian Optimization Functions ---

# Removed problematic decorator from here
def objective_function(recognition_threshold, detection_confidence, recognition_model):
    global PROJECT_ROOT, FONT_PATH, GROUND_TRUTH_MAP, ARGS
    
    # Ensure dimensions are passed to use_named_args if it's not picking them up from global
    # This is a common pitfall. For safety, objective_function might need to be defined inside main
    # or DIMENSIONS passed explicitly if @use_named_args is outside a scope where DIMENSIONS is set.
    # For now, assuming it works or will be adjusted.

    if PROJECT_ROOT is None or FONT_PATH is None or GROUND_TRUTH_MAP is None or ARGS is None:
        console.print("[red]Error:[/red] Global paths/config not initialized for objective function.")
        return 0.0 # High penalty (assuming we minimize negative score)

    _, eval_summary = run_single_evaluation_iteration(
        current_recognition_threshold=recognition_threshold,
        current_detection_confidence=detection_confidence,
        recognition_model_name=recognition_model,
        cli_args=ARGS,
        project_root_path=PROJECT_ROOT,
        font_file_path=FONT_PATH,
        gt_map=GROUND_TRUTH_MAP
    )
    
    if not eval_summary:
        if ARGS.debug: console.print("[yellow]Evaluation failed for this iteration, returning low score.[/yellow]")
        return 1000.0 # Return a large value if eval fails (since we minimize)
    
    # Weighted score (higher is better, so we will return negative of this)
    # Adjust weights as needed
    score = (
        eval_summary["correct_recognitions"] * 2.0
        - eval_summary["incorrect_recognitions (misidentified_known)"] * 1.5 
        - eval_summary["false_positives_on_unknown"] * 2.5 # Higher penalty for FP on unknowns
        - eval_summary["missed_known_faces (FN)"] * 1.0
    )
    
    if ARGS.debug:
        console.print(f"[dim]Params: RecModel={recognition_model}, RecThresh={recognition_threshold:.2f}, DetConf={detection_confidence:.2f} -> Score: {score:.2f}[/dim]")

    return -score # skopt minimizes, so return negative of our maximization score

# Moved current_objective_function_for_skopt to global scope to fix PicklingError
# The @use_named_args decorator needs DIMENSIONS to be defined when this function is defined.
# DIMENSIONS is set globally in run_bayesian_optimization before gp_minimize is called,
# or within the __main__ block if optimization is not run.
# For this to work reliably, DIMENSIONS should ideally be defined at module level
# or passed explicitly. However, skopt's @use_named_args expects a global or closured `dimensions` list.
# We will ensure DIMENSIONS is set before this function is effectively used by gp_minimize.
# Hardcoding dimensions directly in the decorator to avoid issues with global variable resolution at definition time.
@use_named_args(dimensions=[
    Real(0.3, 0.9, name='recognition_threshold'),
    Real(0.2, 0.8, name='detection_confidence'),
    Categorical(['sface', 'arcface'], name='recognition_model')
])
def current_objective_function_for_skopt(recognition_threshold, detection_confidence, recognition_model):
    # This wrapper calls the main objective_function.
    # The decorator @use_named_args will use the `dimensions` argument passed to it.
    # If DIMENSIONS is updated globally before gp_minimize, this should work.
    # A more robust solution might involve dynamic decorator application or a class-based objective.
    return objective_function(recognition_threshold=recognition_threshold,
                              detection_confidence=detection_confidence,
                              recognition_model=recognition_model)

def run_bayesian_optimization(n_calls=30, n_random_starts=10):
    global DIMENSIONS, PROJECT_ROOT
    if not HAS_SKOPT:
        console.print("[yellow]Skipping Bayesian Optimization: scikit-optimize is not installed.[/yellow]")
        return None

    console.print(Panel(f"[bold cyan]Starting Bayesian optimization with {n_calls} total evaluations ({n_random_starts} random)...[/bold cyan]", title="[yellow]Bayesian Optimization[/yellow]", expand=False))
    
    # DIMENSIONS is now defined globally, so we use it directly.
    console.print(f"[dim]Optimizing parameters based on globally defined DIMENSIONS:[/dim]")
    console.print(f"[dim]- Recognition threshold: {DIMENSIONS[0].bounds if DIMENSIONS and len(DIMENSIONS) > 0 else 'N/A'}[/dim]")
    console.print(f"[dim]- Detection confidence: {DIMENSIONS[1].bounds if DIMENSIONS and len(DIMENSIONS) > 1 else 'N/A'}[/dim]")
    console.print(f"[dim]- Recognition models: {DIMENSIONS[2].categories if DIMENSIONS and len(DIMENSIONS) > 2 else 'N/A'}[/dim]")
    
    # Use the globally defined current_objective_function_for_skopt, which is already decorated with global DIMENSIONS
    result = gp_minimize(
        func=current_objective_function_for_skopt, 
        dimensions=DIMENSIONS, # Pass the global DIMENSIONS
        n_calls=n_calls,
        n_random_starts=n_random_starts,
        random_state=42, # For reproducibility
        verbose=True 
    )
    
    opt_result_path = os.path.join(PROJECT_ROOT, "source", "images", "test", "bayesian_optimization_results.pkl")
    dump(result, opt_result_path)
    console.print(f"[green]Bayesian optimization results saved to {opt_result_path}[/green]")
    return result

def analyze_optimization_results(result, project_root_path):
    if result is None:
        console.print("[yellow]No optimization result to analyze.[/yellow]")
        return None

    console.print(Panel("[bold cyan]BAYESIAN OPTIMIZATION RESULTS[/bold cyan]", title="[yellow]Optimization Analysis[/yellow]", expand=False))
    best_params = result.x
    best_score = -result.fun # Score was negated for minimization

    console.print(f"[bold]Best parameters found:[/bold]")
    opt_summary_table = Table(show_header=False, box=None)
    opt_summary_table.add_column("Parameter", style="cyan")
    opt_summary_table.add_column("Value", style="yellow")
    opt_summary_table.add_row("Recognition Model", str(best_params[2]))
    opt_summary_table.add_row("Recognition Threshold", f"{best_params[0]:.3f}")
    opt_summary_table.add_row("Detection Confidence", f"{best_params[1]:.3f}")
    opt_summary_table.add_row("Achieved Score", f"{best_score:.3f}")
    console.print(opt_summary_table)

    # Create and save plots
    try:
        fig_conv = plot_convergence(result)
        conv_plot_path = os.path.join(project_root_path, "source", "images", "test", "optimization_convergence.png")
        fig_conv.figure.savefig(conv_plot_path) # Access figure from Axes object
        plt.close(fig_conv.figure) # Close figure to free memory
        console.print(f"[green]Convergence plot saved to {conv_plot_path}[/green]")

        # plot_objective might create multiple subplots depending on dimensions
        # It returns a list of Axes objects
        # axes_obj = plot_objective(result, n_points=30) # n_points for smoother plot
        # obj_plot_path = os.path.join(project_root_path, "source", "images", "test", "optimization_objective.png")
        # # Assuming plot_objective returns a figure or can be made to save
        # # This part might need adjustment based on skopt's plotting API for saving multi-plots
        # if isinstance(axes_obj, list) and hasattr(axes_obj[0], 'figure'):
        #     axes_obj[0].figure.savefig(obj_plot_path)
        #     plt.close(axes_obj[0].figure)
        # elif hasattr(axes_obj, 'figure'): # If it's a single figure object
        #      axes_obj.figure.savefig(obj_plot_path)
        #      plt.close(axes_obj.figure)
        # print(f"Objective plot saved to {obj_plot_path}")
        # Note: plot_objective can be complex for >2D. Partial dependence plots are often better.
        # For simplicity, we'll skip saving plot_objective directly if it's problematic.
        console.print("[dim]Objective plots can be generated manually using skopt.plots.plot_objective(result).[/dim]")

    except Exception as e:
        console.print(f"[red]Could not generate/save optimization plots:[/red] {e}")

    # Save all evaluated points and their scores to a CSV
    trials_data = []
    for i in range(len(result.x_iters)):
        params = result.x_iters[i]
        score = -result.func_vals[i]
        trials_data.append({
            'recognition_model': params[2],
            'recognition_threshold': params[0],
            'detection_confidence': params[1],
            'score': score
        })
    
    trials_df = pd.DataFrame(trials_data)
    trials_csv_path = os.path.join(project_root_path, "source", "images", "test", "optimization_trials_summary.csv")
    trials_df.to_csv(trials_csv_path, index=False)
    console.print(f"[green]All optimization trials saved to {trials_csv_path}[/green]")
    
    return trials_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Optimize or test face recognition parameters.")
    
    # Arguments for Grid Search (existing, but might be superseded by optimization)
    parser.add_argument("--start_threshold", type=float, default=0.3, help="Start recognition similarity threshold for grid search.")
    parser.add_argument("--end_threshold", type=float, default=0.8, help="End recognition similarity threshold for grid search.")
    parser.add_argument("--step_threshold", type=float, default=0.05, help="Step for recognition similarity threshold for grid search.")
    parser.add_argument("--start_confidence", type=float, default=0.3, help="Start detection confidence for grid search.")
    parser.add_argument("--end_confidence", type=float, default=0.7, help="End detection confidence for grid search.")
    parser.add_argument("--step_confidence", type=float, default=0.1, help="Step for detection confidence for grid search.")

    # Arguments for Bayesian Optimization
    parser.add_argument("--optimize", action="store_true", help="Run Bayesian optimization.")
    parser.add_argument("--n_calls", type=int, default=50, help="Number of calls (evaluations) for Bayesian optimization.")
    parser.add_argument("--n_random_starts", type=int, default=10, help="Number of random initial points for Bayesian optimization.")
    
    # General arguments
    parser.add_argument("--fixed_recognition_model", type=str, default="sface", choices=['sface', 'arcface', 'opencv_dnn'], help="Fixed recognition model if not optimizing it. Note: 'opencv_dnn' is excluded from --optimize runs due to errors.")
    parser.add_argument("--fixed_recognition_threshold", type=float, help="Fixed recognition threshold if not optimizing/gridding.")
    parser.add_argument("--fixed_detection_confidence", type=float, help="Fixed detection confidence if not optimizing/gridding.")
    parser.add_argument("--debug", action="store_true", help="Enable debug printing.")
    parser.add_argument("--show_similarities", action="store_true", help="Show all similarity scores in debug output.")
    
    ARGS = parser.parse_args() # Store args globally

    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
    FONT_PATH = os.path.join(PROJECT_ROOT, "fonts", "SourceHanSansTC-VF.ttf")
    
    ground_truth_map_input = [
        {'Face 1':'阿 Yo'}, {'Face 2':'Sinnie'}, {'Face 3':'阿蛋'},
        {'Face 4':'Yanny'}, {'Face 5':'Elka'}, {'Face 6':'Tania'},
        {'Face 7':'Mei Mei'}, {'Face 8':'阿妹'},
        {'Face 9':'NOT_IN_DATASET'}, {'Face 10':'NOT_IN_DATASET'}
    ]
    GROUND_TRUTH_MAP = {k: v for item in ground_truth_map_input for k, v in item.items()}

    if ARGS.optimize:
        if not HAS_SKOPT:
            console.print("[red]Cannot run optimization because scikit-optimize is not installed. Exiting.[/red]")
            exit(1)
        
        # Define the dimensions for the objective_function decorator at the top level
        # This is a bit of a workaround for how @use_named_args works.
        # The decorator needs the dimensions at the time the function is defined.
        # We will set the global DIMENSIONS here, and the objective_function's decorator
        # will need to be adjusted or the function wrapped.
        # For now, run_bayesian_optimization defines its own local wrapper for the objective function.
        
        opt_result = run_bayesian_optimization(ARGS.n_calls, ARGS.n_random_starts)
        if opt_result:
            analyze_optimization_results(opt_result, PROJECT_ROOT)
            
            # Optionally, run a final test with the best found parameters
            best_params_from_opt = opt_result.x
            console.print(Panel("[bold cyan]FINAL TEST WITH BEST OPTIMIZED PARAMETERS[/bold cyan]", title="[yellow]Final Test[/yellow]", expand=False))
            _, final_eval_summary = run_single_evaluation_iteration(
                current_recognition_threshold=best_params_from_opt[0],
                current_detection_confidence=best_params_from_opt[1],
                recognition_model_name=best_params_from_opt[2],
                cli_args=ARGS,
                project_root_path=PROJECT_ROOT,
                font_file_path=FONT_PATH,
                gt_map=GROUND_TRUTH_MAP
            )
            if final_eval_summary:
                console.print("[bold green]Final Evaluation Summary (Best Optimized):[/bold green]")
                final_summary_table = Table(show_header=False, box=None)
                final_summary_table.add_column("Metric", style="cyan")
                final_summary_table.add_column("Value", style="yellow")
                for key, val in final_eval_summary.items():
                    final_summary_table.add_row(key, str(val))
                # Add detection_confidence and recognition_model to the summary for clarity
                final_eval_summary['recognition_threshold'] = best_params_from_opt[0]
                final_eval_summary['detection_confidence'] = best_params_from_opt[1]
                final_eval_summary['recognition_model'] = best_params_from_opt[2]
                final_summary_table.add_row("recognition_threshold (optimized)", f"{best_params_from_opt[0]:.3f}")
                final_summary_table.add_row("detection_confidence (optimized)", f"{best_params_from_opt[1]:.3f}")
                final_summary_table.add_row("recognition_model (optimized)", str(best_params_from_opt[2]))
                console.print(final_summary_table)
                
                # Save this single best result to a specific CSV
                best_summary_df = pd.DataFrame([final_eval_summary])
                best_summary_path = os.path.join(PROJECT_ROOT, "source", "images", "test", "best_optimized_run_summary.csv")
                best_summary_df.to_csv(best_summary_path, index=False)
                console.print(f"[green]Summary for best optimized run saved to {best_summary_path}[/green]")

    else: # Fallback to grid search or single run if --optimize is not used
        console.print(Panel("[bold cyan]Running Grid Search / Fixed Parameter Evaluation[/bold cyan]", title="[yellow]Grid Search/Fixed Params[/yellow]", expand=False))
        recognition_models_to_test = [ARGS.fixed_recognition_model] # For now, grid search only on one model
        
        # Use fixed values if provided, otherwise use grid search ranges
        if ARGS.fixed_recognition_threshold is not None:
            recognition_thresholds_to_test = [ARGS.fixed_recognition_threshold]
        else:
            recognition_thresholds_to_test = np.arange(ARGS.start_threshold, ARGS.end_threshold + ARGS.step_threshold, ARGS.step_threshold)
        
        if ARGS.fixed_detection_confidence is not None:
            detection_confidences_to_test = [ARGS.fixed_detection_confidence]
        else:
            detection_confidences_to_test = np.arange(ARGS.start_confidence, ARGS.end_confidence + ARGS.step_confidence, ARGS.step_confidence)

        all_eval_summaries = []
        best_score = -float('inf')
        best_params_grid = {}

        console.print(f"[bold]Models to test:[/bold] {recognition_models_to_test}")
        console.print(f"[bold]Detection confidences:[/bold] {detection_confidences_to_test}")
        console.print(f"[bold]Recognition thresholds:[/bold] {recognition_thresholds_to_test}")

        for model_name in recognition_models_to_test:
            console.print(Panel(f"[bold cyan]Evaluating Model: {model_name}[/bold cyan]", title="[yellow]Model Evaluation[/yellow]", expand=False))
            for det_conf in detection_confidences_to_test:
                current_det_conf_rounded = round(det_conf, 2)
                console.print(f"\n--- [bold]Evaluating for Detection Confidence: {current_det_conf_rounded}[/bold] ---")
                for rec_thresh in recognition_thresholds_to_test:
                    current_rec_thresh_rounded = round(rec_thresh, 2)
                    
                    _, eval_summary = run_single_evaluation_iteration(
                        current_rec_thresh_rounded,
                        current_det_conf_rounded,
                        model_name, # Pass model name
                        ARGS,
                        PROJECT_ROOT,
                        None, 
                        FONT_PATH,
                        GROUND_TRUTH_MAP
                    )
                    
                    if eval_summary: 
                        eval_summary['recognition_model'] = model_name
                        eval_summary['recognition_threshold'] = current_rec_thresh_rounded
                        eval_summary['detection_confidence'] = current_det_conf_rounded
                        all_eval_summaries.append(eval_summary)
                    
                        current_score = (
                            eval_summary["correct_recognitions"] * 2 
                            - eval_summary["incorrect_recognitions (misidentified_known)"] * 1.5
                            - eval_summary["false_positives_on_unknown"] * 2.5 
                            - eval_summary["missed_known_faces (FN)"]
                        )

                        if current_score > best_score:
                            best_score = current_score
                            best_params_grid = {
                                'recognition_model': model_name,
                                'recognition_threshold': current_rec_thresh_rounded,
                                'detection_confidence': current_det_conf_rounded
                            }
        
        console.print(Panel("[bold cyan]OVERALL GRID EVALUATION RESULTS[/bold cyan]", title="[yellow]Grid Results[/yellow]", expand=False))
        if all_eval_summaries:
            summary_df = pd.DataFrame(all_eval_summaries)
            cols_order = ['recognition_model', 'detection_confidence', 'recognition_threshold', 
                          'correct_recognitions', 'incorrect_recognitions (misidentified_known)', 
                          'missed_known_faces (FN)', 'false_positives_on_unknown', 
                          'correctly_unidentified_unknowns (TN_unknown)', 'total_detected_faces',
                          'total_gt_known_faces_in_image', 'total_gt_unknown_faces_in_image']
            summary_df = summary_df[[col for col in cols_order if col in summary_df.columns]]
            
            # Print DataFrame as a Rich Table
            grid_results_table = Table(title="Grid Search Evaluation Summary")
            for col in summary_df.columns:
                grid_results_table.add_column(col)
            for index, row in summary_df.iterrows():
                grid_results_table.add_row(*[str(x) for x in row.values])
            console.print(grid_results_table)

            if best_params_grid:
                 console.print(f"\n[bold green]Best parameters (Grid):[/bold green] Model: {best_params_grid['recognition_model']}, DetConf: {best_params_grid['detection_confidence']:.2f}, RecThresh: {best_params_grid['recognition_threshold']:.2f} (Score: {best_score:.2f})")
            
            summary_csv_path = os.path.join(PROJECT_ROOT, "source", "images", "test", "evaluation_summary_grid_model_conf_thresh.csv")
            summary_df.to_csv(summary_csv_path, index=False)
            console.print(f"[green]Grid evaluation summary saved to: {summary_csv_path}[/green]")

            if best_params_grid:
                console.print(f"\n[dim]To view image for best grid parameters, check for file matching:[/dim]")
                console.print(f"[dim]source/images/test/result_eval_model_{best_params_grid['recognition_model']}_rec_{best_params_grid['recognition_threshold']:.2f}_det_{best_params_grid['detection_confidence']:.2f}.jpeg[/dim]")
        else:
            console.print("[yellow]No evaluation summaries were generated from grid search.[/yellow]")
