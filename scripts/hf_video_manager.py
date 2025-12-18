#!/usr/bin/env python3
"""
Huggingface Video Manager - Upload and manage videos with xet storage

This script manages video files in a Huggingface repository using xet storage
for efficient chunk-level deduplication.

Features:
- Upload local videos to HF with xet deduplication
- Download videos from HF
- List and manage repository contents
- Support for batch operations

Prerequisites:
- huggingface_hub >= 0.32.0 (with hf_xet support)
- HF_TOKEN environment variable or `huggingface-cli login`

Usage:
    # Upload all videos from source/videos
    python scripts/hf_video_manager.py upload

    # Upload specific video
    python scripts/hf_video_manager.py upload --file source/videos/video1.mp4

    # List videos in repository
    python scripts/hf_video_manager.py list

    # Download all videos
    python scripts/hf_video_manager.py download

    # Download specific video
    python scripts/hf_video_manager.py download --file video1.mp4
"""

import os
import sys
import click
from pathlib import Path
from typing import List, Optional

try:
    from huggingface_hub import HfApi, hf_hub_download, upload_file, upload_folder
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.panel import Panel
except ImportError:
    print("Missing dependencies. Install with:")
    print("  pip install huggingface_hub>=0.32.0 hf_xet rich")
    sys.exit(1)

# Configuration
DEFAULT_REPO_ID = "yellowcandle/mv-face-recognition-videos"
DEFAULT_LOCAL_DIR = "source/videos"
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm", ".m4v"}

console = Console()


def ensure_repo_exists(api: HfApi, repo_id: str) -> bool:
    """
    Ensure the HF repository exists, create if it doesn't.

    Args:
        api: HfApi instance
        repo_id: Repository ID

    Returns:
        True if repository exists or was created
    """
    try:
        api.repo_info(repo_id=repo_id, repo_type="dataset")
        console.print(f"[green]✅ Repository exists: {repo_id}[/green]")
        return True
    except Exception:
        console.print(f"[yellow]📦 Creating repository: {repo_id}[/yellow]")
        try:
            api.create_repo(
                repo_id=repo_id,
                repo_type="dataset",
                private=False,
                exist_ok=True,
            )
            console.print(f"[green]✅ Repository created: {repo_id}[/green]")
            return True
        except Exception as e:
            console.print(f"[red]❌ Failed to create repository: {e}[/red]")
            return False


def get_local_videos(local_dir: str) -> List[Path]:
    """
    Get list of video files in local directory.

    Args:
        local_dir: Local directory path

    Returns:
        List of video file paths
    """
    dir_path = Path(local_dir)
    if not dir_path.exists():
        return []

    videos = []
    for file_path in dir_path.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in VIDEO_EXTENSIONS:
            videos.append(file_path)

    return sorted(videos)


def get_repo_videos(api: HfApi, repo_id: str) -> List[str]:
    """
    Get list of video files in HF repository.

    Args:
        api: HfApi instance
        repo_id: Repository ID

    Returns:
        List of video filenames in repository
    """
    try:
        files = api.list_repo_files(repo_id=repo_id, repo_type="dataset")
        videos = [
            f for f in files
            if Path(f).suffix.lower() in VIDEO_EXTENSIONS
            and not f.startswith(".")
        ]
        return sorted(videos)
    except Exception as e:
        console.print(f"[red]❌ Error listing repository: {e}[/red]")
        return []


@click.group()
def cli():
    """Huggingface Video Manager - Manage videos with xet storage"""
    pass


