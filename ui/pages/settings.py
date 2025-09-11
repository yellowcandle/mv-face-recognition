"""
Settings page for the NiceGUI application.
"""

from nicegui import ui
import json

def create():
    """Create the settings page content."""
    
    def load_config():
        with open("config.json", "r") as f:
            return json.load(f)

    def save_config(config):
        with open("config.json", "w") as f:
            json.dump(config, f, indent=4)
        ui.notify("Configuration saved!", type='positive')
        # Here you might want to re-initialize backend components
        # For simplicity, we'll just notify the user.

    config = load_config()

    with ui.card().classes('w-full'):
        ui.label('Face Detection Settings').classes('text-lg font-bold')
        with ui.row().classes('w-full'):
            detection_threshold = ui.slider(
                min=0.1, max=0.9, step=0.05, value=config["face_detection"]["detection_threshold"]
            ).props('label="Detection Threshold"')
            
            input_size = ui.select(
                options=["320x320", "640x640", "800x800"],
                value=f'{config["face_detection"]["input_size"][0]}x{config["face_detection"]["input_size"][1]}'
            ).props('label="Input Size"')

    with ui.card().classes('w-full mt-4'):
        ui.label('Face Matching Settings').classes('text-lg font-bold')
        with ui.row().classes('w-full'):
            similarity_threshold = ui.slider(
                min=0.1, max=0.9, step=0.05, value=config["face_matching"]["similarity_threshold"]
            ).props('label="Similarity Threshold"')
            
            max_results = ui.number(
                label="Max Results", value=config["face_matching"]["max_results"], min=1, max=20
            )

    with ui.card().classes('w-full mt-4'):
        ui.label('Video Processing Settings').classes('text-lg font-bold')
        with ui.row().classes('w-full'):
            frame_skip = ui.slider(
                min=1, max=30, value=config["video_processing"]["frame_skip"]
            ).props('label="Frame Skip"')
            
            output_fps = ui.number(
                label="Output FPS", value=config["video_processing"]["output_fps"], min=10, max=60
            )

    def save_and_update():
        size_map = {"320x320": [320, 320], "640x640": [640, 640], "800x800": [800, 800]}
        
        config["face_detection"]["detection_threshold"] = detection_threshold.value
        config["face_detection"]["input_size"] = size_map[input_size.value]
        config["face_matching"]["similarity_threshold"] = similarity_threshold.value
        config["face_matching"]["max_results"] = max_results.value
        config["video_processing"]["frame_skip"] = frame_skip.value
        config["video_processing"]["output_fps"] = output_fps.value
        
        save_config(config)

    ui.button('Save Configuration', on_click=save_and_update, icon='save').props('color=primary')
