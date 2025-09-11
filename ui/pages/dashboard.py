"""
Dashboard page for the NiceGUI application.
"""

from nicegui import ui, app
from src.services.video_processor import VideoProcessor
from src.database.chroma_setup import ChromaDBManager


def create():
    """Create the dashboard page content."""

    video_processor: VideoProcessor = app.storage.general.get("video_processor")
    db_manager: ChromaDBManager = app.storage.general.get("db_manager")

    with ui.row().classes("w-full justify-around"):
        with ui.card().classes("w-1/3 text-center"):
            ui.label("Available Videos").classes("text-lg font-bold")
            if video_processor:
                videos = video_processor.get_available_videos()
                ui.label(f"{len(videos)}").classes("text-4xl font-bold")
            else:
                ui.label("N/A").classes("text-4xl font-bold")

        with ui.card().classes("w-1/3 text-center"):
            ui.label("Contestants in DB").classes("text-lg font-bold")
            if db_manager:
                stats = db_manager.get_database_stats()
                ui.label(f'{stats.get("total_embeddings", "N/A")}').classes(
                    "text-4xl font-bold"
                )
            else:
                ui.label("N/A").classes("text-4xl font-bold")

    ui.separator().classes("my-8")

    ui.label("Recent Activity").classes("text-2xl font-bold mb-4")

    # Placeholder for recent activity
    with ui.card():
        ui.label("No recent activity to display.")
