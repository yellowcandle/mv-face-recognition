"""CLI entry points for MV Face Recognition System."""

from .main import main as mv_face_recognition_main
from .gradio_launcher import launch_gradio
from .generate_catalogue import generate_catalogue_main

__all__ = ['mv_face_recognition_main', 'launch_gradio', 'generate_catalogue_main']