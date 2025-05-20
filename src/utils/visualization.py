"""
Visualization utilities using Rich for formatted terminal output.

This module provides functions for displaying progress, results,
and statistics with rich formatting.
"""

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import cv2
import numpy as np
import pandas as pd

try:
    from rich import box
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
    )
    from rich.table import Table
    from rich.text import Text
    from rich.tree import Tree

    HAS_RICH = True
except ImportError:
    # Fallback to plain output if Rich is not available
    HAS_RICH = False


# Create console for output
if HAS_RICH:
    console = Console()
else:
    # Dummy console for fallback
    class DummyConsole:
        def print(self, *args, **kwargs):
            print(*args)

        def rule(self, title="", **kwargs):
            print(f"\n{'=' * 40}\n{title}\n{'=' * 40}")

    console = DummyConsole()


def create_progress_bar() -> Any:
    """
    Create a rich progress bar for tracking operations.

    Returns:
        Progress bar instance or None if rich is not available
    """
    if not HAS_RICH:
        return None

    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    )


def display_banner(title: str, subtitle: Optional[str] = None):
    """
    Display a banner with the application title.

    Args:
        title: Main title text
        subtitle: Optional subtitle text
    """
    if HAS_RICH:
        # Create a styled panel
        text = f"[bold cyan]{title}[/bold cyan]"
        if subtitle:
            text += f"\n[italic]{subtitle}[/italic]"

        panel = Panel(
            text,
            border_style="blue",
            padding=(1, 2),
            title="Face Recognition System",
            title_align="center",
        )
        console.print(panel)
    else:
        # Fallback to plain text
        print(f"\n{'-' * 60}")
        print(f"{title:^60}")
        if subtitle:
            print(f"{subtitle:^60}")
        print(f"{'-' * 60}\n")


def display_table(data: Union[List[Dict[str, Any]], pd.DataFrame], title: str):
    """
    Display data as a formatted table.

    Args:
        data: Data to display (list of dicts or DataFrame)
        title: Table title
    """
    if not data:
        console.print("[italic]No data to display[/italic]")
        return

    # Convert to DataFrame if needed
    if not isinstance(data, pd.DataFrame):
        df = pd.DataFrame(data)
    else:
        df = data

    if HAS_RICH:
        # Create a rich table
        table = Table(title=title, box=box.ROUNDED)

        # Add columns
        for column in df.columns:
            table.add_column(str(column), style="cyan")

        # Add rows
        for _, row in df.iterrows():
            table.add_row(*[str(x) for x in row.values])

        console.print(table)
    else:
        # Fallback to pandas display
        print(f"\n{title}")
        print(df)


def display_results(
    results: List[Dict[str, Any]],
    video_name: Optional[str] = None,
    show_summary: bool = True,
):
    """
    Display face recognition results in a formatted table.

    Args:
        results: Recognition results
        video_name: Optional video name for filtering
        show_summary: Whether to show summary statistics
    """
    if not results:
        console.print("[italic yellow]No recognition results to display[/italic yellow]")
        return

    # Convert to DataFrame
    df = pd.DataFrame(results)

    # Filter by video if specified
    if video_name and "video" in df.columns:
        df = df[df["video"] == video_name]

    if df.empty:
        console.print(f"[italic yellow]No results for video: {video_name}[/italic yellow]")
        return

    if HAS_RICH:
        # Main results table
        console.rule("[bold green]Recognition Results[/bold green]")

        # Create a rich table
        table = Table(box=box.ROUNDED)

        # Add relevant columns
        columns = []
        if "video" in df.columns and len(df["video"].unique()) > 1:
            columns.append("video")
        if "timestamp_str" in df.columns:
            columns.append("timestamp_str")
        elif "timestamp" in df.columns:
            columns.append("timestamp")
        if "frame" in df.columns:
            columns.append("frame")
        if "nickname" in df.columns:
            columns.append("nickname")
        elif "person_id" in df.columns:
            columns.append("person_id")
        if "confidence" in df.columns:
            columns.append("confidence")

        # Limit to 20 rows max for display
        display_df = df
        if len(df) > 20:
            display_df = df.head(20)
            note = f"Showing 20 of {len(df)} results"
        else:
            note = f"Total: {len(df)} results"

        # Add columns
        for column in columns:
            table.add_column(str(column), style="cyan")

        # Add rows
        for _, row in display_df.iterrows():
            values = []
            for col in columns:
                if col == "confidence" and col in row:
                    # Format confidence as percentage
                    values.append(
                        f"{row[col]:.2%}" if isinstance(row[col], float) else str(row[col])
                    )
                elif col in row:
                    values.append(str(row[col]))
                else:
                    values.append("")

            table.add_row(*values)

        console.print(table)
        console.print(f"[italic]{note}[/italic]")

        # Show summary if requested
        if show_summary and ("nickname" in df.columns or "person_id" in df.columns):
            console.rule("[bold green]Recognition Summary[/bold green]")

            # Get person column
            person_col = "nickname" if "nickname" in df.columns else "person_id"

            # Group by video and person
            if "video" in df.columns and len(df["video"].unique()) > 1:
                summary = df.groupby(["video", person_col]).size().unstack(fill_value=0)
            else:
                summary = df.groupby([person_col]).size()

            # Create summary table
            summary_table = Table(title="Appearances by Person", box=box.ROUNDED)

            if isinstance(summary, pd.DataFrame):
                # Multi-column summary (by video)
                summary_table.add_column("Person", style="cyan")

                # Add video columns
                for video in summary.columns:
                    summary_table.add_column(str(video), style="green")

                # Add rows
                for person, row in summary.iterrows():
                    values = [str(person)] + [str(count) for count in row.values]
                    summary_table.add_row(*values)
            else:
                # Single column summary
                summary_table.add_column("Person", style="cyan")
                summary_table.add_column("Appearances", style="green")

                for person, count in summary.items():
                    summary_table.add_row(str(person), str(count))

            console.print(summary_table)
    else:
        # Fallback to plain table
        print("\nRecognition Results:")
        print(df.head(20))

        if show_summary:
            print("\nRecognition Summary:")
            person_col = "nickname" if "nickname" in df.columns else "person_id"

            if "video" in df.columns and len(df["video"].unique()) > 1:
                summary = df.groupby(["video", person_col]).size().unstack(fill_value=0)
            else:
                summary = df.groupby([person_col]).size()

            print(summary)


