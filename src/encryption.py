"""
Encryption utilities for face recognition system.
Provides secure encryption/decryption of biometric data and sensitive information.
"""

import os
import base64
import json
from typing import List, Optional, Dict, Any
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class FaceDataEncryption:
    """
    Handles encryption/decryption of face embeddings and sensitive biometric data.
    Uses AES-256 encryption with PBKDF2 key derivation for maximum security.
    """

    def __init__(self, master_key: Optional[str] = None, salt: Optional[bytes] = None):
        """
        Initialize encryption handler.

        Args:
            master_key: Base64 encoded master key (generated if None)
            salt: Salt for key derivation (random if None)
        """
        self.salt = salt or os.urandom(16)
        self.master_key = master_key or base64.urlsafe_b64encode(os.urandom(32)).decode()

        # Derive encryption key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.master_key.encode()))
        self.cipher = Fernet(key)

    def encrypt_embedding(self, embedding: List[float]) -> str:
        """
        Encrypt face embedding vector.

        Args:
            embedding: List of float values representing face embedding

        Returns:
            Base64 encoded encrypted data
        """
        if not isinstance(embedding, list) or not all(isinstance(x, (int, float)) for x in embedding):
            raise ValueError("Embedding must be a list of numbers")

        # Convert to JSON string for encryption
        data = json.dumps(embedding, separators=(',', ':'))
        encrypted = self.cipher.encrypt(data.encode('utf-8'))
        return base64.urlsafe_b64encode(encrypted).decode('utf-8')

    def decrypt_embedding(self, encrypted_data: str) -> List[float]:
        """
        Decrypt face embedding vector.

        Args:
            encrypted_data: Base64 encoded encrypted embedding

        Returns:
            Original embedding as list of floats

        Raises:
            ValueError: If decryption fails or data is corrupted
        """
        try:
            # Decode and decrypt
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            decrypted_data = self.cipher.decrypt(encrypted_bytes).decode('utf-8')

            # Parse JSON
            embedding = json.loads(decrypted_data)

            if not isinstance(embedding, list) or not all(isinstance(x, (int, float)) for x in embedding):
                raise ValueError("Decrypted data is not a valid embedding")

            return [float(x) for x in embedding]

        except (InvalidToken, json.JSONDecodeError, ValueError, UnicodeDecodeError) as e:
            raise ValueError(f"Failed to decrypt embedding: {str(e)}")

    def encrypt_contestant_data(self, data: Dict[str, Any]) -> str:
        """
        Encrypt sensitive contestant information.

        Args:
            data: Dictionary containing contestant data

        Returns:
            Base64 encoded encrypted data
        """
        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")

        # Convert to JSON
        json_data = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        encrypted = self.cipher.encrypt(json_data.encode('utf-8'))
        return base64.urlsafe_b64encode(encrypted).decode('utf-8')

    def decrypt_contestant_data(self, encrypted_data: str) -> Dict[str, Any]:
        """
        Decrypt contestant data.

        Args:
            encrypted_data: Base64 encoded encrypted data

        Returns:
            Original data dictionary
        """
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            decrypted_data = self.cipher.decrypt(encrypted_bytes).decode('utf-8')
            data = json.loads(decrypted_data)

            if not isinstance(data, dict):
                raise ValueError("Decrypted data is not a valid dictionary")

            return data

        except (InvalidToken, json.JSONDecodeError, ValueError, UnicodeDecodeError) as e:
            raise ValueError(f"Failed to decrypt contestant data: {str(e)}")

    def get_master_key(self) -> str:
        """Get the master key for backup/storage."""
        return self.master_key

    def get_salt(self) -> str:
        """Get the salt for backup/storage."""
        return base64.urlsafe_b64encode(self.salt).decode('utf-8')

    @classmethod
    def from_backup(cls, master_key: str, salt: str) -> 'FaceDataEncryption':
        """Create instance from backed up key and salt."""
        salt_bytes = base64.urlsafe_b64decode(salt.encode('utf-8'))
        return cls(master_key=master_key, salt=salt_bytes)