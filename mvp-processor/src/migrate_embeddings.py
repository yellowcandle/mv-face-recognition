#!/usr/bin/env python3
"""
Embedding Migration Tool
Migrates existing face embeddings to the unified embedding format
"""

import click
import yaml
import logging
import json
from pathlib import Path
from tqdm import tqdm

from unified_embedding_system import UnifiedEmbeddingSystem, EmbeddingMethod

# Setup logging
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@click.command()
@click.option("--config", "-c", 
              default="config.yaml", 
              help="Configuration file path")
@click.option("--method", "-m", 
              type=click.Choice(['insightface', 'face_recognition', 'opencv_custom']),
              help="Target embedding method (default: auto-detect)")
@click.option("--force", "-f", 
              is_flag=True, 
              help="Force regeneration of existing unified embeddings")
@click.option("--dry-run", "-d", 
              is_flag=True, 
              help="Show what would be migrated without actually doing it")
@click.option("--stats-only", "-s", 
              is_flag=True, 
              help="Only show migration statistics")
def migrate_embeddings(config, method, force, dry_run, stats_only):
    """
    Migrate existing face embeddings to unified format
    
    This tool converts legacy face embeddings to the new unified format,
    ensuring consistent distance calculations and improved recognition accuracy.
    """
    
    try:
        # Load configuration
        with open(config, 'r') as f:
            config_data = yaml.safe_load(f)
        
        logger.info(f"Loaded configuration from {config}")
        
        # Initialize unified embedding system
        embedding_system = UnifiedEmbeddingSystem(config_data)
        
        # Override method if specified
        if method:
            target_method = EmbeddingMethod(method)
            embedding_system.embedding_config.method = target_method
            logger.info(f"Using specified embedding method: {method}")
        else:
            logger.info(f"Using configured embedding method: {embedding_system.embedding_config.method.value}")
        
        # Get embeddings directory
        embeddings_dir = Path(config_data["contestants"]["photo_dir"])
        
        if not embeddings_dir.exists():
            logger.error(f"Embeddings directory does not exist: {embeddings_dir}")
            return
        
        # Show current state
        _show_current_state(embeddings_dir, embedding_system)
        
        if stats_only:
            return
        
        if dry_run:
            logger.info("DRY RUN MODE - No changes will be made")
        
        # Perform migration
        if not dry_run:
            click.echo("\nStarting migration...")
            stats = embedding_system.migrate_embeddings(
                embeddings_dir, 
                target_method=embedding_system.embedding_config.method,
                force_regenerate=force
            )
            
            # Show results
            click.echo(f"\n✅ Migration completed successfully!")
            click.echo(f"   Migrated: {stats['migrated']} embeddings")
            click.echo(f"   Skipped:  {stats['skipped']} embeddings")
            click.echo(f"   Errors:   {stats['errors']} embeddings")
            
            if stats['errors'] > 0:
                click.echo(f"\n⚠️  {stats['errors']} embeddings had errors during migration")
                click.echo("   Check the logs above for details")
        
        # Show system stats
        system_stats = embedding_system.get_statistics()
        click.echo(f"\n📊 Unified Embedding System Statistics:")
        click.echo(f"   Method: {system_stats['config']['method']}")
        click.echo(f"   Dimension: {system_stats['config']['dimension']}")
        click.echo(f"   Normalized: {system_stats['config']['normalized']}")
        click.echo(f"   Distance threshold: {system_stats['config']['distance_threshold']:.3f}")
        
        click.echo(f"\n🔧 Backend Availability:")
        for backend, available in system_stats['backend_availability'].items():
            status = "✅" if available else "❌"
            click.echo(f"   {backend}: {status}")
        
        if not dry_run and stats['migrated'] > 0:
            click.echo(f"\n🎯 Next Steps:")
            click.echo(f"   1. Update your config.yaml to enable unified system:")
            click.echo(f"      face_detection:")
            click.echo(f"        use_unified_system: true")
            click.echo(f"   2. Test the system with a sample video:")
            click.echo(f"      python process_video.py --input sample_video.mp4")
            click.echo(f"   3. Monitor recognition accuracy and adjust thresholds if needed")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        click.echo(f"❌ Migration failed: {e}", err=True)
        raise