def display_stats(stats: Dict[str, Any]):
    """
    Display system performance statistics.

    Args:
        stats: Statistics dictionary
    """
    if not stats:
        return

    if HAS_RICH:
        console.rule("[bold blue]Performance Statistics[/bold blue]")

        # Create table for stats
        table = Table(box=box.ROUNDED)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        # Add important stats first
        important_stats = [
            ("frames_processed", "Frames Processed"),
            ("faces_detected", "Faces Detected"),
            ("faces_recognized", "Faces Recognized"),
            ("processing_time", "Total Processing Time (s)"),
            ("avg_fps", "Average FPS"),
        ]

        for key, label in important_stats:
            if key in stats:
                value = stats[key]

                # Format specific stats
                if key == "processing_time" and isinstance(value, (int, float)):
                    formatted_value = f"{value:.2f} seconds"
                elif key == "avg_fps" and isinstance(value, (int, float)):
                    formatted_value = f"{value:.2f} frames/sec"
                else:
                    formatted_value = str(value)

                table.add_row(label, formatted_value)

        # Add cache stats if available
        cache_stats = [
            ("memory_hits", "Cache Memory Hits"),
            ("disk_hits", "Cache Disk Hits"),
            ("db_hits", "Cache DB Hits"),
            ("misses", "Cache Misses"),
            ("hit_rate", "Cache Hit Rate"),
        ]

        has_cache_stats = any(key in stats for key, _ in cache_stats)
        if has_cache_stats:
            table.add_section()

            for key, label in cache_stats:
                if key in stats:
                    value = stats[key]

                    # Format specific stats
                    if key == "hit_rate" and isinstance(value, (int, float)):
                        formatted_value = f"{value:.2%}"
                    else:
                        formatted_value = str(value)

                    table.add_row(label, formatted_value)

        console.print(table)
    else:
        # Fallback
        print("\nPerformance Statistics:")
        for key, value in stats.items():
            print(f"{key}: {value}")


def display_selection_menu(options: List[str], prompt: str):
    """
    Display a selection menu for user input.

    Args:
        options: List of options to choose from
        prompt: Prompt text for the selection

    Returns:
        List of selected options
    """
    if HAS_RICH:
        console.print(f"[bold]{prompt}[/bold]")

        # Display options with numbers
        for idx, name in enumerate(options, 1):
            console.print(f"  [cyan]{idx}.[/cyan] {name}")

        console.print(f"  [cyan]{len(options) + 1}.[/cyan] Select all")
    else:
        print(f"\n{prompt}")
        for idx, name in enumerate(options, 1):
            print(f"  {idx}. {name}")
        print(f"  {len(options) + 1}. Select all")

    # Get user input
    indices = input(
        f"\nEnter the numbers of the items you want to select, separated by commas (e.g., 1,3,5), or '{len(options) + 1}' to select all: "
    )

    if indices.strip() == str(len(options) + 1):
        return options

    selected_indices = [int(i.strip()) - 1 for i in indices.split(",") if i.strip().isdigit()]
    selected_items = [options[i] for i in selected_indices if 0 <= i < len(options)]

    return selected_items


