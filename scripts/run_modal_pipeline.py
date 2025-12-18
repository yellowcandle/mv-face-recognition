#!/usr/bin/env python3
"""
Modal + Huggingface Video Processing Pipeline Orchestrator

This script provides a unified interface to:
1. Upload local videos to Huggingface (with xet storage)
2. Process videos on Modal cloud infrastructure
3. Download processed results
4. Optionally upload to Cloudflare R2

Usage:
    # Full pipeline: upload -> process -> download results
    python scripts/run_modal_pipeline.py full

    # Upload only: sync local videos to Huggingface
    python scripts/run_modal_pipeline.py upload

    # Process only: run Modal processing on HF videos
    python scripts/run_modal_pipeline.py process

    # Download results from Modal volume
    python scripts/run_modal_pipeline.py download-results

    # Check status
    python scripts/run_modal_pipeline.py status
"""

import os
import sys
import subprocess
import click
from pathlib import Path
from typing import Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
except ImportError:
    print("Missing rich library. Install with: pip install rich")
    sys.exit(1)

console = Console()

# Configuration
HF_REPO_ID = "yellowcandle/mv-face-recognition-videos"
LOCAL_VIDEOS_DIR = "source/videos"
MODAL_VOLUME_NAME = "mv-face-recognition-data"


def run_command(cmd: list, description: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command with status output."""
    console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")
    try:
        result = subprocess.run(cmd, check=check, capture_output=True, text=True)
        if result.stdout:
            console.print(result.stdout)
        return result
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e.stderr}[/red]")
        raise


def check_prerequisites() -> bool:
    """Check that all required tools are installed."""
    missing = []

    # Check Modal CLI
    try:
        subprocess.run(["modal", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        missing.append("modal (pip install modal)")

    # Check huggingface_hub
    try:
        import huggingface_hub
        if not hasattr(huggingface_hub, '__version__') or \
           tuple(map(int, huggingface_hub.__version__.split('.')[:2])) < (0, 32):
            missing.append("huggingface_hub >= 0.32.0 (pip install 'huggingface_hub>=0.32.0')")
    except ImportError:
        missing.append("huggingface_hub >= 0.32.0 (pip install 'huggingface_hub>=0.32.0')")

    # Check HF token
    if not os.environ.get("HF_TOKEN") and not os.environ.get("HUGGING_FACE_HUB_TOKEN"):
        try:
            from huggingface_hub import HfFolder
            if not HfFolder.get_token():
                console.print("[yellow]⚠️ No Huggingface token found. Run: huggingface-cli login[/yellow]")
        except Exception:
            console.print("[yellow]⚠️ Could not verify Huggingface authentication[/yellow]")

    if missing:
        console.print(Panel(
            "\n".join([f"❌ {dep}" for dep in missing]),
            title="[red]Missing Dependencies[/red]",
            border_style="red"
        ))
        return False

    return True


@click.group()
def cli():
    """Modal + Huggingface Video Processing Pipeline"""
    pass


@cli.command()
@click.option("--local-dir", default=LOCAL_VIDEOS_DIR, help="Local videos directory")
@click.option("--repo-id", default=HF_REPO_ID, help="Huggingface repository ID")
def upload(local_dir: str, repo_id: str):
    """Upload local videos to Huggingface repository"""
    console.print(Panel(
        f"📤 Uploading videos to Huggingface\n"
        f"📁 Source: {local_dir}\n"
        f"📦 Target: {repo_id}",
        title="[bold blue]Upload to Huggingface[/bold blue]",
        border_style="blue"
    ))

    if not check_prerequisites():
        sys.exit(1)

    # Run the upload script
    cmd = [
        sys.executable,
        "scripts/hf_video_manager.py",
        "upload",
        "--local-dir", local_dir,
        "--repo-id", repo_id,
    ]

    result = run_command(cmd, "Uploading videos", check=False)

    if result.returncode == 0:
        console.print("[green]✅ Upload complete![/green]")
    else:
        console.print("[red]❌ Upload failed[/red]")
        sys.exit(1)


@cli.command()
@click.option("--parallel", is_flag=True, help="Process videos in parallel")
@click.option("--max-containers", default=4, help="Maximum parallel containers")
@click.option("--video", help="Process specific video only")
@click.option("--similarity-threshold", default=0.25, help="Face matching threshold")
@click.option("--force", is_flag=True, help="Force reprocessing")
def process(parallel: bool, max_containers: int, video: Optional[str], similarity_threshold: float, force: bool):
    """Process videos on Modal using Huggingface source"""
    console.print(Panel(
        f"🔧 Processing videos on Modal\n"
        f"⚡ Parallel: {parallel}\n"
        f"🎯 Threshold: {similarity_threshold}",
        title="[bold blue]Modal Processing[/bold blue]",
        border_style="blue"
    ))

    if not check_prerequisites():
        sys.exit(1)

    # Build modal command
    cmd = ["modal", "run", "modal_hf_processor.py"]

    if video:
        cmd.extend(["--video", video])
    elif parallel:
        cmd.extend(["--parallel", "--max-containers", str(max_containers)])

    cmd.extend(["--similarity-threshold", str(similarity_threshold)])

    if force:
        cmd.append("--force-reprocess")

    console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")

    # Run Modal command (stream output)
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    for line in process.stdout:
        print(line, end='')

    process.wait()

    if process.returncode == 0:
        console.print("[green]✅ Processing complete![/green]")
    else:
        console.print("[red]❌ Processing failed[/red]")
        sys.exit(1)


@cli.command("download-results")
@click.option("--output-dir", default="output", help="Local output directory")
def download_results(output_dir: str):
    """Download processed results from Modal volume"""
    console.print(Panel(
        f"📥 Downloading results from Modal volume\n"
        f"📁 Target: {output_dir}",
        title="[bold blue]Download Results[/bold blue]",
        border_style="blue"
    ))

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Download different result types
    result_dirs = [
        ("processed_videos", "Processed videos"),
        ("metadata", "Metadata files"),
        ("thumbnails", "Thumbnails"),
        ("galleries", "Galleries"),
    ]

    for remote_dir, description in result_dirs:
        console.print(f"[blue]📥 Downloading {description}...[/blue]")

        local_subdir = output_path / remote_dir
        local_subdir.mkdir(parents=True, exist_ok=True)

        cmd = [
            "modal", "volume", "get",
            MODAL_VOLUME_NAME,
            f"/{remote_dir}",
            str(local_subdir),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                console.print(f"[green]✅ Downloaded {description}[/green]")
            else:
                console.print(f"[yellow]⚠️ No {description} found or empty[/yellow]")
        except Exception as e:
            console.print(f"[red]❌ Error downloading {description}: {e}[/red]")

    console.print(Panel(
        f"✅ Results downloaded to: {output_path.absolute()}",
        title="[bold green]Download Complete[/bold green]",
        border_style="green"
    ))


@cli.command()
def status():
    """Show pipeline status"""
    console.print(Panel(
        "📊 Checking pipeline status...",
        title="[bold blue]Pipeline Status[/bold blue]",
        border_style="blue"
    ))

    # Video extensions to check
    video_extensions = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm", ".m4v"}

    # Check local videos
    local_path = Path(LOCAL_VIDEOS_DIR)
    local_videos = list(local_path.glob("*")) if local_path.exists() else []
    local_video_names = {f.name for f in local_videos if f.suffix.lower() in video_extensions}
    local_video_count = len(local_video_names)

    # Check HF repository
    hf_video_names = set()
    try:
        from huggingface_hub import HfApi
        api = HfApi()
        files = api.list_repo_files(repo_id=HF_REPO_ID, repo_type="dataset")
        hf_video_names = {f for f in files if Path(f).suffix.lower() in video_extensions}
        hf_video_count = len(hf_video_names)
        hf_status = f"✅ {hf_video_count} videos"
    except Exception as e:
        hf_status = f"❌ Error: {str(e)[:50]}"
        hf_video_count = 0

    # Check Modal volume
    try:
        result = subprocess.run(
            ["modal", "volume", "ls", MODAL_VOLUME_NAME, "/"],
            capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            modal_status = "✅ Connected"
        else:
            modal_status = "⚠️ Empty or not found"
    except Exception:
        modal_status = "❌ Modal CLI not available"

    # Display status table
    table = Table(title="Pipeline Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details", style="yellow")

    table.add_row("Local Videos", f"{local_video_count} files", str(local_path.absolute()))
    table.add_row("Huggingface Repo", hf_status, HF_REPO_ID)
    table.add_row("Modal Volume", modal_status, MODAL_VOLUME_NAME)

    console.print(table)

    # Show sync status by comparing actual filenames, not just counts
    if local_video_count > 0 or hf_video_count > 0:
        only_local = local_video_names - hf_video_names
        only_hf = hf_video_names - local_video_names

        if only_local:
            console.print(f"\n[yellow]📤 {len(only_local)} local videos not yet uploaded to HF[/yellow]")
            for v in sorted(only_local)[:5]:  # Show first 5
                console.print(f"   • {v}")
            if len(only_local) > 5:
                console.print(f"   ... and {len(only_local) - 5} more")

        if only_hf:
            console.print(f"\n[yellow]📥 {len(only_hf)} HF videos not downloaded locally[/yellow]")
            for v in sorted(only_hf)[:5]:  # Show first 5
                console.print(f"   • {v}")
            if len(only_hf) > 5:
                console.print(f"   ... and {len(only_hf) - 5} more")

        if not only_local and not only_hf and local_video_count > 0:
            console.print("\n[green]✅ Local and HF repository are in sync[/green]")


@cli.command()
@click.option("--local-dir", default=LOCAL_VIDEOS_DIR, help="Local videos directory")
@click.option("--repo-id", default=HF_REPO_ID, help="Huggingface repository ID")
@click.option("--parallel", is_flag=True, default=True, help="Process videos in parallel")
@click.option("--max-containers", default=4, help="Maximum parallel containers")
@click.option("--similarity-threshold", default=0.25, help="Face matching threshold")
@click.option("--output-dir", default="output", help="Local output directory")
@click.option("--skip-upload", is_flag=True, help="Skip uploading to HF (use existing)")
@click.option("--skip-download", is_flag=True, help="Skip downloading results")
def full(
    local_dir: str,
    repo_id: str,
    parallel: bool,
    max_containers: int,
    similarity_threshold: float,
    output_dir: str,
    skip_upload: bool,
    skip_download: bool,
):
    """Run the full pipeline: upload -> process -> download"""
    console.print(Panel(
        "🚀 Running Full Modal + Huggingface Pipeline\n\n"
        "Steps:\n"
        "1. Upload local videos to Huggingface\n"
        "2. Process videos on Modal cloud\n"
        "3. Download processed results",
        title="[bold blue]Full Pipeline[/bold blue]",
        border_style="blue"
    ))

    if not check_prerequisites():
        sys.exit(1)

    # Step 1: Upload to Huggingface
    if not skip_upload:
        console.print("\n" + "="*60)
        console.print("[bold blue]Step 1: Upload to Huggingface[/bold blue]")
        console.print("="*60 + "\n")

        cmd = [
            sys.executable,
            "scripts/hf_video_manager.py",
            "sync",
            "--local-dir", local_dir,
            "--repo-id", repo_id,
        ]
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            console.print("[yellow]⚠️ Upload had issues, continuing...[/yellow]")
    else:
        console.print("[dim]Skipping upload step[/dim]")

    # Step 2: Process on Modal
    console.print("\n" + "="*60)
    console.print("[bold blue]Step 2: Process on Modal[/bold blue]")
    console.print("="*60 + "\n")

    cmd = ["modal", "run", "modal_hf_processor.py"]
    if parallel:
        cmd.extend(["--parallel", "--max-containers", str(max_containers)])
    cmd.extend(["--similarity-threshold", str(similarity_threshold)])

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    for line in process.stdout:
        print(line, end='')

    process.wait()

    if process.returncode != 0:
        console.print("[red]❌ Processing failed[/red]")
        sys.exit(1)

    # Step 3: Download results
    if not skip_download:
        console.print("\n" + "="*60)
        console.print("[bold blue]Step 3: Download Results[/bold blue]")
        console.print("="*60 + "\n")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        for remote_dir in ["processed_videos", "metadata", "thumbnails", "galleries"]:
            local_subdir = output_path / remote_dir
            local_subdir.mkdir(parents=True, exist_ok=True)

            cmd = [
                "modal", "volume", "get",
                MODAL_VOLUME_NAME,
                f"/{remote_dir}",
                str(local_subdir),
            ]
            subprocess.run(cmd, check=False)

        console.print(f"[green]✅ Results downloaded to: {output_path.absolute()}[/green]")
    else:
        console.print("[dim]Skipping download step[/dim]")

    # Final summary
    console.print(Panel(
        "✅ Pipeline Complete!\n\n"
        f"📦 Videos stored in: {repo_id}\n"
        f"📁 Results saved to: {output_dir}",
        title="[bold green]Success[/bold green]",
        border_style="green"
    ))


@cli.command("list-hf")
@click.option("--repo-id", default=HF_REPO_ID, help="Huggingface repository ID")
def list_hf(repo_id: str):
    """List videos in Huggingface repository"""
    cmd = [
        sys.executable,
        "scripts/hf_video_manager.py",
        "list",
        "--repo-id", repo_id,
    ]
    subprocess.run(cmd)


@cli.command("clear-cache")
@click.option("--all", "clear_all", is_flag=True, help="Clear all cached data")
def clear_cache(clear_all: bool):
    """Clear Modal volume cache"""
    console.print("[yellow]🗑️ Clearing Modal volume cache...[/yellow]")

    cmd = ["modal", "run", "modal_hf_processor.py", "--clear-cache-all"]
    subprocess.run(cmd)


if __name__ == "__main__":
    cli()
