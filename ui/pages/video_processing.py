"""
Video processing page implementing DESIGN.md layout specifications.
Two-column layout with real-time video player and face recognition panel.
"""

from nicegui import ui, app
from pathlib import Path
import asyncio
import cv2
import numpy as np
from typing import Dict, List, Optional

def create():
    """Create the video processing page content implementing DESIGN.md layout."""
    video_processor = getattr(app, 'video_processor', None)
    
    # Global state for real-time processing
    processing_state = {
        'is_processing': False,
        'current_video': None,
        'detected_faces': [],
        'similarity_scores': {},
        'frame_count': 0
    }
    
    # Main container with header bar (60px height)
    with ui.row().classes('w-full h-16 bg-gray-800 items-center px-4'):
        ui.label('Face Recognition Dashboard').classes('text-xl font-bold text-white')
        ui.space()
        status_badge = ui.badge('READY', color='green').classes('text-white')
        ui.label('Live Processing Status').classes('text-white text-sm ml-2')
    
    # Main content area - Two column layout (60% video, 40% face panel)
    with ui.row().classes('w-full flex-1'):
        # Left Panel - Video Player (60% width)
        with ui.column().classes('w-3/5 h-full bg-black'):
            # Video selection header
            with ui.row().classes('w-full p-4 bg-gray-900'):
                videos_dir = Path('source/videos')
                video_files = [f.name for f in videos_dir.iterdir() if f.is_file()] if videos_dir.exists() else []
                
                if not video_files:
                    ui.label("No videos found in /source/videos/").classes('text-red-400')
                    video_select = None
                else:
                    video_select = ui.select(
                        options=video_files,
                        label='Select a video',
                        on_change=lambda e: on_video_select(e, processing_state, None)  # video_player will be set later
                    ).classes('w-full bg-gray-800 text-white')
            
            # Video player with detection overlay
            video_container = ui.column().classes('w-full flex-1 relative')
            with video_container:
                video_player = ui.video(src='').classes('w-full h-full object-contain')
                # Overlay canvas for face detection boxes (will be implemented)
                detection_overlay = ui.html('').classes('absolute top-0 left-0 w-full h-full pointer-events-none')
            
            # Update the video selection handler to include video_player
            if video_select:
                video_select.on_change = lambda e: on_video_select(e, processing_state, video_player)
            
            # Video controls
            with ui.row().classes('w-full p-2 bg-gray-900 text-white text-sm'):
                frame_rate_label = ui.label('FPS: 0.0').classes('text-green-400')
                ui.space()
                resolution_label = ui.label('Resolution: N/A').classes('text-blue-400')
        
        # Right Panel - Face Recognition Panel (40% width)
        with ui.column().classes('w-2/5 h-full bg-slate-800'):
            # Face panel header
            with ui.row().classes('w-full p-4 bg-slate-700'):
                ui.label('Detected Faces').classes('text-xl font-bold text-white')
                ui.space()
                face_count_badge = ui.badge('0', color='blue').classes('text-white')
            
            # Face tiles grid (3 columns, auto rows, 10px gap)
            face_grid = ui.column().classes('w-full p-4 gap-2 overflow-y-auto flex-1')
            with face_grid:
                ui.label('No faces detected yet...').classes('text-gray-400 text-center p-8')
            
            # Processing controls
            with ui.column().classes('w-full p-4 bg-slate-700'):
                ui.label('Processing Controls').classes('text-lg font-bold text-white mb-2')
                
                with ui.row().classes('w-full gap-2'):
                    start_time = ui.number(label='Start (s)', value=0, min=0).classes('flex-1')
                    end_time = ui.number(label='End (s)', value=60, min=0).classes('flex-1')
                
                similarity_threshold = ui.slider(
                    min=0.1, max=0.9, value=0.4, step=0.05
                ).props('label-always').classes('w-full text-white')
                ui.label('Similarity Threshold: 0.4').classes('text-sm text-gray-300')
                
                process_button = ui.button(
                    'Start Real-time Processing', 
                    icon='play_arrow',
                    on_click=lambda: start_realtime_processing(
                        processing_state, video_select, start_time, end_time, 
                        similarity_threshold, status_badge, face_grid, face_count_badge
                    )
                ).props('color=primary').classes('w-full mt-2')
    
    # Bottom Panel - Similarity Scores (200px height)
    with ui.row().classes('w-full h-48 bg-gray-700 p-4'):
        ui.label('Recognition Confidence Scores').classes('text-xl font-bold text-white mb-2')
        
        # Confidence chart container
        chart_container = ui.column().classes('w-full flex-1')
        with chart_container:
            ui.label('No recognition data yet...').classes('text-gray-400 text-center p-8')
    
    # Serve the videos directory statically
    app.add_static_files('/static', 'source/videos')

