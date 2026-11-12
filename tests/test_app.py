import os
import tempfile

os.environ.update(
    API_ID="12345",
    API_HASH="abcdef",
    PANEL_PASSWORD="panel-pass",
    DATA_DIR=tempfile.mkdtemp(),
)
os.environ.pop("SESSION_STRING", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.rules import RuleError, RuleStore  # noqa: E402
from app.telegram_manager import ManagerError, normalize_phone  # noqa: E402


def make_store(tmp_path):
    return RuleStore(tmp_path / "rules.json")


def test_exact_match_ignores_case_and_spaces(tmp_path):
    s = make_store(tmp_path)
    s.add("ads", "Reklam için DM")
    assert s.match("ads") == "Reklam için DM"
    assert s.match("  ADS ") == "Reklam için DM"
    assert s.match("ads please") is None
    assert s.match("") is None


def test_disabled_rule_does_not_match(tmp_path):
    s = make_store(tmp_path)
    r = s.add("done", "Tamamlandı ✅")
    s.update(r.id, "done", "Tamamlandı ✅", False)
    assert s.match("done") is None


def test_duplicate_trigger_rejected(tmp_path):
    s = make_store(tmp_path)
    s.add("ads", "a")
    with pytest.raises(RuleError) as e:
        s.add("ADS", "b")
    assert e.value.status == 409


def test_rules_persist(tmp_path):
    s = make_store(tmp_path)
    s.add("done", "bitti")
    assert make_store(tmp_path).match("done") == "bitti"


def test_phone_normalization():
    assert normalize_phone("905315151419") == "+905315151419"
    assert normalize_phone("+90 531 515 14 19") == "+905315151419"
    with pytest.raises(ManagerError):
        normalize_phone("12")


def test_api_requires_login_and_rules_crud():
    c = TestClient(app)
    assert c.get("/api/status").status_code == 401
    assert c.get("/api/rules").status_code == 401
    assert c.get("/health").json()["ok"] is True

    assert c.post("/api/panel/login", json={"password": "wrong"}).status_code == 401
    assert c.post("/api/panel/login", json={"password": "panel-pass"}).status_code == 200

    assert c.get("/api/status").json()["state"] == "logged_out"
    r = c.post("/api/rules", json={"trigger": "ads", "replacement": "Yeni metin"})
    assert r.status_code == 201
    rid = r.json()["id"]
    assert c.post("/api/rules", json={"trigger": "Ads", "replacement": "x"}).status_code == 409
    assert c.put(f"/api/rules/{rid}", json={"trigger": "ads", "replacement": "Başka", "enabled": True}).json()["replacement"] == "Başka"
    assert c.get("/api/rules/export").status_code == 200
    assert c.delete(f"/api/rules/{rid}").status_code == 200
    assert c.get("/api/rules").json() == []
    assert c.post("/api/tg/verify-code", json={"code": "12345"}).status_code == 409
    assert c.get("/api/session").status_code == 409
    assert "Telegram Panel" in c.get("/").text


class FakeMsg:
    def __init__(self, text):
        self.message = text


class FakeEvent:
    def __init__(self, text):
        self.raw_text = text
        self.message = FakeMsg(text)
        self.edited = None

    async def edit(self, text):
        self.edited = text


def test_outgoing_message_is_edited(tmp_path):
    import asyncio
    from app.config import load_settings
    from app.telegram_manager import TelegramManager

    store = make_store(tmp_path)
    store.add("ads", "Reklam metni")
    store.add("done", "İş tamam")
    m = TelegramManager(load_settings(), store)
    for text, want in [("ads", "Reklam metni"), ("Done", "İş tamam"), ("merhaba", None)]:
        ev = FakeEvent(text)
        asyncio.run(m._on_outgoing(ev))
        assert ev.edited == want
    assert m.edit_count == 2
