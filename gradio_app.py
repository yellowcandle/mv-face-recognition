"""
Modern Gradio Web Interface for MV Face Recognition System.
Provides real-time camera processing, image/video analysis, and configuration management.
"""

import warnings
import gradio as gr
import pandas as pd
import logging
from typing import Optional
from datetime import datetime

# Import our modular components
from src.config.settings import get_config, save_config
from src.core.face_detector import FaceDetector
from src.services.embedding_service import EmbeddingService
from src.services.recognition_service import RecognitionService
from src.services.video_processing_service import VideoProcessingService
from src.services.visualization import VisualizationService

# Suppress warnings BEFORE any other imports
warnings.filterwarnings("ignore", message=".*rcond.*")
warnings.filterwarnings("ignore", category=FutureWarning, module="insightface")
warnings.filterwarnings("ignore", message=".*Albumentations.*")
warnings.filterwarnings("ignore", category=UserWarning, module="albumentations")
warnings.filterwarnings("ignore", message=".*browser-compatible.*")
warnings.filterwarnings("ignore", message=".*does not have browser-compatible.*")
warnings.filterwarnings(
    "ignore", category=UserWarning, module="gradio.components.video"
)
warnings.filterwarnings("ignore", category=UserWarning, module="gradio")

# Hugging Face Spaces GPU support
try:
    import spaces
    HF_SPACES_GPU = True
except ImportError:
    # Fallback decorator for local development
    def spaces_gpu_decorator(*args, **kwargs):
        def decorator(func):
            return func
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return decorator
    
    spaces = type('spaces', (), {'GPU': spaces_gpu_decorator})()
    HF_SPACES_GPU = False

# Global instances to avoid re-initialization
_global_detector: Optional[FaceDetector] = None

