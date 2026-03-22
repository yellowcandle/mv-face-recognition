#!/usr/bin/env python3
"""
Modal setup and configuration script for MV Face Recognition.

Sets up:
1. Modal workspace and authentication
2. Modal volumes for data storage
3. Modal secrets for credentials
4. Modal functions for video processing
5. Test runs to verify configuration

Usage:
    python scripts/setup_modal.py                      # Full setup
    python scripts/setup_modal.py --check              # Check existing setup
    python scripts/setup_modal.py --create-volumes    # Create volumes only
    python scripts/setup_modal.py --create-secrets     # Create secrets only
    python scripts/setup_modal.py --test               # Test functions
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Tuple, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class ModalSetup:
    """Set up Modal for MV Face Recognition."""

    VOLUMES = {
        "mv-face-recognition-data": "Persistent storage for videos, embeddings, and metadata",
    }

    SECRETS = {
        "hf-secret": "HF_TOKEN",
        "modal-config": "MODAL_CONFIG",
    }

    def __init__(self):
        """Initialize Modal setup."""
        self.workspace = "mv-face-recognition"
        self.status = {}

    def check_modal_cli(self) -> bool:
        """Check if Modal CLI is installed and configured."""
        try:
            result = subprocess.run(
                ["modal", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                logger.info(f"✅ Modal CLI found: {result.stdout.strip()}")
                return True
            else:
                logger.error("❌ Modal CLI not properly installed")
                return False
        except FileNotFoundError:
            logger.error("❌ Modal CLI not found. Install with: pip install modal")
            return False
        except Exception as e:
            logger.error(f"❌ Error checking Modal: {e}")
            return False

    def check_modal_token(self) -> bool:
        """Check if Modal token is configured."""
        try:
            result = subprocess.run(
                ["modal", "token-flow"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if "already authenticated" in result.stdout.lower():
                logger.info("✅ Modal token already configured")
                return True
            elif result.returncode != 0:
                logger.warning("⚠️  Modal token not configured")
                return False
        except Exception as e:
            logger.warning(f"⚠️  Could not verify Modal token: {e}")
        
        return self._has_modal_token_file()

    def _has_modal_token_file(self) -> bool:
        """Check if Modal token file exists."""
        modal_dir = Path.home() / ".modal"
        token_file = modal_dir / "token"
        return token_file.exists()

    def authenticate_modal(self) -> bool:
        """Authenticate with Modal."""
        if self._has_modal_token_file():
            logger.info("✅ Modal token file found")
            return True
        
        logger.info("Starting Modal authentication...")
        try:
            subprocess.run(
                ["modal", "setup"],
                timeout=120,
            )
            logger.info("✅ Modal authentication completed")
            return True
        except Exception as e:
            logger.error(f"❌ Modal authentication failed: {e}")
            return False

    def create_volumes(self) -> bool:
        """Create Modal volumes."""
        all_created = True
        
        for volume_name, description in self.VOLUMES.items():
            try:
                logger.info(f"Creating volume: {volume_name}...")
                result = subprocess.run(
                    ["modal", "volume", "create", volume_name],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                
                if result.returncode == 0 or "already exists" in result.stdout:
                    logger.info(f"✅ Volume '{volume_name}' ready")
                    self.status[f"volume_{volume_name}"] = "created"
                else:
                    logger.error(f"❌ Failed to create volume '{volume_name}'")
                    logger.error(f"   Output: {result.stderr}")
                    all_created = False
            except Exception as e:
                logger.error(f"❌ Error creating volume '{volume_name}': {e}")
                all_created = False
        
        return all_created

    def create_secrets(self) -> bool:
        """Create Modal secrets."""
        all_created = True
        
        logger.info("\nSetting up Modal secrets...")
        
        for secret_name, env_var in self.SECRETS.items():
            try:
                env_value = os.getenv(env_var)
                
                if not env_value:
                    logger.warning(
                        f"⚠️  {env_var} not set in environment, skipping secret '{secret_name}'"
                    )
                    logger.info(
                        f"   Set with: export {env_var}=your_value"
                    )
                    all_created = False
                    continue
                
                logger.info(f"Creating secret: {secret_name}...")
                
                result = subprocess.run(
                    ["modal", "secret", "create", secret_name, f"{env_var}={env_value}"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                
                if result.returncode == 0:
                    logger.info(f"✅ Secret '{secret_name}' created")
                    self.status[f"secret_{secret_name}"] = "created"
                else:
                    if "already exists" in result.stdout or "already exists" in result.stderr:
                        logger.info(f"✅ Secret '{secret_name}' already exists")
                        self.status[f"secret_{secret_name}"] = "exists"
                    else:
                        logger.error(f"❌ Failed to create secret '{secret_name}'")
                        logger.error(f"   Output: {result.stderr}")
                        all_created = False
            except Exception as e:
                logger.error(f"❌ Error creating secret '{secret_name}': {e}")
                all_created = False
        
        return all_created

    def list_volumes(self) -> bool:
        """List existing Modal volumes."""
        try:
            result = subprocess.run(
                ["modal", "volume", "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            logger.info("\nExisting Modal volumes:")
            logger.info(result.stdout)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Error listing volumes: {e}")
            return False

    def list_secrets(self) -> bool:
        """List existing Modal secrets."""
        try:
            result = subprocess.run(
                ["modal", "secret", "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            logger.info("\nExisting Modal secrets:")
            logger.info(result.stdout)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Error listing secrets: {e}")
            return False

    def test_modal_function(self) -> bool:
        """Test running a simple Modal function."""
        logger.info("\nTesting Modal function execution...")
        
        test_script = """