@cli.command()
@click.option("--repo-id", default=DEFAULT_REPO_ID, help="Huggingface repository ID")
@click.option("--local-dir", default=DEFAULT_LOCAL_DIR, help="Local videos directory")
@click.option("--file", "file_path", help="Upload specific file only")
@click.option("--dry-run", is_flag=True, help="Show what would be uploaded without uploading")
def upload(repo_id: str, local_dir: str, file_path: Optional[str], dry_run: bool):
    """Upload videos to Huggingface repository"""
    console.print(Panel(
        f"📤 Upload Videos to Huggingface\n"
        f"📦 Repository: {repo_id}\n"
        f"📁 Local directory: {local_dir}",
        title="[bold blue]Upload Configuration[/bold blue]",
        border_style="blue"
    ))

    # Enable high performance xet mode
    os.environ["HF_XET_HIGH_PERFORMANCE"] = "1"

    api = HfApi()

    # Ensure repository exists
    if not ensure_repo_exists(api, repo_id):
        sys.exit(1)

    # Get videos to upload
    if file_path:
        video_path = Path(file_path)
        if not video_path.exists():
            console.print(f"[red]❌ File not found: {file_path}[/red]")
            sys.exit(1)
        videos = [video_path]
    else:
        videos = get_local_videos(local_dir)
        if not videos:
            console.print(f"[yellow]⚠️ No videos found in {local_dir}[/yellow]")
            return

    # Get existing videos in repo
    existing_videos = set(get_repo_videos(api, repo_id))

    # Show upload plan
    table = Table(title="Videos to Upload")
    table.add_column("File", style="cyan")
    table.add_column("Size", style="green", justify="right")
    table.add_column("Status", style="yellow")

    total_size = 0
    to_upload = []

    for video in videos:
        size = video.stat().st_size
        size_mb = size / (1024 * 1024)
        total_size += size

        if video.name in existing_videos:
            status = "Already exists"
            style = "dim"
        else:
            status = "Will upload"
            style = "bold"
            to_upload.append(video)

        table.add_row(
            f"[{style}]{video.name}[/{style}]",
            f"{size_mb:.1f} MB",
            status
        )

    console.print(table)
    console.print(f"\n📊 Total: {len(videos)} videos, {total_size/(1024*1024*1024):.2f} GB")
    console.print(f"📤 To upload: {len(to_upload)} new videos")

    if dry_run:
        console.print("[yellow]🔍 Dry run - no files uploaded[/yellow]")
        return

    if not to_upload:
        console.print("[green]✅ All videos already in repository[/green]")
        return

    # Upload videos
    console.print("\n[bold blue]📤 Starting upload...[/bold blue]")
    console.print("[dim]Using xet storage for efficient chunk-level deduplication[/dim]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Uploading...", total=len(to_upload))

        for video in to_upload:
            progress.update(task, description=f"Uploading {video.name}...")

            try:
                upload_file(
                    path_or_fileobj=str(video),
                    path_in_repo=video.name,
                    repo_id=repo_id,
                    repo_type="dataset",
                )
                console.print(f"[green]✅ Uploaded: {video.name}[/green]")
            except Exception as e:
                console.print(f"[red]❌ Failed: {video.name} - {e}[/red]")

            progress.advance(task)

    console.print(Panel(
        f"✅ Upload complete!\n"
        f"📤 Uploaded: {len(to_upload)} videos\n"
        f"📦 Repository: https://huggingface.co/datasets/{repo_id}",
        title="[bold green]Success[/bold green]",
        border_style="green"
    ))


@cli.command()
@click.option("--repo-id", default=DEFAULT_REPO_ID, help="Huggingface repository ID")
@click.option("--local-dir", default=DEFAULT_LOCAL_DIR, help="Local download directory")
@click.option("--file", "file_name", help="Download specific file only")
@click.option("--force", is_flag=True, help="Force re-download existing files")
def download(repo_id: str, local_dir: str, file_name: Optional[str], force: bool):
    """Download videos from Huggingface repository"""
    console.print(Panel(
        f"📥 Download Videos from Huggingface\n"
        f"📦 Repository: {repo_id}\n"
        f"📁 Local directory: {local_dir}",
        title="[bold blue]Download Configuration[/bold blue]",
        border_style="blue"
    ))

    # Enable high performance xet mode
    os.environ["HF_XET_HIGH_PERFORMANCE"] = "1"

    api = HfApi()

    # Get videos in repository
    if file_name:
        videos = [file_name]
    else:
        videos = get_repo_videos(api, repo_id)
        if not videos:
            console.print(f"[yellow]⚠️ No videos found in repository[/yellow]")
            return

    # Check existing local files
    local_dir_path = Path(local_dir)
    local_dir_path.mkdir(parents=True, exist_ok=True)

    existing_local = set(f.name for f in local_dir_path.iterdir() if f.is_file())

    # Show download plan
    table = Table(title="Videos to Download")
    table.add_column("File", style="cyan")
    table.add_column("Status", style="yellow")

    to_download = []

    for video in videos:
        if video in existing_local and not force:
            status = "Already exists"
            style = "dim"
        else:
            status = "Will download"
            style = "bold"
            to_download.append(video)

        table.add_row(f"[{style}]{video}[/{style}]", status)

    console.print(table)
    console.print(f"\n📊 Total: {len(videos)} videos in repository")
    console.print(f"📥 To download: {len(to_download)} videos")

    if not to_download:
        console.print("[green]✅ All videos already downloaded[/green]")
        return

    # Download videos
    console.print("\n[bold blue]📥 Starting download...[/bold blue]")
    console.print("[dim]Using xet storage for efficient streaming[/dim]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Downloading...", total=len(to_download))

        for video in to_download:
            progress.update(task, description=f"Downloading {video}...")

            try:
                hf_hub_download(
                    repo_id=repo_id,
                    filename=video,
                    repo_type="dataset",
                    local_dir=str(local_dir_path),
                    local_dir_use_symlinks=False,
                )
                console.print(f"[green]✅ Downloaded: {video}[/green]")
            except Exception as e:
                console.print(f"[red]❌ Failed: {video} - {e}[/red]")

            progress.advance(task)

    console.print(Panel(
        f"✅ Download complete!\n"
        f"📥 Downloaded: {len(to_download)} videos\n"
        f"📁 Location: {local_dir_path.absolute()}",
        title="[bold green]Success[/bold green]",
        border_style="green"
    ))