def on_video_select(e, processing_state, video_player=None):
    """Handle video selection with enhanced feedback."""
    if e.value:
        video_path = f'/static/{e.value}'
        processing_state['current_video'] = e.value
        if video_player:
            video_player.set_source(video_path)
        ui.notify(f"Loaded {e.value}", type='positive')
    else:
        processing_state['current_video'] = None
        if video_player:
            video_player.set_source('')

def create_face_tile(face_data: Dict, confidence_level: str) -> ui.card:
    """Create a face tile with color-coded confidence border."""
    # Color coding based on confidence
    if confidence_level == 'high':  # >90%
        border_color = 'border-green-500'
        bg_color = 'bg-green-900'
    elif confidence_level == 'medium':  # 70-90%
        border_color = 'border-yellow-500'
        bg_color = 'bg-yellow-900'
    else:  # <70%
        border_color = 'border-red-500'
        bg_color = 'bg-red-900'
    
    with ui.card().classes(f'w-28 h-28 {border_color} border-2 {bg_color} cursor-pointer'):
        # Face image (100x100px)
        if 'image_data' in face_data:
            ui.image().classes('w-24 h-20 object-cover')
        else:
            ui.label('👤').classes('text-4xl text-center w-full h-20 flex items-center justify-center')
        
        # Name/ID label
        name = face_data.get('name', 'Unknown')
        ui.label(name).classes('text-xs text-white text-center truncate')
        
        # Confidence percentage
        confidence = face_data.get('confidence', 0.0)
        ui.label(f'{confidence:.1%}').classes('text-xs text-gray-300 text-center')
        
        # Timestamp
        timestamp = face_data.get('timestamp', '00:00')
        ui.label(timestamp).classes('text-xs text-gray-400 text-center')

async def start_realtime_processing(
    processing_state, video_select, start_time, end_time, 
    similarity_threshold, status_badge, face_grid, face_count_badge
):
    """Start real-time face recognition processing."""
    if not processing_state['current_video']:
        ui.notify('Please select a video first', type='negative')
        return
    
    if processing_state['is_processing']:
        ui.notify('Processing already in progress', type='warning')
        return
    
    try:
        processing_state['is_processing'] = True
        status_badge.set_text('PROCESSING')
        status_badge.props('color=orange')
        
        # Clear previous results
        face_grid.clear()
        processing_state['detected_faces'] = []
        face_count_badge.set_text('0')
        
        with face_grid:
            ui.label('Processing...').classes('text-yellow-400 text-center p-4')
        
        # Start processing (placeholder - will integrate with actual processor)
        await simulate_processing(processing_state, face_grid, face_count_badge)
        
        status_badge.set_text('COMPLETED')
        status_badge.props('color=green')
        ui.notify('Processing completed!', type='positive')
        
    except Exception as e:
        status_badge.set_text('ERROR')
        status_badge.props('color=red')
        ui.notify(f'Processing error: {str(e)}', type='negative')
    finally:
        processing_state['is_processing'] = False

async def simulate_processing(processing_state, face_grid, face_count_badge):
    """Simulate face detection processing (placeholder)."""
    # This is a placeholder - will be replaced with actual video processing
    face_grid.clear()
    
    # Simulate detecting faces over time
    for i in range(5):
        await asyncio.sleep(1)  # Simulate processing time
        
        # Add a simulated face detection
        face_data = {
            'name': f'Contestant {i+1}',
            'confidence': 0.7 + (i * 0.05),
            'timestamp': f'00:{i+1:02d}'
        }
        
        processing_state['detected_faces'].append(face_data)
        
        # Update face grid
        with face_grid:
            if i == 0:  # Clear "Processing..." message on first detection
                face_grid.clear()
            
            confidence = face_data['confidence']
            if confidence > 0.9:
                confidence_level = 'high'
            elif confidence > 0.7:
                confidence_level = 'medium'
            else:
                confidence_level = 'low'
            
            create_face_tile(face_data, confidence_level)
        
        # Update count
        face_count_badge.set_text(str(len(processing_state['detected_faces'])))