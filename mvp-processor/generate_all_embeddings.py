#!/usr/bin/env python3
"""
Streamlined Embedding Generation for MV Face Recognition
Generates unified embeddings for all 96 contestants using ID-based photo structure

Usage:
    python generate_all_embeddings.py [--force] [--config config.yaml]
"""

import sys
import logging
import pandas as pd
import numpy as np
import json
from pathlib import Path
from tqdm import tqdm
import click
from datetime import datetime

# Setup paths
sys.path.append('src')
from unified_embedding_system import UnifiedEmbeddingSystem, EmbeddingMethod

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@click.command()
@click.option("--config", "-c", 
              default="config/processing_config.yaml", 
              help="Configuration file path")
@click.option("--force", "-f", 
              is_flag=True, 
              help="Force regeneration of existing embeddings")
@click.option("--validate-only", "-v", 
              is_flag=True, 
              help="Only validate existing embeddings without generating new ones")
@click.option("--contestant-id", "-i", 
              type=int,
              help="Generate embedding for specific contestant ID (1-96)")
def main(config, force, validate_only, contestant_id):
    """Generate unified embeddings for all contestants using ID-based photo structure"""
    
    try:
        # Load configuration
        import yaml
        with open(config, 'r') as f:
            config_data = yaml.safe_load(f)
        
        # Initialize unified embedding system
        embedding_system = UnifiedEmbeddingSystem(config_data)
        
        # Load contestant info
        contestant_csv = Path("../source/contestant_info.csv")
        if not contestant_csv.exists():
            raise FileNotFoundError(f"Contestant info CSV not found: {contestant_csv}")
        
        contestants_df = pd.read_csv(contestant_csv)
        logger.info(f"Loaded {len(contestants_df)} contestants from CSV")
        
        # Photo and output directories
        photo_base_dir = Path("../source/photo/contestants")
        output_dir = Path("../source/photo/contestants")
        
        if not photo_base_dir.exists():
            raise FileNotFoundError(f"Photo directory not found: {photo_base_dir}")
        
        # Statistics
        stats = {
            "total": 0,
            "generated": 0,
            "skipped": 0,
            "errors": 0,
            "start_time": datetime.now()
        }
        
        # Process contestants
        if contestant_id:
            # Single contestant mode
            contestants_to_process = contestants_df[contestants_df['編號'] == contestant_id]
            if contestants_to_process.empty:
                raise ValueError(f"Contestant ID {contestant_id} not found in CSV")
        else:
            # All contestants mode
            contestants_to_process = contestants_df
        
        stats["total"] = len(contestants_to_process)
        
        with tqdm(total=stats["total"], desc="Processing contestants") as pbar:
            for _, row in contestants_to_process.iterrows():
                contestant_id = int(row['編號'])
                name = row['姓名']
                nickname = row['暱稱']
                
                try:
                    result = process_contestant(
                        contestant_id, name, nickname,
                        photo_base_dir, output_dir,
                        embedding_system, force, validate_only
                    )
                    
                    if result == "generated":
                        stats["generated"] += 1
                    elif result == "skipped":
                        stats["skipped"] += 1
                    elif result == "error":
                        stats["errors"] += 1
                        
                except Exception as e:
                    logger.error(f"Failed to process contestant {contestant_id} ({nickname}): {e}")
                    stats["errors"] += 1
                
                pbar.update(1)
                pbar.set_postfix({
                    "Generated": stats["generated"],
                    "Skipped": stats["skipped"],
                    "Errors": stats["errors"]
                })
        
        # Final results
        elapsed = datetime.now() - stats["start_time"]
        
        click.echo(f"\n✅ Embedding generation completed!")
        click.echo(f"   Total:     {stats['total']} contestants")
        click.echo(f"   Generated: {stats['generated']} embeddings")
        click.echo(f"   Skipped:   {stats['skipped']} embeddings")
        click.echo(f"   Errors:    {stats['errors']} embeddings")
        click.echo(f"   Duration:  {elapsed.total_seconds():.1f} seconds")
        
        if stats["errors"] > 0:
            click.echo(f"\n⚠️  {stats['errors']} contestants could not be processed")
            click.echo("   Check logs for details")
        
        # Validation summary
        if not validate_only:
            validate_all_embeddings(output_dir, contestants_df)
            
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        click.echo(f"❌ Generation failed: {e}", err=True)
        sys.exit(1)