def get_face_detector(force_cpu=False) -> Optional[FaceDetector]:
    """Initializes and returns a global FaceDetector instance."""
    global _global_detector
    if _global_detector is None:
        try:
            config = get_config()
            if force_cpu:
                config.recognition.use_gpu = False
            
            # On ZeroGPU, detector must be initialized within a @spaces.GPU function.
            # We return None here, and the GPU-decorated function will create it.
            if HF_SPACES_GPU and not force_cpu:
                logger.info("ZeroGPU environment detected. Deferring FaceDetector initialization.")
                return None

            logger.info(f"Initializing FaceDetector (CPU: {force_cpu})...")
            _global_detector = FaceDetector(config, force_cpu_only=force_cpu)
            logger.info("✅ Face detector initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize face detector: {e}", exc_info=True)
            _global_detector = None
    return _global_detector

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FaceRecognitionApp:
    """Main Gradio application for face recognition."""

    def __init__(self):
        """Initialize the application."""
        self.config = get_config()
        self.processing_stats = {
            "total_processed": 0,
            "faces_detected": 0,
            "faces_recognized": 0,
            "last_updated": datetime.now(),
        }
        self.title_to_path_mapping = {}
        
        # Initialize services
        self.face_detector: Optional[FaceDetector] = None # Will be set in GPU context
        self.embedding_service: Optional[EmbeddingService] = None
        self.recognition_service: Optional[RecognitionService] = None
        self.video_processing_service: Optional[VideoProcessingService] = None
        self.visualization_service: Optional[VisualizationService] = None

        # UI state
        self.processing_video = False

    def _initialize_system(self, force_cpu=False):
        """Initialize all services required for the application."""
        if self.video_processing_service is not None and not force_cpu:
            return # Already initialized

        logger.info(f"Initializing system (force_cpu={force_cpu})...")
        try:
            self.face_detector = get_face_detector(force_cpu=force_cpu)
            if self.face_detector is None and not HF_SPACES_GPU:
                 raise RuntimeError("Failed to initialize FaceDetector.")

            # Services that don't depend on a live detector can be initialized now.
            self.recognition_service = RecognitionService(use_chroma=self.config.recognition.enable_chromadb)
            self.visualization_service = VisualizationService()
            
            # Services that need a detector.
            if self.face_detector:
                self._initialize_detector_dependent_services()

        except Exception as e:
            logger.error(f"System initialization failed: {e}", exc_info=True)
            gr.Error(f"Failed to initialize system: {e}")

    def _initialize_detector_dependent_services(self):
        """Initializes services that require a FaceDetector instance."""
        if self.face_detector is None:
            logger.error("Cannot initialize dependent services without a FaceDetector.")
            return

        logger.info("Initializing detector-dependent services...")
        contestants_dir = self.config.project_root / "source/photo/contestants"
        contestant_info_path = self.config.project_root / "contestant_info.csv"

        self.embedding_service = EmbeddingService(self.face_detector, str(contestants_dir), str(contestant_info_path))
        self.video_processing_service = VideoProcessingService(self.face_detector, self.recognition_service)
        
        # Load embeddings
        self._load_all_embeddings()
        logger.info("✅ Detector-dependent services initialized.")

    def _load_all_embeddings(self):
        """Load all known face embeddings using the embedding service."""
        if not self.embedding_service:
            logger.error("Embedding service not initialized.")
            return
        try:
            all_names = self.embedding_service.contestant_info["暱稱"].tolist()
            self.embedding_service.load_embeddings_for_contestants(all_names)
            logger.info(f"Loaded {len(self.embedding_service.known_embeddings)} contestant embeddings.")
        except Exception as e:
            logger.error(f"Failed to load embeddings: {e}", exc_info=True)

    def get_available_videos(self):
        """Get list of available videos with titles from the source directory."""
        try:
            from src.config.video_titles import VIDEO_TITLE_MAPPING
        except ImportError:
            VIDEO_TITLE_MAPPING = {}
        
        videos_dir = self.config.project_root / "source/videos"
        if not videos_dir.exists():
            logger.warning(f"Videos directory not found: {videos_dir}")
            return [], {}

        video_files = []
        title_to_path_mapping = {}
        for ext in ["*.mp4", "*.mov", "*.avi"]:
            for video_file in videos_dir.glob(ext):
                display_title = VIDEO_TITLE_MAPPING.get(video_file.name, video_file.stem)
                video_files.append(display_title)
                title_to_path_mapping[display_title] = str(video_file)
        
        self.title_to_path_mapping = title_to_path_mapping
        return sorted(video_files), title_to_path_mapping

    def get_video_titles_for_dropdown(self):
        """Get just the video titles for the dropdown."""
        video_titles, _ = self.get_available_videos()
        return video_titles

    def get_video_path_from_title(self, title):
        """Get the file path from the selected title."""
        if not self.title_to_path_mapping:
            self.get_available_videos()
        return self.title_to_path_mapping.get(title, title)

    def _create_timeline_data(self, results_df):
        """Create timeline data for native Gradio Dataframe component."""
        try:
            if results_df is None or results_df.empty:
                return [], ["All"], "No timeline data available"

            # Ensure required columns exist
            if "Name" not in results_df.columns:
                return [], ["All"], "Timeline data is missing 'Name' column."

            # Group by contestant and calculate statistics
            timeline_data = []
            contestant_stats = {}

            for _, row in results_df.iterrows():
                name = str(row.get("Name", "Unknown"))
                if name == "Unknown":
                    continue
                
                if name not in contestant_stats:
                    contestant_stats[name] = {"appearances": 0}
                contestant_stats[name]["appearances"] += 1

                timeline_data.append([
                    name,
                    row.get("Time", "00:00"),
                    int(row.get("Frame", 0)),
                    0, # Sequence number (placeholder)
                    contestant_stats[name]["appearances"]
                ])

            contestant_choices = ["All"] + sorted(list(contestant_stats.keys()))
            total_contestants = len(contestant_stats)
            total_appearances = len(results_df)

            stats_html = f"""
            <div style="padding: 10px; background: #f8f9fa; border-radius: 8px; margin: 10px 0;">
                <h4>📊 Recognition Statistics</h4>
                <p><strong>👥 Contestants Detected:</strong> {total_contestants}</p>
                <p><strong>📍 Total Appearances:</strong> {total_appearances}</p>
            </div>
            """
            return timeline_data, contestant_choices, stats_html
        except Exception as e:
            logger.error(f"Error creating timeline data: {e}", exc_info=True)
            return [], ["All"], f"Error creating timeline: {str(e)}"

    def generate_umap_visualization(self, detected_faces_data):
        """Generate UMAP visualization for detected faces."""
        if not self.visualization_service or not self.embedding_service:
            logger.error("Visualization or Embedding service is not initialized.")
            return None
        
        try:
            logger.info(f"Starting UMAP generation with {len(detected_faces_data)} face detections")
            detected_embeddings = [face.normed_embedding for face, name, conf in detected_faces_data if face.normed_embedding is not None]
            detected_labels = [name for face, name, conf in detected_faces_data if face.normed_embedding is not None]

            if not detected_embeddings:
                logger.warning("No valid embeddings found for UMAP plot.")
                return None

            gallery_embeddings = self.embedding_service.get_known_embeddings(normalize=False)
            gallery_names = {name: name for name in gallery_embeddings.keys()}

            umap_plot = self.visualization_service.generate_umap_plot(
                detected_embeddings=detected_embeddings,
                gallery_embeddings=gallery_embeddings,
                gallery_names=gallery_names,
                detected_labels=detected_labels,
            )
            logger.info("UMAP plot generated successfully")
            return umap_plot
        except Exception as e:
            logger.error(f"Error generating UMAP visualization: {e}", exc_info=True)
            return None

    def process_uploaded_video(self, video_path, progress=gr.Progress()):
        """Process an uploaded video file with ZeroGPU awareness."""
        if not video_path:
            return None, "No video provided", ([], ["All"], "")

        try:
            if HF_SPACES_GPU:
                return self._process_video_gpu(video_path, progress)
            else:
                return self._process_video_cpu(video_path, progress)
        except Exception as e:
            logger.error(f"Video processing failed: {e}", exc_info=True)
            return None, f"An error occurred: {e}", ([], ["All"], "")

    @spaces.GPU(duration=60)
    def _warmup_gpu(self):
        """Warmup function to ensure GPU decorator is registered during startup."""
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return "GPU warmed up"

    @spaces.GPU(duration=300)
    def _process_video_gpu(self, video_path, progress):
        """GPU-accelerated video processing."""
        self._initialize_system(force_cpu=False)
        if not self.video_processing_service:
            return None, "Failed to initialize GPU processing services.", ([], ["All"], "")
        return self._process_video_core(video_path, progress)

    def _process_video_cpu(self, video_path, progress):
        """CPU-only video processing fallback."""
        self._initialize_system(force_cpu=True)
        if not self.video_processing_service:
            return None, "Failed to initialize CPU processing services.", ([], ["All"], "")
        return self._process_video_core(video_path, progress)

    def _process_video_core(self, video_path, progress):
        """Core video processing logic using the VideoProcessingService."""
        self.processing_video = True
        
        known_embeddings = self.embedding_service.get_known_embeddings()
        
        output_video_path, results = self.video_processing_service.process_video(
            video_path,
            known_embeddings,
            self.config.recognition.similarity_threshold,
            self.config.recognition.frame_skip,
            self.config.ui.enhanced_ui,
            progress
        )
        
        self.processing_video = False

        if not output_video_path:
            summary = "Video processing failed. Check logs for details."
            timeline_bundle = ([], ["All"], summary)
            return None, summary, timeline_bundle

        summary = f"📊 Processing complete. Found {len(results)} recognition events."
        if results:
            results_df = pd.DataFrame(results)
            timeline_data, choices, stats_html = self._create_timeline_data(results_df)
            summary += f"\nRecognized {len(choices)-1} unique contestants."
        else:
            timeline_data, choices, stats_html = [], ["All"], "No faces recognized."

        timeline_bundle = (timeline_data, choices, stats_html)
        return output_video_path, summary, timeline_bundle

    def update_settings(self, *args):
        """Update system settings."""
        try:
            (
                self.config.recognition.similarity_threshold,
                self.config.recognition.detection_threshold,
                self.config.recognition.frame_skip,
                self.config.recognition.max_faces_per_frame,
                self.config.recognition.use_gpu,
                self.config.recognition.enable_chromadb,
                self.config.ui.enhanced_ui,
            ) = args
            save_config()
            
            # Re-initialize services with new settings on next run
            global _global_detector
            _global_detector = None
            self.video_processing_service = None
            
            return "Settings updated successfully! Services will be reinitialized on next run."
        except Exception as e:
            logger.error(f"Settings update error: {e}", exc_info=True)
            return f"Error updating settings: {e}"

    def _filter_timeline_data(self, timeline_data, search_query, filter_contestant):
        """Filter timeline data based on search query and contestant filter."""
        if not timeline_data:
            return []
        
        df = pd.DataFrame(timeline_data, columns=["Contestant", "Time", "Frame", "Sequence", "Appearances"])
        
        if filter_contestant and filter_contestant != "All":
            df = df[df["Contestant"] == filter_contestant]
        
        if search_query:
            df = df[df["Contestant"].str.contains(search_query, case=False, na=False)]
            
        return df.values.tolist()

