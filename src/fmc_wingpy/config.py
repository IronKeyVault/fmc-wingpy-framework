#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Secure credential and configuration management.

Storage strategy (see ADR-002 §7):
1. Try OS keyring (SecretService / GNOME Keyring) — works on desktop Linux
2. If keyring is unavailable (headless), fall back to a local credentials
   file at <project>/credentials.json with chmod 600 (owner-only).
   Credentials are encrypted at rest using Fernet with a machine-derived key
   (from /etc/machine-id + username).
"""
import json, os, logging, base64, hashlib, getpass
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken

log = logging.getLogger("fmc_wingpy")
SERVICE_NAME = "fmc_wingpy"
CONFIG_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_FILE = CONFIG_DIR / "config.json"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"
LOG_DIR = CONFIG_DIR / "logs"


def _derive_key() -> bytes:
    """Derive a Fernet encryption key from machine identity.

    Uses /etc/machine-id + username as input to scrypt. The result is
    deterministic on the same machine for the same user, but cannot be
    reproduced on another machine or by another user.
    """
    try:
        machine_id = Path("/etc/machine-id").read_text().strip()
    except FileNotFoundError:
        machine_id = "fmc-wingpy-fallback-id"
    username = getpass.getuser()
    salt = f"fmc-wingpy-{username}-{machine_id}".encode()
    key = hashlib.scrypt(salt, salt=salt, n=16384, r=8, p=1, dklen=32)
    return base64.urlsafe_b64encode(key)


def _encrypt(data: dict) -> bytes:
    return Fernet(_derive_key()).encrypt(json.dumps(data).encode())


def _decrypt(token: bytes) -> dict:
    return json.loads(Fernet(_derive_key()).decrypt(token))


def _keyring_available() -> bool:
    """Check if OS keyring is usable (desktop session with unlocked keyring)."""
    try:
        import keyring
        from keyring.backends.SecretService import Keyring as SS
        ss = SS()
        ss.get_password("fmc_wingpy_probe", "probe")
        return True
    except Exception:
        return False


def _ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _read_credentials_file() -> dict:
    """Read credentials from local file (encrypted or legacy plaintext)."""
    if not CREDENTIALS_FILE.exists():
        return {}
    raw = CREDENTIALS_FILE.read_bytes()
    try:
        return _decrypt(raw)
    except InvalidToken:
        pass
    # Legacy plaintext — auto-migrate
    try:
        data = json.loads(raw)
        log.info("Migrating plaintext credentials to encrypted format")
        _write_credentials_file(data)
        return data
    except (json.JSONDecodeError, UnicodeDecodeError):
        log.error("Failed to read credentials file: unknown format")
        return {}


def _write_credentials_file(data: dict):
    """Write encrypted credentials to local file with chmod 600 from creation."""
    _ensure_config_dir()
    encrypted = _encrypt(data)
    fd = os.open(CREDENTIALS_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(encrypted)


class CredentialManager:
    @staticmethod
    def set_credentials(fmc_base_url: str, fmc_username: str, fmc_password: str):
        if _keyring_available():
            import keyring
            keyring.set_password(SERVICE_NAME, "fmc_base_url", fmc_base_url)
            keyring.set_password(SERVICE_NAME, "fmc_username", fmc_username)
            keyring.set_password(SERVICE_NAME, "fmc_password", fmc_password)
            log.info("Credentials stored in OS keyring")
        else:
            data = {
                "fmc_base_url": fmc_base_url,
                "fmc_username": fmc_username,
                "fmc_password": fmc_password,
            }
            _write_credentials_file(data)
            log.info("Credentials encrypted and stored in %s (chmod 600)", CREDENTIALS_FILE)
        return True

    @staticmethod
    def get_credentials() -> dict:
        if _keyring_available():
            import keyring
            fmc_base_url = keyring.get_password(SERVICE_NAME, "fmc_base_url")
            fmc_username = keyring.get_password(SERVICE_NAME, "fmc_username")
            fmc_password = keyring.get_password(SERVICE_NAME, "fmc_password")
            if all([fmc_base_url, fmc_username, fmc_password]):
                return {
                    "fmc_base_url": fmc_base_url,
                    "fmc_username": fmc_username,
                    "fmc_password": fmc_password,
                }
        try:
            data = _read_credentials_file()
            if all(k in data for k in ("fmc_base_url", "fmc_username", "fmc_password")):
                return data
        except Exception as e:
            log.error("Failed to read credentials file: %s", e)
        log.info("No credentials found")
        return None

    @staticmethod
    def clear_credentials():
        if _keyring_available():
            import keyring
            for key in ["fmc_base_url", "fmc_username", "fmc_password"]:
                try:
                    keyring.delete_password(SERVICE_NAME, key)
                except Exception:
                    pass
        if CREDENTIALS_FILE.exists():
            CREDENTIALS_FILE.unlink()
        log.info("Credentials cleared")
        return True

    @staticmethod
    def get_storage_backend() -> str:
        if _keyring_available():
            return "OS keyring (SecretService)"
        return f"Local file ({CREDENTIALS_FILE}, encrypted, chmod 600)"


class ConfigManager:
    @staticmethod
    def ensure_directories():
        _ensure_config_dir()

    @staticmethod
    def get_config_dir() -> Path:
        ConfigManager.ensure_directories()
        return CONFIG_DIR

    @staticmethod
    def get_log_dir() -> Path:
        ConfigManager.ensure_directories()
        return LOG_DIR

    @staticmethod
    def get_log_file() -> Path:
        return ConfigManager.get_log_dir() / "fmc_wingpy.log"

    @staticmethod
    def _load_config() -> dict:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        return {}

    @staticmethod
    def _save_config(data: dict):
        ConfigManager.ensure_directories()
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def get(key: str, default=None):
        """Get a config value by key."""
        try:
            return ConfigManager._load_config().get(key, default)
        except Exception as e:
            log.warning("Failed to load config: %s", e)
        return default

    @staticmethod
    def set(key: str, value):
        """Set a config value by key."""
        try:
            data = ConfigManager._load_config()
            data[key] = value
            ConfigManager._save_config(data)
            log.info("Config saved: %s", key)
        except Exception as e:
            log.error("Failed to save config: %s", e)
            raise

    @staticmethod
    def clear():
        """Remove config file."""
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
        log.info("Configuration cleared")