def process_contestant(contestant_id, name, nickname, photo_base_dir, output_dir, 
                      embedding_system, force, validate_only):
    """Process a single contestant's embedding"""
    
    # Output files
    embedding_path = output_dir / f"contestant_{contestant_id}_unified_embedding.npy"
    metadata_path = output_dir / f"contestant_{contestant_id}_embedding_metadata.json"
    
    # Check if already exists
    if embedding_path.exists() and metadata_path.exists() and not force:
        if validate_only:
            # Validate existing embedding
            try:
                embedding = np.load(embedding_path)
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                
                expected_method = embedding_system.embedding_config.method.value
                if metadata.get("method") == expected_method and len(embedding) == 512:
                    logger.debug(f"Validated embedding for contestant {contestant_id} ({nickname})")
                    return "skipped"
                else:
                    logger.warning(f"Invalid embedding for contestant {contestant_id}: method={metadata.get('method')}, dim={len(embedding)}")
                    return "error"
            except Exception as e:
                logger.error(f"Failed to validate embedding for contestant {contestant_id}: {e}")
                return "error"
        else:
            logger.debug(f"Embedding already exists for contestant {contestant_id} ({nickname})")
            return "skipped"
    
    if validate_only:
        logger.warning(f"Missing embedding for contestant {contestant_id} ({nickname})")
        return "error"
    
    # Find photo files
    contestant_dir = photo_base_dir / str(contestant_id)
    if not contestant_dir.exists():
        logger.error(f"Photo directory not found for contestant {contestant_id}: {contestant_dir}")
        return "error"
    
    # Look for primary photo ({id}-1.jpg/png)
    photo_extensions = ['.jpg', '.jpeg', '.png']
    photo_path = None
    
    for ext in photo_extensions:
        candidate = contestant_dir / f"{contestant_id}-1{ext}"
        if candidate.exists():
            photo_path = candidate
            break
    
    if not photo_path:
        logger.error(f"No primary photo found for contestant {contestant_id} in {contestant_dir}")
        return "error"
    
    try:
        # Generate embedding
        logger.debug(f"Generating embedding for contestant {contestant_id} from {photo_path}")
        embedding, metadata = embedding_system.generate_embedding(str(photo_path))
        
        if embedding is None:
            logger.error(f"Failed to generate embedding for contestant {contestant_id}")
            return "error"
        
        # Save embedding
        np.save(embedding_path, embedding)
        
        # Save metadata
        enhanced_metadata = {
            "contestant_id": contestant_id,
            "name": name,
            "nickname": nickname,
            "method": embedding_system.embedding_config.method.value,
            "source_photo": str(photo_path),
            "dimension": len(embedding),
            "generated_at": datetime.now().isoformat(),
            **metadata
        }
        
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(enhanced_metadata, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Generated embedding for contestant {contestant_id} ({nickname})")
        return "generated"
        
    except Exception as e:
        logger.error(f"Failed to generate embedding for contestant {contestant_id}: {e}")
        return "error"


def validate_all_embeddings(output_dir, contestants_df):
    """Validate that all contestants have embeddings"""
    
    click.echo(f"\n🔍 Validation Summary:")
    
    valid_count = 0
    missing_count = 0
    invalid_count = 0
    
    for _, row in contestants_df.iterrows():
        contestant_id = int(row['編號'])
        nickname = row['暱稱']
        
        embedding_path = output_dir / f"contestant_{contestant_id}_unified_embedding.npy"
        metadata_path = output_dir / f"contestant_{contestant_id}_embedding_metadata.json"
        
        if embedding_path.exists() and metadata_path.exists():
            try:
                embedding = np.load(embedding_path)
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                
                if len(embedding) == 512 and metadata.get("method") in ["insightface", "face_recognition", "opencv_custom"]:
                    valid_count += 1
                else:
                    invalid_count += 1
                    click.echo(f"   ❌ Invalid: {contestant_id} ({nickname}) - dim={len(embedding)}, method={metadata.get('method')}")
            except Exception as e:
                invalid_count += 1
                click.echo(f"   ❌ Corrupt: {contestant_id} ({nickname}) - {e}")
        else:
            missing_count += 1
            click.echo(f"   ⚠️  Missing: {contestant_id} ({nickname})")
    
    click.echo(f"   ✅ Valid:   {valid_count}/96 contestants")
    click.echo(f"   ⚠️  Missing: {missing_count}/96 contestants")
    click.echo(f"   ❌ Invalid: {invalid_count}/96 contestants")
    
    if valid_count == 96:
        click.echo(f"\n🎉 Perfect! All 96 contestants have valid embeddings!")
    else:
        click.echo(f"\n⚠️  System needs {96 - valid_count} more embeddings for full coverage")


if __name__ == "__main__":
    main()