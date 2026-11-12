"""Ortam değişkenlerinden ayarları okur."""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    panel_password: str
    secret_key: str
    default_phone: str
    session_string: str
    data_dir: Path
    cookie_secure: bool

    @property
    def rules_file(self) -> Path:
        return self.data_dir / "rules.json"

    @property
    def session_file(self) -> Path:
        return self.data_dir / "session.txt"


# Senin bilgilerin (Render'da ayar girmene gerek yok)
DEFAULTS = {
    "API_ID": "16896485",
    "API_HASH": "29b5bb9351b4cb3738d73abaf5eb28ca",
    "PHONE": "905315151419",
    "PANEL_PASSWORD": "DuhanPanel2026",
}
for _k, _v in DEFAULTS.items():
    if not os.getenv(_k, "").strip():
        os.environ[_k] = _v


def load_settings() -> Settings:
    missing = [k for k in ("API_ID", "API_HASH", "PANEL_PASSWORD") if not os.getenv(k, "").strip()]
    if missing:
        raise ConfigError("Eksik ortam değişkenleri: " + ", ".join(missing))

    try:
        api_id = int(os.environ["API_ID"].strip())
    except ValueError as exc:
        raise ConfigError("API_ID sayı olmalı (örn. 16896485)") from exc

    panel_password = os.environ["PANEL_PASSWORD"].strip()
    secret_key = os.getenv("SECRET_KEY", "").strip()
    if not secret_key:
        # SECRET_KEY verilmediyse paneldeki şifreden türet (yeniden başlatmada sabit kalır)
        secret_key = hashlib.sha256(("panel:" + panel_password).encode()).hexdigest()

    data_dir = Path(os.getenv("DATA_DIR", "./data")).expanduser()
    data_dir.mkdir(parents=True, exist_ok=True)

    secure_env = os.getenv("COOKIE_SECURE")
    cookie_secure = (secure_env == "1") if secure_env is not None else bool(os.getenv("RENDER"))

    return Settings(
        api_id=api_id,
        api_hash=os.environ["API_HASH"].strip(),
        panel_password=panel_password,
        secret_key=secret_key,
        default_phone=os.getenv("PHONE", "").strip(),
        session_string=os.getenv("SESSION_STRING", "").strip(),
        data_dir=data_dir,
        cookie_secure=cookie_secure,
    )