def format_timestamp(seconds: float) -> str:
    """
    Format seconds as MM:SS timestamp.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted timestamp string
    """
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


class StatusDisplay:
    """Live status display for face recognition processing."""

    def __init__(self):
        """Initialize the status display."""
        self.start_time = time.time()
        self.stats = {
            "frames_processed": 0,
            "faces_detected": 0,
            "faces_recognized": 0,
            "current_video": None,
            "videos_completed": 0,
            "videos_total": 0,
            "recognition_rate": 0.0,
            "elapsed_time": 0.0,
            "estimated_remaining": 0.0,
            "current_frame_rate": 0.0,
        }
        self.live_display = None
        self.last_update = time.time()
        self.update_interval = 0.5  # seconds

    def start(self, videos_total: int = 0):
        """
        Start the live display.

        Args:
            videos_total: Total number of videos to process
        """
        if not HAS_RICH:
            return

        self.stats["videos_total"] = videos_total
        self.stats["elapsed_time"] = 0.0
        self.start_time = time.time()

        # Create layout
        layout = Layout()
        layout.split(
            Layout(name="header", size=1),
            Layout(name="main"),
            Layout(name="footer", size=3),
        )

        layout["main"].split_row(
            Layout(name="stats"),
            Layout(name="progress"),
        )

        # Start live display
        self.live_display = Live(layout, refresh_per_second=4, screen=True)
        self.live_display.start()

        # Initial update
        self._update_display(layout)

    def update(
        self,
        frames_processed: Optional[int] = None,
        faces_detected: Optional[int] = None,
        faces_recognized: Optional[int] = None,
        current_video: Optional[str] = None,
        videos_completed: Optional[int] = None,
    ):
        """
        Update the display with new stats.

        Args:
            frames_processed: Number of frames processed
            faces_detected: Number of faces detected
            faces_recognized: Number of faces recognized
            current_video: Current video being processed
            videos_completed: Number of videos completed
        """
        now = time.time()

        # Update stats
        if frames_processed is not None:
            self.stats["frames_processed"] = frames_processed
        if faces_detected is not None:
            self.stats["faces_detected"] = faces_detected
        if faces_recognized is not None:
            self.stats["faces_recognized"] = faces_recognized
        if current_video is not None:
            self.stats["current_video"] = current_video
        if videos_completed is not None:
            self.stats["videos_completed"] = videos_completed

        # Calculate derived stats
        self.stats["elapsed_time"] = now - self.start_time

        # Calculate recognition rate
        if self.stats["faces_detected"] > 0:
            self.stats["recognition_rate"] = (
                self.stats["faces_recognized"] / self.stats["faces_detected"]
            )

        # Calculate estimated remaining time
        if self.stats["videos_completed"] > 0 and self.stats["videos_total"] > 0:
            time_per_video = self.stats["elapsed_time"] / self.stats["videos_completed"]
            remaining_videos = self.stats["videos_total"] - self.stats["videos_completed"]
            self.stats["estimated_remaining"] = time_per_video * remaining_videos

        # Calculate current FPS
        if now - self.last_update >= self.update_interval:
            frames_delta = self.stats["frames_processed"] - getattr(self, "_last_frames", 0)
            time_delta = now - self.last_update

            if time_delta > 0:
                self.stats["current_frame_rate"] = frames_delta / time_delta

            self._last_frames = self.stats["frames_processed"]
            self.last_update = now

        # Update display
        if HAS_RICH and self.live_display:
            if now - getattr(self, "_last_display_update", 0) >= 0.25:  # Limit update rate
                try:
                    # Create a new layout for each update to avoid issues with the 'Live' object
                    layout = Layout()
                    layout.split(
                        Layout(name="header", size=1),
                        Layout(name="main"),
                        Layout(name="footer", size=3),
                    )

                    layout["main"].split_row(
                        Layout(name="stats"),
                        Layout(name="progress"),
                    )

                    # Update content in the layout
                    self._update_display(layout)

                    # Update the live display with the new layout
                    self.live_display.update(layout)
                except Exception as e:
                    # Fallback to simpler display if rich update fails
                    print(f"Display update error (using fallback): {str(e)}")
                    self._print_status()

                self._last_display_update = now
        else:
            # Fallback to periodic print
            if now - getattr(self, "_last_print", 0) >= 5.0:  # Print every 5 seconds
                self._print_status()
                self._last_print = now

    def stop(self):
        """Stop the live display."""
        if HAS_RICH and self.live_display:
            self.live_display.stop()
            self.live_display = None

    def _update_display(self, layout):
        """Update the rich display layout."""
        if not HAS_RICH:
            return

        # Header with title
        layout["header"].update(
            Text("Face Recognition System", style="bold cyan", justify="center")
        )

        # Main statistics panel
        stats_content = [
            Text("📊 Processing Statistics:", style="bold yellow"),
            Text(f"Frames Processed: {self.stats['frames_processed']}"),
            Text(f"Faces Detected: {self.stats['faces_detected']}"),
            Text(f"Faces Recognized: {self.stats['faces_recognized']}"),
            Text(f"Recognition Rate: {self.stats['recognition_rate']:.1%}"),
            Text(f"Current FPS: {self.stats['current_frame_rate']:.1f}"),
            Text(f"Elapsed Time: {self._format_time(self.stats['elapsed_time'])}"),
        ]

        if self.stats["videos_total"] > 0:
            stats_content.append(
                Text(f"Videos: {self.stats['videos_completed']}/{self.stats['videos_total']}")
            )
            if self.stats["estimated_remaining"] > 0:
                stats_content.append(
                    Text(f"Est. Remaining: {self._format_time(self.stats['estimated_remaining'])}")
                )

        stats_panel = Panel(
            "\n".join(str(line) for line in stats_content),
            title="Statistics",
            border_style="blue",
            padding=(1, 2),
        )
        layout["stats"].update(stats_panel)

        # Progress panel
        progress_content = []

        if self.stats["current_video"]:
            progress_content.append(
                Text(f"Processing: {self.stats['current_video']}", style="bold cyan")
            )

        # Add a simple progress bar
        if self.stats["videos_total"] > 0 and self.stats["videos_completed"] > 0:
            width = 40
            completed = min(self.stats["videos_completed"], self.stats["videos_total"])
            filled = int(width * (completed / self.stats["videos_total"]))
            bar = (
                f"[{'=' * filled}{' ' * (width - filled)}] {completed}/{self.stats['videos_total']}"
            )
            progress_content.append(Text(bar))

        # Add face recognition events
        faces_panel = Panel(
            "\n".join(str(line) for line in progress_content),
            title="Progress",
            border_style="green",
            padding=(1, 2),
        )
        layout["progress"].update(faces_panel)

        # Footer with instructions
        footer_text = "Press Ctrl+C to stop processing"
        layout["footer"].update(Text(footer_text, justify="center", style="italic"))

    def _print_status(self):
        """Print status to console (fallback for when Rich is not available)."""
        print(
            f"\rProcessed: {self.stats['frames_processed']} frames | "
            f"Detected: {self.stats['faces_detected']} faces | "
            f"Recognized: {self.stats['faces_recognized']} | "
            f"FPS: {self.stats['current_frame_rate']:.1f}",
            end="",
        )

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format seconds as HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"


