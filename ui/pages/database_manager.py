"""
Database manager page for the NiceGUI application.
"""

from nicegui import ui, app
from src.database.chroma_setup import ChromaDBManager
from pathlib import Path

def create():
    """Create the database manager page content."""
    db_manager: ChromaDBManager = app.storage.general.get('db_manager')

    def refresh_gallery():
        gallery.clear()
        with gallery:
            create_gallery()

    def create_gallery():
        if not db_manager:
            ui.notify("Database manager not initialized.", type='negative')
            return

        contestants_dir = Path("source/photo/contestants")
        
        with ui.row().classes('w-full q-gutter-md'):
            for contestant_folder in sorted(contestants_dir.iterdir()):
                if contestant_folder.is_dir():
                    # Find the first image in the folder
                    image_file = next(contestant_folder.glob('*.jpg'), None)
                    if image_file:
                        with ui.card():
                            ui.image(str(image_file)).classes('w-32 h-32 object-cover')
                            ui.label(contestant_folder.name).classes('text-center font-bold')

    ui.label('Contestant Gallery').classes('text-2xl font-bold mb-4')
    
    with ui.row():
        ui.button('Refresh Gallery', on_click=refresh_gallery, icon='refresh')

    gallery = ui.column()
    with gallery:
        create_gallery()
