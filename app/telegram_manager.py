"""Telegram hesabına giriş (kod / 2 adımlı şifre) ve mesaj düzenleme."""
from __future__ import annotations

import asyncio
import logging
import re
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from telethon import TelegramClient, events
from telethon.errors import (
    ApiIdInvalidError,
    FloodWaitError,
    MessageNotModifiedError,
    PasswordHashInvalidError,
    PhoneCodeEmptyError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberBannedError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)
from telethon.sessions import StringSession

from .config import Settings
from .rules import RuleStore

log = logging.getLogger("tgpanel")

LOGGED_OUT = "logged_out"
AWAITING_CODE = "awaiting_code"
AWAITING_PASSWORD = "awaiting_password"
LOGGED_IN = "logged_in"


class ManagerError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) < 7 or len(digits) > 15:
        raise ManagerError("Telefon numarası geçersiz. Örnek: +905315151419")
    return "+" + digits


class TelegramManager:
    def __init__(self, settings: Settings, rules: RuleStore):
        self.settings = settings
        self.rules = rules
        self.client: Optional[TelegramClient] = None
        self.state = LOGGED_OUT
        self.phone: Optional[str] = None
        self.phone_code_hash: Optional[str] = None
        self.me: Optional[dict] = None
        self.edit_count = 0
        self.logs: deque[dict] = deque(maxlen=100)
        self._lock = asyncio.Lock()

    # ---- yardımcılar ----------------------------------------------
    def add_log(self, kind: str, text: str) -> None:
        self.logs.appendleft(
            {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), "kind": kind, "text": text}
        )
        log.info("[%s] %s", kind, text)

    def _new_client(self, session: str = "") -> TelegramClient:
        client = TelegramClient(
            StringSession(session),
            self.settings.api_id,
            self.settings.api_hash,
            device_model="Telegram Panel",
            system_version="Server",
            app_version="1.0",
        )
        client.parse_mode = None  # metin düz gönderilsin, * _ gibi karakterler bozulmasın
        client.add_event_handler(self._on_outgoing, events.NewMessage(outgoing=True))
        return client

    async def _drop_client(self) -> None:
        client, self.client = self.client, None
        if client is not None:
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001
                pass

    def _reset_login(self) -> None:
        self.state = LOGGED_OUT
        self.phone_code_hash = None
        self.me = None

    def _save_session(self) -> None:
        assert self.client is not None
        value = self.client.session.save()
        try:
            self.settings.session_file.write_text(value, "utf-8")
        except OSError as exc:
            self.add_log("warn", f"Oturum dosyaya yazılamadı: {exc}")

    def session_string(self) -> Optional[str]:
        if self.state != LOGGED_IN or self.client is None:
            return None
        return self.client.session.save()

    # ---- yaşam döngüsü --------------------------------------------
    async def start(self) -> None:
        session = self.settings.session_string
        if not session and self.settings.session_file.exists():
            try:
                session = self.settings.session_file.read_text("utf-8").strip()
            except OSError:
                session = ""
        if not session:
            self.add_log("info", "Kayıtlı oturum yok, panelden giriş yapın")
            return
        client = self._new_client(session)
        try:
            await client.connect()
            if await client.is_user_authorized():
                self.client = client
                await self._after_login()
                self.add_log("info", "Kayıtlı oturumla otomatik giriş yapıldı")
                return
            self.add_log("warn", "Kayıtlı oturum geçersiz, yeniden giriş yapın")
        except Exception as exc:  # noqa: BLE001
            self.add_log("error", f"Otomatik giriş başarısız: {exc}")
        try:
            await client.disconnect()
        except Exception:  # noqa: BLE001
            pass

    async def stop(self) -> None:
        await self._drop_client()

    async def _after_login(self) -> None:
        assert self.client is not None
        me = await self.client.get_me()
        self.me = {
            "id": me.id,
            "name": " ".join(filter(None, [me.first_name, me.last_name])) or "—",
            "username": me.username,
            "phone": ("+" + me.phone) if me.phone else None,
        }
        self.state = LOGGED_IN
        self.phone_code_hash = None
        self._save_session()

    # ---- giriş akışı ----------------------------------------------
    async def send_code(self, phone: str) -> None:
        phone = normalize_phone(phone)
        async with self._lock:
            if self.state == LOGGED_IN:
                raise ManagerError("Zaten giriş yapılmış", 409)
            await self._drop_client()
            self._reset_login()
            client = self._new_client()
            try:
                await client.connect()
                sent = await client.send_code_request(phone)
            except PhoneNumberInvalidError:
                await self._safe_disconnect(client)
                raise ManagerError("Telefon numarası geçersiz")
            except PhoneNumberBannedError:
                await self._safe_disconnect(client)
                raise ManagerError("Bu numara Telegram tarafından engellenmiş")
            except ApiIdInvalidError:
                await self._safe_disconnect(client)
                raise ManagerError("API_ID / API_HASH hatalı. my.telegram.org'dan kontrol edin", 500)
            except FloodWaitError as exc:
                await self._safe_disconnect(client)
                raise ManagerError(f"Çok fazla deneme. {exc.seconds} saniye sonra tekrar deneyin", 429)
            except Exception as exc:  # noqa: BLE001
                await self._safe_disconnect(client)
                raise ManagerError(f"Kod gönderilemedi: {exc}", 502)
            self.client = client
            self.phone = phone
            self.phone_code_hash = sent.phone_code_hash
            self.state = AWAITING_CODE
            self.add_log("info", f"{phone} numarasına kod gönderildi")

    async def verify_code(self, code: str) -> None:
        code = re.sub(r"\D", "", code or "")
        if not code:
            raise ManagerError("Kodu girin")
        async with self._lock:
            if self.state != AWAITING_CODE or self.client is None or not self.phone:
                raise ManagerError("Önce kod isteyin", 409)
            try:
                await self.client.sign_in(phone=self.phone, code=code, phone_code_hash=self.phone_code_hash)
            except SessionPasswordNeededError:
                self.state = AWAITING_PASSWORD
                self.add_log("info", "İki adımlı doğrulama şifresi gerekiyor")
                return
            except (PhoneCodeInvalidError, PhoneCodeEmptyError):
                raise ManagerError("Kod hatalı")
            except PhoneCodeExpiredError:
                await self._drop_client()
                self._reset_login()
                raise ManagerError("Kodun süresi dolmuş. Yeni kod isteyin", 410)
            except FloodWaitError as exc:
                raise ManagerError(f"Çok fazla deneme. {exc.seconds} saniye bekleyin", 429)
            except Exception as exc:  # noqa: BLE001
                raise ManagerError(f"Giriş başarısız: {exc}", 502)
            await self._after_login()
            self.add_log("info", f"Giriş yapıldı: {self.me['name']}")

    async def verify_password(self, password: str) -> None:
        if not password:
            raise ManagerError("Şifreyi girin")
        async with self._lock:
            if self.state != AWAITING_PASSWORD or self.client is None:
                raise ManagerError("Şu an şifre istenmiyor", 409)
            try:
                await self.client.sign_in(password=password)
            except PasswordHashInvalidError:
                raise ManagerError("Şifre hatalı")
            except FloodWaitError as exc:
                raise ManagerError(f"Çok fazla deneme. {exc.seconds} saniye bekleyin", 429)
            except Exception as exc:  # noqa: BLE001
                raise ManagerError(f"Giriş başarısız: {exc}", 502)
            await self._after_login()
            self.add_log("info", f"Giriş yapıldı: {self.me['name']}")

    async def cancel_login(self) -> None:
        async with self._lock:
            if self.state in (AWAITING_CODE, AWAITING_PASSWORD):
                await self._drop_client()
                self._reset_login()

    async def logout(self) -> None:
        async with self._lock:
            if self.client is not None and self.state == LOGGED_IN:
                try:
                    await self.client.log_out()
                except Exception as exc:  # noqa: BLE001
                    self.add_log("warn", f"Telegram'dan çıkış sırasında hata: {exc}")
            await self._drop_client()
            self._reset_login()
            try:
                self.settings.session_file.unlink(missing_ok=True)
            except OSError:
                pass
            self.add_log("info", "Hesaptan çıkış yapıldı")

    @staticmethod
    async def _safe_disconnect(client: TelegramClient) -> None:
        try:
            await client.disconnect()
        except Exception:  # noqa: BLE001
            pass

    # ---- mesaj düzenleme ------------------------------------------
    async def _on_outgoing(self, event: events.NewMessage.Event) -> None:
        text = event.raw_text
        if not text:
            return
        new_text = self.rules.match(text)
        if new_text is None or new_text == event.message.message:
            return
        await asyncio.sleep(2)
        try:
            await event.edit(new_text, link_preview=True)
        except MessageNotModifiedError:
            return
        except FloodWaitError as exc:
            self.add_log("error", f"Telegram sınırı: {exc.seconds} sn beklenmeli")
            return
        except Exception as exc:  # noqa: BLE001
            self.add_log("error", f"Düzenlenemedi ({text[:30]!r}): {exc}")
            return
        self.edit_count += 1
        self.add_log("edit", f"{text.strip()[:40]} → {new_text[:60]}")

    # ---- durum ----------------------------------------------------
    def status(self) -> dict:
        return {
            "state": self.state,
            "phone": self.phone,
            "me": self.me,
            "edit_count": self.edit_count,
            "default_phone": self.settings.default_phone,
        }
