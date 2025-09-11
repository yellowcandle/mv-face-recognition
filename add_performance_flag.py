#!/usr/bin/env python
"""
Add the optimize-performance flag to main.py
"""

from pathlib import Path

# Get the main.py file path
MAIN_PY = Path("src/main.py")

# Read the content
with open(MAIN_PY, "r") as f:
    content = f.read()

# Find the place to add the option (after the optimize-cache option)
optimize_cache_option = """    optimize_cache: bool = typer.Option(
        False,
        "--optimize-cache",
        help="Preload and optimize cache for faster processing",
    ),"""

# New option to add
new_option = """    optimize_performance: bool = typer.Option(
        True,
        "--optimize-performance/--no-optimize-performance",
        help="Apply performance optimizations for faster processing",
    ),"""

# Add the new option after optimize_cache
if optimize_cache_option in content:
    modified_content = content.replace(
        optimize_cache_option, optimize_cache_option + "\n" + new_option
    )

    # Make sure the initialize_components function accepts the optimize_performance parameter
    if "def initialize_components" in modified_content:
        # Add the parameter to the function definition
        modified_content = modified_content.replace(
            "def initialize_components(", "def initialize_components("
        )

        if "cache_dir: Path" in modified_content:
            modified_content = modified_content.replace(
                "cache_dir: Path",
                "cache_dir: Path,\n    optimize_performance: bool = True",
            )

    # Pass the parameter when calling the function
    if "detector, recognizer, backend = initialize_components(" in modified_content:
        if "optimize_performance=optimize_performance" not in modified_content:
            # Add to the function call
            modified_content = modified_content.replace(
                'cache_dir=paths["cache_dir"]',
                'cache_dir=paths["cache_dir"],\n        optimize_performance=optimize_performance',
            )

    # Write the modified content
    with open(MAIN_PY, "w") as f:
        f.write(modified_content)

    print(f"Added --optimize-performance flag to {MAIN_PY}")
else:
    print(f"Could not find optimize_cache option in {MAIN_PY}")
