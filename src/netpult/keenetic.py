"""Синхронный клиент Keenetic CLI (telnet) для мобильного приложения.

Проверено на Keenetic Air (KN-1610), KeeneticOS 3.8.5:
    ip hotspot host <mac> deny    — запретить доступ к сети
    ip hotspot host <mac> permit  — вернуть доступ
"""
from __future__ import annotations

import re
import socket
import time
from dataclasses import dataclass

ANSI_RE = re.compile(rb"\x1b\[[0-9;]*[A-Za-z]")
PROMPT = b"(config)>"


@dataclass
class Device:
    mac: str
    ip: str = ""
    hostname: str = ""
    ssid: str = ""
    active: bool = False
    rssi: int | None = None
    txrate: int | None = None
    blocked: bool = False

    @property
    def label(self) -> str:
        return self.hostname or self.mac


class KeeneticError(RuntimeError):
    pass


class Keenetic:
    def __init__(self, host: str, login: str, password: str, port: int = 23, timeout: float = 8.0):
        self.host = host
        self.login = login
        self.password = password
        self.port = port
        self.timeout = timeout
        self._sock: socket.socket | None = None

    def __enter__(self) -> "Keenetic":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- соединение ---

    def connect(self) -> None:
        self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self._sock.settimeout(self.timeout)
        self._read_until(b"Login:")
        self._send(self.login)
        self._read_until(b"Password:")
        self._send(self.password)
        self._read_until(PROMPT)

    def close(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def _send(self, line: str) -> None:
        assert self._sock
        self._sock.sendall(line.encode() + b"\r\n")

    def _read_until(self, marker: bytes) -> str:
        assert self._sock
        buf = b""
        deadline = time.time() + self.timeout
        while marker not in buf and time.time() < deadline:
            try:
                chunk = self._sock.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            buf += chunk
            if buf.endswith(b"(config)> ") and marker == PROMPT:
                break
        return _clean(buf)

    def command(self, line: str) -> str:
        self._send(line)
        out = self._read_until(PROMPT)
        lowered = out.lower()
        if "error[" in lowered or "no such command" in lowered:
            raise KeeneticError(out.strip()[-300:])
        return out

    # --- действия ---

    def devices(self) -> list[Device]:
        return parse_hotspot(self.command("show ip hotspot"))

    def set_access(self, mac: str, allow: bool, save: bool = True) -> None:
        action = "permit" if allow else "deny"
        self.command(f"ip hotspot host {mac.lower()} {action}")
        if save:
            self.command("system configuration save")


def _clean(data: bytes) -> str:
    data = ANSI_RE.sub(b"", data)
    out = bytearray()
    i = 0
    while i < len(data):
        if data[i] == 0xFF and i + 1 < len(data):
            if data[i + 1] in (0xFB, 0xFC, 0xFD, 0xFE) and i + 2 < len(data):
                i += 3
                continue
            if data[i + 1] == 0xFA:
                j = data.find(b"\xff\xf0", i)
                i = j + 2 if j != -1 else len(data)
                continue
            i += 2
            continue
        out.append(data[i])
        i += 1
    return out.decode("utf-8", "replace").replace("\r", "")


def parse_hotspot(raw: str) -> list[Device]:
    devices: list[Device] = []
    cur: dict[str, str] = {}

    def flush() -> None:
        if not cur.get("mac"):
            return
        devices.append(
            Device(
                mac=cur["mac"],
                ip=cur.get("ip", ""),
                hostname=cur.get("hostname") or cur.get("name", ""),
                ssid=cur.get("ssid", ""),
                active=cur.get("active") == "yes",
                rssi=_int(cur.get("rssi")),
                txrate=_int(cur.get("txrate")),
                blocked=cur.get("access") == "deny",
            )
        )
        cur.clear()

    for line in raw.splitlines():
        s = line.strip()
        if s.startswith("host:"):
            flush()
            continue
        if ":" not in s:
            continue
        key, _, value = s.partition(":")
        key = key.strip()
        if key in {"mac", "ip", "hostname", "name", "ssid", "active", "rssi", "txrate", "access"}:
            cur[key] = value.strip()
    flush()
    return devices


def _int(v: str | None) -> int | None:
    try:
        return int(str(v).split()[0])
    except Exception:
        return None