@cli.command("list")
@click.option("--repo-id", default=DEFAULT_REPO_ID, help="Huggingface repository ID")
@click.option("--local-dir", default=DEFAULT_LOCAL_DIR, help="Local videos directory")
def list_videos(repo_id: str, local_dir: str):
    """List videos in repository and local directory"""
    api = HfApi()

    # Get repo videos
    repo_videos = get_repo_videos(api, repo_id)

    # Get local videos
    local_videos = get_local_videos(local_dir)
    local_video_names = set(v.name for v in local_videos)

    console.print(Panel(
        f"📦 Repository: {repo_id}\n"
        f"📁 Local directory: {local_dir}",
        title="[bold blue]Video Inventory[/bold blue]",
        border_style="blue"
    ))

    # Create comparison table
    table = Table(title="Video Files")
    table.add_column("Video Name", style="cyan")
    table.add_column("Repository", style="green", justify="center")
    table.add_column("Local", style="yellow", justify="center")

    all_videos = sorted(set(repo_videos) | local_video_names)

    for video in all_videos:
        in_repo = "✅" if video in repo_videos else "❌"
        in_local = "✅" if video in local_video_names else "❌"
        table.add_row(video, in_repo, in_local)

    console.print(table)

    console.print(f"\n📊 Summary:")
    console.print(f"   📦 In repository: {len(repo_videos)} videos")
    console.print(f"   📁 Local: {len(local_videos)} videos")

    # Check sync status
    only_repo = set(repo_videos) - local_video_names
    only_local = local_video_names - set(repo_videos)

    if only_repo:
        console.print(f"   📥 Need to download: {len(only_repo)} videos")
    if only_local:
        console.print(f"   📤 Need to upload: {len(only_local)} videos")
    if not only_repo and not only_local:
        console.print("   ✅ Local and repository are in sync!")


@cli.command()
@click.option("--repo-id", default=DEFAULT_REPO_ID, help="Huggingface repository ID")
def info(repo_id: str):
    """Show repository information"""
    api = HfApi()

    try:
        repo_info = api.repo_info(repo_id=repo_id, repo_type="dataset")

        console.print(Panel(
            f"📦 Repository: {repo_id}\n"
            f"📝 ID: {repo_info.id}\n"
            f"👤 Author: {repo_info.author}\n"
            f"🔒 Private: {repo_info.private}\n"
            f"📅 Last modified: {repo_info.lastModified}\n"
            f"🔗 URL: https://huggingface.co/datasets/{repo_id}",
            title="[bold blue]Repository Info[/bold blue]",
            border_style="blue"
        ))

        # Get video count
        videos = get_repo_videos(api, repo_id)
        console.print(f"\n📹 Videos in repository: {len(videos)}")

    except Exception as e:
        console.print(f"[red]❌ Error getting repository info: {e}[/red]")
        console.print("[dim]Repository may not exist or you may not have access.[/dim]")


@cli.command()
@click.option("--repo-id", default=DEFAULT_REPO_ID, help="Huggingface repository ID")
@click.option("--local-dir", default=DEFAULT_LOCAL_DIR, help="Local videos directory")
def sync(repo_id: str, local_dir: str):
    """Sync local directory with repository (upload missing files)"""
    console.print(Panel(
        f"🔄 Sync Local to Repository\n"
        f"📦 Repository: {repo_id}\n"
        f"📁 Local directory: {local_dir}",
        title="[bold blue]Sync Configuration[/bold blue]",
        border_style="blue"
    ))

    api = HfApi()

    # Ensure repository exists
    if not ensure_repo_exists(api, repo_id):
        sys.exit(1)

    # Get current state
    repo_videos = set(get_repo_videos(api, repo_id))
    local_videos = get_local_videos(local_dir)
    local_video_names = {v.name: v for v in local_videos}

    # Find files to upload
    to_upload = [
        local_video_names[name]
        for name in local_video_names
        if name not in repo_videos
    ]

    if not to_upload:
        console.print("[green]✅ Already in sync - no files to upload[/green]")
        return

    console.print(f"[yellow]📤 {len(to_upload)} files to upload[/yellow]")

    # Enable high performance xet mode
    os.environ["HF_XET_HIGH_PERFORMANCE"] = "1"

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Syncing...", total=len(to_upload))

        for video in to_upload:
            progress.update(task, description=f"Uploading {video.name}...")

            try:
                upload_file(
                    path_or_fileobj=str(video),
                    path_in_repo=video.name,
                    repo_id=repo_id,
                    repo_type="dataset",
                )
                console.print(f"[green]✅ Uploaded: {video.name}[/green]")
            except Exception as e:
                console.print(f"[red]❌ Failed: {video.name} - {e}[/red]")

            progress.advance(task)

    console.print("[green]✅ Sync complete![/green]")


if __name__ == "__main__":
    cli()