# Helper function for saving annotated images
def save_annotated_frame(
    frame: np.ndarray,
    output_dir: Union[str, Path],
    filename: str,
    faces: Optional[List[Dict[str, Any]]] = None,
):
    """
    Save an annotated frame with face boxes and labels.

    Args:
        frame: Frame to annotate
        output_dir: Output directory
        filename: Output filename
        faces: Face detection results (optional)
    """
    if isinstance(output_dir, str):
        output_dir = Path(output_dir)

    # Create directory if needed
    os.makedirs(output_dir, exist_ok=True)

    # Create a copy for annotations
    annotated = frame.copy()

    # Draw face boxes and labels
    if faces:
        for face in faces:
            if "bbox" not in face:
                continue

            # Get bounding box
            bbox = face["bbox"]
            if len(bbox) >= 4:
                x1, y1, x2, y2 = map(int, bbox[:4])

                # Draw rectangle
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)

                # Prepare label text
                label_parts = []

                # Add person ID/name if available
                if "person_id" in face:
                    label_parts.append(str(face["person_id"]))
                elif "name" in face:
                    label_parts.append(str(face["name"]))

                # Add confidence if available
                if "confidence" in face and isinstance(face["confidence"], (int, float)):
                    label_parts.append(f"{face['confidence']:.2f}")

                if label_parts:
                    label = " ".join(label_parts)

                    # Draw label background
                    label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)

                    cv2.rectangle(
                        annotated,
                        (x1, y1 - label_size[1] - 10),
                        (x1 + label_size[0], y1),
                        (0, 255, 0),
                        cv2.FILLED,
                    )

                    # Draw text
                    cv2.putText(
                        annotated,
                        label,
                        (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (255, 255, 255),
                        1,
                    )

    # Save annotated frame
    output_path = output_dir / filename
    cv2.imwrite(str(output_path), annotated)

    return str(output_path)