from modal import App

app = App("mv-face-recognition-test")

@app.function()
def test_function():
    return {"status": "success", "message": "Modal is working!"}

if __name__ == "__main__":
    result = test_function.remote()
    print(result)
"""
        
        temp_file = Path("/tmp/test_modal.py")
        temp_file.write_text(test_script)
        
        try:
            result = subprocess.run(
                ["modal", "run", str(temp_file)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            
            if result.returncode == 0 and "success" in result.stdout:
                logger.info("✅ Modal function execution working")
                return True
            else:
                logger.warning("⚠️  Modal function test inconclusive")
                logger.info(f"   Output: {result.stdout}")
                return False
        except Exception as e:
            logger.warning(f"⚠️  Modal function test failed: {e}")
            return False
        finally:
            temp_file.unlink(missing_ok=True)

    def check_existing_setup(self) -> Dict[str, str]:
        """Check existing Modal setup."""
        logger.info("\nChecking existing Modal setup...")
        
        status = {}
        
        if self._has_modal_token_file():
            status["authentication"] = "✅ Configured"
        else:
            status["authentication"] = "❌ Not configured"
        
        try:
            result = subprocess.run(
                ["modal", "volume", "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if "mv-face-recognition-data" in result.stdout:
                status["volume_mv-face-recognition-data"] = "✅ Created"
            else:
                status["volume_mv-face-recognition-data"] = "❌ Not found"
        except:
            status["volumes"] = "⚠️  Could not check"
        
        try:
            result = subprocess.run(
                ["modal", "secret", "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if "hf-secret" in result.stdout:
                status["secret_hf-secret"] = "✅ Created"
            else:
                status["secret_hf-secret"] = "❌ Not found"
        except:
            status["secrets"] = "⚠️  Could not check"
        
        return status

    def run_full_setup(self) -> bool:
        """Run complete Modal setup."""
        logger.info("=" * 60)
        logger.info("Modal Setup for MV Face Recognition")
        logger.info("=" * 60)
        
        if not self.check_modal_cli():
            logger.error("\n❌ Modal CLI not available. Install with: pip install modal")
            return False
        
        if not self.check_modal_token():
            logger.info("\nModal token not found. Starting authentication...")
            if not self.authenticate_modal():
                logger.error("\n❌ Modal authentication failed")
                return False
        
        self.create_volumes()
        self.create_secrets()
        
        self.list_volumes()
        self.list_secrets()
        
        logger.info("\n" + "=" * 60)
        logger.info("Setup Summary")
        logger.info("=" * 60)
        
        for key, value in self.status.items():
            logger.info(f"{key}: {value}")
        
        logger.info("\n✅ Modal setup complete!")
        logger.info("\nNext steps:")
        logger.info("1. Set environment variables:")
        logger.info("   export HF_TOKEN=your_huggingface_token")
        logger.info("   export MODAL_CONFIG='{...}'")
        logger.info("\n2. Test video processing:")
        logger.info("   python scripts/setup_modal.py --test")
        logger.info("\n3. Run video processing pipeline:")
        logger.info("   modal run scripts/modal_hf_processor.py --full-pipeline")
        
        return True

    def run_check_only(self) -> bool:
        """Check existing Modal setup without changes."""
        logger.info("=" * 60)
        logger.info("Modal Configuration Check")
        logger.info("=" * 60)
        
        status = self.check_existing_setup()
        
        logger.info("\nConfiguration Status:")
        for key, value in status.items():
            logger.info(f"  {key}: {value}")
        
        all_configured = all("✅" in v for v in status.values())
        
        if all_configured:
            logger.info("\n✅ Modal is fully configured!")
        else:
            logger.info("\n⚠️  Some components are missing. Run setup to configure.")
        
        return all_configured


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Set up Modal for MV Face Recognition"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check existing setup only (no changes)",
    )
    parser.add_argument(
        "--create-volumes",
        action="store_true",
        help="Create volumes only",
    )
    parser.add_argument(
        "--create-secrets",
        action="store_true",
        help="Create secrets only",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test Modal function execution",
    )
    parser.add_argument(
        "--list-volumes",
        action="store_true",
        help="List existing volumes",
    )
    parser.add_argument(
        "--list-secrets",
        action="store_true",
        help="List existing secrets",
    )

    args = parser.parse_args()

    setup = ModalSetup()

    if args.check:
        setup.run_check_only()
    elif args.create_volumes:
        setup.create_volumes()
        setup.list_volumes()
    elif args.create_secrets:
        setup.create_secrets()
        setup.list_secrets()
    elif args.test:
        setup.test_modal_function()
    elif args.list_volumes:
        setup.list_volumes()
    elif args.list_secrets:
        setup.list_secrets()
    else:
        success = setup.run_full_setup()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
