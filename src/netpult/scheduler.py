"""Фоновый планировщик: включает и выключает интернет по расписанию.

Работает, пока приложение запущено (в том числе в фоне, пока Android не выгрузит
процесс). Каждые 20 секунд проверяет правила и меняет доступ только у тех
устройств, чьё состояние действительно пора изменить.
"""
from __future__ import annotations

import asyncio
import datetime
from typing import Callable, Awaitable

from .adapters import build_adapter
from .storage import Store, rule_key, should_block


class Scheduler:
    def __init__(self, store: Store, on_change: Callable[[], Awaitable[None]] | None = None) -> None:
        self._store = store
        self._on_change = on_change
        self._profiles: dict[str, dict] = {}
        self._applied: dict[str, bool] = {}
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def set_profiles(self, profiles: list[dict]) -> None:
        self._profiles = {str(p.get("host", "")).strip().lower(): p for p in profiles}

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            try:
                await self._task
            except Exception:  # noqa: BLE001
                pass

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self._tick()
            except Exception:  # noqa: BLE001
                pass
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=20)
            except asyncio.TimeoutError:
                pass

    async def _tick(self) -> None:
        rules = await self._store.rules()
        if not rules:
            return
        now = datetime.datetime.now()
        minutes = now.hour * 60 + now.minute
        changed = False
        for key, rule in rules.items():
            want_block = should_block(rule, minutes)
            if want_block is None:
                continue
            if self._applied.get(key) == want_block:
                continue
            host, _, mac = key.partition("|")
            profile = self._profiles.get(host)
            if not profile or not mac:
                continue
            try:
                await asyncio.to_thread(_apply, profile, mac, not want_block)
            except Exception:  # noqa: BLE001
                continue
            self._applied[key] = want_block
            changed = True
        if changed and self._on_change:
            try:
                await self._on_change()
            except Exception:  # noqa: BLE001
                pass


def _apply(profile: dict, mac: str, allow: bool) -> None:
    build_adapter(profile).set_access(mac, allow)
