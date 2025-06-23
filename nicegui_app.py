m#!/usr/bin/env python3
"""
MV Face Recognition - NiceGUI Edition
A modern, real-time UI for face recognition in music videos.
"""

import logging
from nicegui import ui, app
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import backend services and UI components
try:
    from src.services.video_processor import VideoProcessor
    from src.database.chroma_setup import ChromaDBManager
    from ui.theme import theme
    from ui.pages import dashboard, video_processing, database_manager, settings
except ImportError as e:
    logger.error(f"Error importing modules: {e}")
    # We can't use ui.notify here as the app isn't running yet.
    print(f"Error importing modules: {e}")


# --- App Setup ---

@app.on_start
async def startup():
    """Initialize backend services on application startup."""
    try:
        app.storage.general['video_processor'] = VideoProcessor()
        app.storage.general['db_manager'] = ChromaDBManager()
        logger.info("Backend services initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize backend services: {e}")
        app.storage.general['error'] = str(e)

# --- UI Layout ---

@ui.page('/')
def index_page():
    """Main page layout and navigation."""
    # Set theme
    theme.set_theme()

    # Check for initialization errors
    if 'error' in app.storage.general:
        ui.notification(f"Initialization Error: {app.storage.general['error']}", type='negative', position='center')
        return

    with ui.header(elevated=True).classes('items-center justify-between'):
        ui.label('MV Face Recognition').classes('text-2xl font-bold')
        with ui.tabs() as tabs:
            ui.tab('Dashboard', icon='dashboard')
            ui.tab('Video Processing', icon='movie')
            ui.tab('Database Manager', icon='people')
            ui.tab('Settings', icon='settings')

    with ui.footer(elevated=True):
        ui.label('© 2024 MV Face Recognition Team')

    with ui.tab_panels(tabs, value='Dashboard').classes('w-full'):
        with ui.tab_panel('Dashboard'):
            dashboard.create()
        with ui.tab_panel('Video Processing'):
            video_processing.create()
        with ui.tab_panel('Database Manager'):
            database_manager.create()
        with ui.tab_panel('Settings'):
            settings.create()


# --- Main Entry ---

def main():
    """Run the NiceGUI application."""
    ui.run(
        title="MV Face Recognition",
        port=8080,
        storage_secret="a_very_secret_key_for_storage",
        favicon="🎬"
    )

if __name__ in {"__main__", "__mp_main__"}:
    main()
