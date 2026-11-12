"""Metin değiştirme kuralları (ads -> ..., done -> ...)."""
from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

MAX_LEN = 4096  # Telegram mesaj sınırı


class RuleError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def normalize(text: str) -> str:
    """Boşlukları sadeleştirir, büyük/küçük harf farkını kaldırır."""
    return " ".join(text.split()).casefold()


@dataclass
class Rule:
    id: str
    trigger: str
    replacement: str
    enabled: bool = True


class RuleStore:
    def __init__(self, path: Path, seed_json: str = ""):
        self.path = path
        self._lock = threading.Lock()
        self._rules: list[Rule] = []
        self._load(seed_json)

    # ---- kalıcılık -------------------------------------------------
    def _load(self, seed_json: str) -> None:
        raw: object = None
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text("utf-8"))
            except (OSError, json.JSONDecodeError):
                raw = None
        elif seed_json.strip():
            try:
                raw = json.loads(seed_json)
            except json.JSONDecodeError:
                raw = None
        if isinstance(raw, list):
            for item in raw:
                try:
                    trigger = str(item["trigger"]).strip()
                    replacement = str(item["replacement"])
                    if not trigger or not replacement.strip():
                        continue
                    self._rules.append(
                        Rule(
                            id=str(item.get("id") or uuid.uuid4().hex[:10]),
                            trigger=trigger,
                            replacement=replacement,
                            enabled=bool(item.get("enabled", True)),
                        )
                    )
                except (KeyError, TypeError):
                    continue
            self._save()

    def _save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps([asdict(r) for r in self._rules], ensure_ascii=False, indent=2), "utf-8")
        os.replace(tmp, self.path)

    # ---- doğrulama -------------------------------------------------
    @staticmethod
    def _clean(trigger: str, replacement: str) -> tuple[str, str]:
        trigger = trigger.strip()
        if not trigger:
            raise RuleError("Tetikleyici metin boş olamaz")
        if not replacement.strip():
            raise RuleError("Yeni metin boş olamaz")
        if len(trigger) > MAX_LEN or len(replacement) > MAX_LEN:
            raise RuleError(f"Metin en fazla {MAX_LEN} karakter olabilir")
        return trigger, replacement

    def _find_dupe(self, trigger: str, ignore_id: Optional[str] = None) -> bool:
        key = normalize(trigger)
        return any(r.id != ignore_id and normalize(r.trigger) == key for r in self._rules)

    # ---- CRUD ------------------------------------------------------
    def list(self) -> list[Rule]:
        with self._lock:
            return [Rule(**asdict(r)) for r in self._rules]

    def add(self, trigger: str, replacement: str, enabled: bool = True) -> Rule:
        trigger, replacement = self._clean(trigger, replacement)
        with self._lock:
            if self._find_dupe(trigger):
                raise RuleError("Bu tetikleyici için zaten bir kural var", 409)
            rule = Rule(uuid.uuid4().hex[:10], trigger, replacement, enabled)
            self._rules.append(rule)
            self._save()
            return rule

    def update(self, rule_id: str, trigger: str, replacement: str, enabled: bool) -> Rule:
        trigger, replacement = self._clean(trigger, replacement)
        with self._lock:
            for rule in self._rules:
                if rule.id == rule_id:
                    if self._find_dupe(trigger, ignore_id=rule_id):
                        raise RuleError("Bu tetikleyici için zaten bir kural var", 409)
                    rule.trigger, rule.replacement, rule.enabled = trigger, replacement, enabled
                    self._save()
                    return Rule(**asdict(rule))
        raise RuleError("Kural bulunamadı", 404)

    def delete(self, rule_id: str) -> None:
        with self._lock:
            before = len(self._rules)
            self._rules = [r for r in self._rules if r.id != rule_id]
            if len(self._rules) == before:
                raise RuleError("Kural bulunamadı", 404)
            self._save()

    def export_json(self) -> str:
        with self._lock:
            return json.dumps([asdict(r) for r in self._rules], ensure_ascii=False)

    # ---- eşleştirme ------------------------------------------------
    def match(self, text: str) -> Optional[str]:
        """Mesaj tam olarak bir tetikleyiciyse yeni metni döndürür."""
        key = normalize(text)
        if not key:
            return None
        with self._lock:
            for rule in self._rules:
                if rule.enabled and normalize(rule.trigger) == key:
                    return rule.replacement
        return None
