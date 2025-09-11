"""
Video processing page for the NiceGUI application.
"""

from nicegui import ui, app
from pathlib import Path


def create():
    """Create the video processing page content."""
    video_processor = app.storage.general.get("video_processor")

    def on_video_select(e):
        """Handle video selection."""
        if e.value:
            video_player.set_source(f"/static/{e.value}")
            ui.notify(f"Loaded {e.value}", type="positive")
        else:
            video_player.set_source(None)

    with ui.splitter(value=70).classes("w-full h-full") as splitter:
        with splitter.before:
            with ui.column().classes("w-full"):
                with ui.row().classes("w-full items-center"):
                    videos_dir = Path("source/videos")
                    video_files = [f.name for f in videos_dir.iterdir() if f.is_file()]

                    if not video_files:
                        ui.label("No videos found in /source/videos/").classes(
                            "text-negative"
                        )
                    else:
                        ui.select(
                            options=video_files,
                            label="Select a video",
                            on_change=on_video_select,
                        ).classes("w-full")

                video_player = ui.video().classes("w-full")

        with splitter.after:
            with ui.column().classes("p-4 w-full"):
                ui.label("Processing Controls").classes("text-lg font-bold")

                start_time = ui.number(label="Start time (s)", value=0, min=0)
                end_time = ui.number(label="End time (s)", value=60, min=0)

                async def start_processing_click():
                    await start_processing(
                        video_player.source.replace("/static/", ""),
                        start_time.value,
                        end_time.value,
                    )

                ui.button(
                    "Start Processing",
                    on_click=start_processing_click,
                    icon="play_arrow",
                ).props("color=primary")

                results_area = ui.column().classes("w-full mt-4")

    async def start_processing(video_name, start, end):
        if not video_name:
            ui.notify("No video selected.", type="negative")
            return

        ui.notify(
            f"Starting processing for {video_name} from {start}s to {end}s", type="info"
        )

        # Reset UI elements
        results_area.clear()

        try:
            processor = video_processor.process_video_realtime(video_name, start, end)

            with results_area:
                ui.label("Live Results").classes("text-lg font-bold")
                progress = ui.linear_progress(value=0).classes("w-full")

            for frame_num, annotated_frame, face_results, frame_stats in processor:
                # This is a simplified version. A real implementation would
                # handle the annotated_frame (e.g., display it) and update
                # more detailed stats.
                progress.set_value(
                    frame_stats["total_frames_processed"]
                    / frame_stats["estimated_total_frames"]
                )

                if face_results:
                    with results_area:
                        for result in face_results:
                            if result["matched"]:
                                ui.chip(
                                    f"{result['contestant_name']} ({result['recognition_confidence']:.2f})",
                                    icon="face",
                                ).props("color=positive")

                await ui.run_javascript(
                    'window.dispatchEvent(new Event("resize"))', respond=False
                )  # Force redraw

            ui.notify("Processing finished!", type="positive")

        except Exception as e:
            ui.notify(f"An error occurred: {e}", type="negative")

    # Serve the videos directory statically
    app.add_static_files("/static", "source/videos")
