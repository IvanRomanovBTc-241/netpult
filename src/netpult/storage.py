"""Хранение профилей роутеров и правил расписания (SharedPreferences)."""
from __future__ import annotations

import json

PROFILES_KEY = "profiles_v2"
RULES_KEY = "rules_v2"


class Store:
    def __init__(self, prefs) -> None:
        self._prefs = prefs

    async def profiles(self) -> list[dict]:
        raw = await self._prefs.get(PROFILES_KEY)
        try:
            data = json.loads(raw) if raw else []
        except Exception:  # noqa: BLE001
            data = []
        return data if isinstance(data, list) else []

    async def save_profiles(self, items: list[dict]) -> None:
        await self._prefs.set(PROFILES_KEY, json.dumps(items, ensure_ascii=False))

    async def rules(self) -> dict[str, dict]:
        raw = await self._prefs.get(RULES_KEY)
        try:
            data = json.loads(raw) if raw else {}
        except Exception:  # noqa: BLE001
            data = {}
        return data if isinstance(data, dict) else {}

    async def save_rules(self, rules: dict[str, dict]) -> None:
        await self._prefs.set(RULES_KEY, json.dumps(rules, ensure_ascii=False))


def rule_key(host: str, mac: str) -> str:
    return f"{host.strip().lower()}|{mac.strip().lower()}"


def parse_hhmm(value: str) -> int | None:
    """'00:30' -> 30 минут от полуночи."""
    try:
        hh, mm = value.strip().split(":")
        hour, minute = int(hh), int(mm)
    except Exception:  # noqa: BLE001
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour * 60 + minute


def should_block(rule: dict, minutes_now: int) -> bool | None:
    """True — блокировать, False — разрешить, None — правило неактивно."""
    if not rule.get("enabled"):
        return None
    off = parse_hhmm(str(rule.get("off", "")))
    on = parse_hhmm(str(rule.get("on", "")))
    if off is None or on is None or off == on:
        return None
    if off < on:
        return off <= minutes_now < on
    return minutes_now >= off or minutes_now < on


def describe(rule: dict) -> str:
    if not rule.get("enabled"):
        return ""
    return f"расписание: {rule.get('off', '?')}–{rule.get('on', '?')}"
