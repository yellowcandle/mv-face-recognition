"""
Contract tests for data protection functionality.
Tests the FaceDataEncryption class against defined contracts.
"""

import pytest
from src.encryption import FaceDataEncryption


class TestFaceDataEncryption:
    """Test suite for FaceDataEncryption contract compliance."""

    def setup_method(self):
        """Set up test fixtures."""
        self.encryption = FaceDataEncryption()

    def test_encrypt_embedding(self):
        """Test face embedding encryption."""
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        encrypted = self.encryption.encrypt_embedding(embedding)

        assert isinstance(encrypted, str)
        assert len(encrypted) > 0
        # Should be different from original
        assert encrypted != str(embedding)

    def test_decrypt_embedding(self):
        """Test face embedding decryption."""
        original_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        encrypted = self.encryption.encrypt_embedding(original_embedding)
        decrypted = self.encryption.decrypt_embedding(encrypted)

        assert decrypted == original_embedding

    def test_encrypt_decrypt_roundtrip(self):
        """Test full encryption/decryption roundtrip."""
        test_embeddings = [
            [0.0, 0.0, 0.0],
            [1.0, -1.0, 0.5],
            [0.123456, 0.789012, 0.345678]
        ]

        for embedding in test_embeddings:
            encrypted = self.encryption.encrypt_embedding(embedding)
            decrypted = self.encryption.decrypt_embedding(encrypted)
            assert decrypted == embedding

    def test_encrypt_contestant_data(self):
        """Test contestant data encryption."""
        data = {"name": "John Doe", "id": 123, "metadata": {"age": 25}}
        encrypted = self.encryption.encrypt_contestant_data(data)

        assert isinstance(encrypted, str)
        assert len(encrypted) > 0

    def test_decrypt_contestant_data(self):
        """Test contestant data decryption."""
        original_data = {"name": "Jane Smith", "id": 456, "scores": [95, 87, 92]}
        encrypted = self.encryption.encrypt_contestant_data(original_data)
        decrypted = self.encryption.decrypt_contestant_data(encrypted)

        assert decrypted == original_data

    def test_invalid_embedding_encryption(self):
        """Test encryption rejects invalid embeddings."""
        with pytest.raises(ValueError):
            self.encryption.encrypt_embedding("not a list")

        with pytest.raises(ValueError):
            self.encryption.encrypt_embedding([1, 2, "three"])

    def test_invalid_data_decryption(self):
        """Test decryption rejects invalid data."""
        with pytest.raises(ValueError):
            self.encryption.decrypt_embedding("invalid encrypted data")

        with pytest.raises(ValueError):
            self.encryption.decrypt_embedding("")

    def test_different_instances_isolation(self):
        """Test that different encryption instances produce different results."""
        embedding = [0.5, 0.5, 0.5]

        enc1 = FaceDataEncryption()
        enc2 = FaceDataEncryption()

        encrypted1 = enc1.encrypt_embedding(embedding)
        encrypted2 = enc2.encrypt_embedding(embedding)

        # Different keys should produce different encrypted data
        assert encrypted1 != encrypted2

        # But each should decrypt correctly with its own key
        assert enc1.decrypt_embedding(encrypted1) == embedding
        assert enc2.decrypt_embedding(encrypted2) == embedding

    def test_backup_and_restore(self):
        """Test backup and restore functionality."""
        original_data = {"test": "data", "numbers": [1, 2, 3]}

        # Encrypt with original instance
        encrypted = self.encryption.encrypt_contestant_data(original_data)

        # Create new instance from backup
        master_key = self.encryption.get_master_key()
        salt = self.encryption.get_salt()
        restored_encryption = FaceDataEncryption.from_backup(master_key, salt)

        # Should be able to decrypt with restored instance
        decrypted = restored_encryption.decrypt_contestant_data(encrypted)
        assert decrypted == original_data