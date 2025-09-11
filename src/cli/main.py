from __future__ import annotations

import json
from pathlib import Path

import click

# Import contestant loader helpers for T018/T022 compatibility
from src.models.contestant import load_contestants_from_csv

# Determine a stable project root for storing runtime state
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_DIR = PROJECT_ROOT / "db"
INIT_STATE_FILE = DB_DIR / "init_state.json"


def _ensure_db_dir() -> None:
    DB_DIR.mkdir(parents=True, exist_ok=True)


def _load_init_state() -> dict:
    if INIT_STATE_FILE.exists():
        try:
            with INIT_STATE_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_init_state(state: dict) -> None:
    _ensure_db_dir()
    with INIT_STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


@click.group()
def cli():
    """MV Face Recognition CLI (stub)"""
    pass


@cli.command()
@click.option(
    "--contestant-csv",
    required=True,
    type=click.Path(exists=False),
    help="Path to contestants CSV",
)
@click.option(
    "--photos-dir",
    required=True,
    type=click.Path(exists=False),
    help="Directory with contestant photos",
)
@click.option(
    "--model", default="default", show_default=True, help="Model identifier to use"
)
def init(contestant_csv: str, photos_dir: str, model: str) -> None:
    """
    Initialize the data store and embeddings for contestants.
    This is a lightweight stub used for integration tests.
    """
    import time

    _ensure_db_dir()
    entry_count = 0
    if contestant_csv:
        try:
            contestants = load_contestants_from_csv(contestant_csv)
            entry_count = len(contestants)
        except Exception:
            entry_count = 0

    state = {
        "contestant_csv": str(contestant_csv),
        "photos_dir": str(photos_dir),
        "model": model,
        "entries": int(entry_count),
        "initialized_at": int(time.time()),
    }
    _save_init_state(state)
    click.echo(f"Initialized with {entry_count} entries using model {model}.")


@cli.command(name="process")
def process() -> None:
    """
    Lightweight placeholder processing command.
    """
    click.echo("Process command is a stub in this codebase.")


@cli.command(name="list")
def list_cmd() -> None:
    """
    Lightweight placeholder listing command.
    """
    click.echo("List of items: (stub)")


@cli.command()
def status() -> None:
    """
    Show the current init state.
    """
    state = _load_init_state()
    if not state:
        click.echo("Status: not initialized")
        return
    click.echo("Status: initialized")
    click.echo(json.dumps(state, indent=2))


# Compatibility aliases for tests that import status_command and list_command
status_command = status
list_command = list_cmd


def main() -> None:
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
