import os, json, base64
from typing import Dict, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from config.constants import CREDENTIALS_FILE, SALT_FILE
from config.settings import DEFAULT_KEY_DERIVATION_PASSWORD

class CredentialManager:
    def __init__(self):
        self.key = self._get_or_create_key()
        self.fernet = Fernet(self.key)
        self.credentials = self._load_credentials()

    def _get_or_create_key(self) -> bytes:
        if not os.path.exists(SALT_FILE):
            with open(SALT_FILE, 'wb') as f:
                f.write(os.urandom(16))
        with open(SALT_FILE, 'rb') as f:
            salt = f.read()
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
        return base64.urlsafe_b64encode(kdf.derive(DEFAULT_KEY_DERIVATION_PASSWORD))

    def _load_credentials(self) -> Dict[str, Dict[str, str]]:
        if not os.path.exists(CREDENTIALS_FILE): return {}
        try:
            with open(CREDENTIALS_FILE, 'rb') as f:
                decrypted = self.fernet.decrypt(f.read())
                return json.loads(decrypted)
        except Exception:
            return {}

    def save_credentials(self) -> None:
        encrypted = self.fernet.encrypt(json.dumps(self.credentials).encode())
        with open(CREDENTIALS_FILE, 'wb') as f:
            f.write(encrypted)

    def add_credentials(self, url: str, username: str, password: str) -> None:
        self.credentials[url] = {"username": username, "password": password}
        self.save_credentials()

    def get_credentials(self, url: str) -> Optional[Dict[str, str]]:
        return self.credentials.get(url)