# Global app instance
app_instance = None

def get_app():
    """Get or create the global app instance."""
    global app_instance
    if app_instance is None:
        app_instance = FaceRecognitionApp()
        # Initialize for non-GPU environments immediately
        if not HF_SPACES_GPU:
            app_instance._initialize_system()
    return app_instance

def create_gradio_interface():
    """Create the main Gradio interface with a simplified structure."""
    with gr.Blocks(title="🎬 MV Face Recognition System") as demo:
        gr.Markdown("# 🎬 MV Face Recognition System")
        gr.Markdown("*Advanced AI-powered face recognition for video analysis*")

        with gr.Tabs():
            with gr.Tab("🎬 Video Processing"):
                with gr.Row():
                    with gr.Column(scale=1):
                        video_dropdown = gr.Dropdown(
                            choices=get_app().get_video_titles_for_dropdown(),
                            label="📹 Choose Video",
                        )
                        refresh_videos_btn = gr.Button("🔄 Refresh Video List")
                        video_button = gr.Button("▶️ Process Video", variant="primary")
                    with gr.Column(scale=2):
                        video_output = gr.Video(label="🎯 Processed Video")
                        video_results = gr.Textbox(label="📋 Processing Results", lines=5)

                with gr.Group():
                    gr.Markdown("### 🎯 Recognition Timeline")
                    with gr.Row():
                        contestant_search = gr.Textbox(label="🔍 Search Contestants")
                        contestant_filter = gr.Dropdown(label="📋 Filter by Contestant", choices=["All"], value="All")
                    timeline_stats = gr.HTML()
                    recognition_timeline = gr.Dataframe(
                        headers=["👤 Contestant", "⏰ Time", "🎬 Frame", "📊 Sequence", "📍 Appearances"],
                        datatype=["str", "str", "number", "number", "number"],
                    )

                # Event Handlers for Video Processing
                def process_video_wrapper(dropdown_title, progress=gr.Progress()):
                    app = get_app()
                    video_path = app.get_video_path_from_title(dropdown_title)
                    if not video_path:
                        return None, "Please select a video.", ([], ["All"], "")
                    
                    output_path, summary, timeline_bundle = app.process_uploaded_video(video_path, progress)
                    timeline_data, _, _ = timeline_bundle
                    return output_path, summary, timeline_data, timeline_bundle

                def update_timeline_display(timeline_bundle):
                    timeline_data, choices, stats_html = timeline_bundle
                    return timeline_data, gr.Dropdown(choices=choices, value="All"), stats_html

                full_timeline_data = gr.State(value=[])
                timeline_bundle_state = gr.State()

                video_button.click(
                    process_video_wrapper,
                    inputs=[video_dropdown],
                    outputs=[video_output, video_results, full_timeline_data, timeline_bundle_state]
                ).then(
                    update_timeline_display,
                    inputs=[timeline_bundle_state],
                    outputs=[recognition_timeline, contestant_filter, timeline_stats]
                )

                def filter_timeline_wrapper(search, flt, full_data):
                    return get_app()._filter_timeline_data(full_data, search, flt)

                contestant_search.change(filter_timeline_wrapper, inputs=[contestant_search, contestant_filter, full_timeline_data], outputs=[recognition_timeline])
                contestant_filter.change(filter_timeline_wrapper, inputs=[contestant_search, contestant_filter, full_timeline_data], outputs=[recognition_timeline])
                refresh_videos_btn.click(lambda: gr.Dropdown(choices=get_app().get_video_titles_for_dropdown()), outputs=[video_dropdown])

            with gr.Tab("⚙️ Settings"):
                gr.Markdown("## ⚙️ System Configuration")
                with gr.Row():
                    with gr.Column():
                        sim_threshold = gr.Slider(0.1, 0.9, value=get_app().config.recognition.similarity_threshold, step=0.02, label="🎯 Similarity Threshold")
                        det_threshold = gr.Slider(0.05, 0.8, value=get_app().config.recognition.detection_threshold, step=0.02, label="🔍 Detection Threshold")
                        frame_skip = gr.Slider(1, 120, value=get_app().config.recognition.frame_skip, step=1, label="⏭️ Frame Skip")
                        max_faces = gr.Slider(1, 50, value=get_app().config.recognition.max_faces_per_frame, step=1, label="👥 Max Faces per Frame")
                    with gr.Column():
                        use_gpu = gr.Checkbox(value=get_app().config.recognition.use_gpu, label="⚡ Use GPU Acceleration")
                        enable_chromadb = gr.Checkbox(value=get_app().config.recognition.enable_chromadb, label="🗄 Enable ChromaDB")
                        enhanced_ui = gr.Checkbox(value=get_app().config.ui.enhanced_ui, label="✨ Enhanced UI")
                        settings_button = gr.Button("💾 Save Settings", variant="primary")
                        settings_status = gr.HTML()

                settings_button.click(
                    get_app().update_settings,
                    inputs=[sim_threshold, det_threshold, frame_skip, max_faces, use_gpu, enable_chromadb, enhanced_ui],
                    outputs=[settings_status]
                )

            with gr.Tab("🗺️ UMAP Visualization"):
                gr.Markdown("## 🗺️ Face Embedding Visualization (UMAP)")
                with gr.Row():
                    with gr.Column(scale=2):
                        umap_plot = gr.Plot(label="Face Embedding UMAP")
                    with gr.Column(scale=1):
                        umap_video_dropdown = gr.Dropdown(choices=get_app().get_video_titles_for_dropdown(), label="Select Video for Analysis")
                        generate_umap_btn = gr.Button("🗺️ Generate UMAP", variant="primary")
                        umap_status = gr.HTML("Select a video to generate UMAP.")

                def generate_umap_wrapper(video_title):
                    app = get_app()
                    if not video_title:
                        return None, "Please select a video."
                    
                    # Ensure services are initialized
                    if not app.video_processing_service:
                        app._initialize_system()

                    video_path = app.get_video_path_from_title(video_title)
                    
                    known_embeddings = app.embedding_service.get_known_embeddings()

                    all_matches = app.video_processing_service.get_all_matches_from_video(
                        video_path,
                        known_embeddings,
                        app.config.recognition.similarity_threshold,
                        app.config.recognition.frame_skip
                    )
                    if not all_matches:
                        return None, "No faces detected in the video."
                    
                    fig = app.generate_umap_visualization(all_matches)
                    return fig, f"✅ Generated UMAP for {len(all_matches)} detected faces."

                generate_umap_btn.click(generate_umap_wrapper, inputs=[umap_video_dropdown], outputs=[umap_plot, umap_status])

    return demo

def launch_app():
    """Launch the Gradio application."""
    try:
        # Warmup GPU decorator registration for ZeroGPU
        if HF_SPACES_GPU:
            app = get_app()
            try:
                app._warmup_gpu()
                logger.info("✅ GPU decorator registered successfully")
            except Exception as warmup_error:
                logger.warning(f"GPU warmup failed (continuing anyway): {warmup_error}")
        
        demo = create_gradio_interface()
        demo.launch(server_name="0.0.0.0", server_port=7860, share=False, debug=True)
    except Exception as e:
        logger.error(f"Failed to launch app: {e}", exc_info=True)

if __name__ == "__main__":
    launch_app()