def _show_current_state(embeddings_dir: Path, embedding_system: UnifiedEmbeddingSystem):
    """Show current state of embeddings in the directory"""
    
    click.echo(f"\n📁 Analyzing embeddings directory: {embeddings_dir}")
    
    # Find all embedding files
    legacy_files = list(embeddings_dir.glob("*_embedding.npy"))
    unified_files = list(embeddings_dir.glob("*_unified_embedding.npy"))
    metadata_files = list(embeddings_dir.glob("*_embedding_metadata.json"))
    
    click.echo(f"   Legacy embeddings:  {len(legacy_files)}")
    click.echo(f"   Unified embeddings: {len(unified_files)}")
    click.echo(f"   Metadata files:     {len(metadata_files)}")
    
    # Analyze unified embeddings by method
    method_counts = {}
    valid_unified = 0
    
    for metadata_file in metadata_files:
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            method = metadata.get("method", "unknown")
            method_counts[method] = method_counts.get(method, 0) + 1
            
            # Check if it matches current target method
            if method == embedding_system.embedding_config.method.value:
                valid_unified += 1
                
        except Exception as e:
            logger.debug(f"Failed to read metadata {metadata_file}: {e}")
    
    if method_counts:
        click.echo(f"\n🔍 Unified embeddings by method:")
        for method, count in method_counts.items():
            current = " (current)" if method == embedding_system.embedding_config.method.value else ""
            click.echo(f"   {method}: {count}{current}")
    
    click.echo(f"\n📈 Migration Analysis:")
    target_method = embedding_system.embedding_config.method.value
    needs_migration = len(legacy_files) + len(unified_files) - valid_unified
    click.echo(f"   Target method: {target_method}")
    click.echo(f"   Valid unified embeddings: {valid_unified}")
    click.echo(f"   Needs migration: {needs_migration}")
    
    if needs_migration == 0:
        click.echo(f"   ✅ All embeddings are already in unified format with target method")
    else:
        click.echo(f"   ⚠️  {needs_migration} embeddings need migration to {target_method}")


@click.command()
@click.option("--config", "-c", 
              default="config.yaml", 
              help="Configuration file path")
@click.option("--contestant-photos", "-p",
              help="Path to contestant photos directory")
@click.option("--force", "-f", 
              is_flag=True, 
              help="Force regeneration of existing embeddings")
def regenerate_from_photos(config, contestant_photos, force):
    """
    Regenerate embeddings directly from contestant photos
    
    This command generates unified embeddings directly from the original
    contestant photos, which can provide better quality than migrating
    from existing embeddings.
    """
    
    try:
        # Load configuration
        with open(config, 'r') as f:
            config_data = yaml.safe_load(f)
        
        # Override photo directory if provided
        if contestant_photos:
            config_data["contestants"]["photo_dir"] = contestant_photos
        
        # Initialize system
        from unified_face_detector import UnifiedContestantDatabase, UnifiedEmbeddingSystem
        
        embedding_system = UnifiedEmbeddingSystem(config_data)
        contestant_db = UnifiedContestantDatabase(config_data, embedding_system)
        
        # Load contestant info
        contestant_db.load_contestants_info()
        
        logger.info(f"Loaded {len(contestant_db.contestants_info)} contestants")
        
        # Regenerate embeddings from photos
        if not force:
            click.confirm(f"This will regenerate embeddings from photos. Continue?", abort=True)
        
        stats = contestant_db.regenerate_embeddings_from_photos(force_regenerate=force)
        
        # Show results
        click.echo(f"\n✅ Regeneration completed!")
        click.echo(f"   Generated: {stats['generated']} embeddings")
        click.echo(f"   Skipped:   {stats['skipped']} embeddings")
        click.echo(f"   Errors:    {stats['errors']} embeddings")
        
        if stats['errors'] > 0:
            click.echo(f"\n⚠️  {stats['errors']} photos could not be processed")
            click.echo("   Make sure all contestant photos exist in the specified directory")
        
    except Exception as e:
        logger.error(f"Regeneration failed: {e}")
        click.echo(f"❌ Regeneration failed: {e}", err=True)
        raise


@click.group()
def cli():
    """Unified Face Embedding System Tools"""
    pass


cli.add_command(migrate_embeddings)
cli.add_command(regenerate_from_photos)


if __name__ == "__main__":
    cli()