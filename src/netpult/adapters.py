"""Адаптеры роутеров: единый интерфейс под разные фирмы.

Единого протокола у роутеров нет, поэтому:
  * Keenetic  — родной CLI (telnet), список устройств, доступ по MAC;
  * Telnet    — универсальный: пользователь сам задаёт команды для
                «показать устройства», «заблокировать», «разблокировать»;
                подходит для OpenWrt, старых Xiaomi с telnet, Asus и т.п.

Плейсхолдер {mac} в командах заменяется на MAC устройства.
"""
from __future__ import annotations

import re
import socket
import time

from .keenetic import Device, Keenetic, KeeneticError

MAC_RE = re.compile(r"(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}")
IP_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
ANSI_RE = re.compile(rb"\x1b\[[0-9;]*[A-Za-z]")


class BaseAdapter:
    def list_devices(self) -> list[Device]:
        raise NotImplementedError

    def set_access(self, mac: str, allow: bool) -> None:
        raise NotImplementedError


class KeeneticAdapter(BaseAdapter):
    def __init__(self, profile: dict) -> None:
        self._profile = profile

    def _router(self) -> Keenetic:
        return Keenetic(
            str(self._profile.get("host", "")),
            str(self._profile.get("login", "")),
            str(self._profile.get("password", "")),
            port=int(self._profile.get("port") or 23),
        )

    def list_devices(self) -> list[Device]:
        with self._router() as router:
            return router.devices()

    def set_access(self, mac: str, allow: bool) -> None:
        with self._router() as router:
            router.set_access(mac, allow=allow)


class TelnetAdapter(BaseAdapter):
    """Универсальный telnet-адаптер с пользовательскими командами."""

    def __init__(self, profile: dict) -> None:
        self._profile = profile
        self._block = str(profile.get("block_cmd", "")).strip()
        self._unblock = str(profile.get("unblock_cmd", "")).strip()
        self._list = str(profile.get("list_cmd", "")).strip()

    def _session(self) -> "TelnetSession":
        return TelnetSession(
            host=str(self._profile.get("host", "")),
            port=int(self._profile.get("port") or 23),
            login=str(self._profile.get("login", "")),
            password=str(self._profile.get("password", "")),
        )

    def list_devices(self) -> list[Device]:
        if not self._list:
            return []
        with self._session() as session:
            output = session.command(self._list)
        return parse_devices(output)

    def set_access(self, mac: str, allow: bool) -> None:
        template = self._block if not allow else self._unblock
        if not template:
            raise KeeneticError(
                "Не задана команда для этого действия. Открой профиль роутера и впиши команду."
            )
        command = template.replace("{mac}", mac)
        with self._session() as session:
            out = session.command(command)
        lowered = out.lower()
        if "not found" in lowered or "denied" in lowered or "error" in lowered:
            raise KeeneticError(out.strip()[-200:])


class TelnetSession:
    """Простое telnet-подключение: логин, пароль, произвольная команда."""

    def __init__(self, host: str, port: int, login: str, password: str, timeout: float = 8.0) -> None:
        self.host = host
        self.port = port
        self.login = login
        self.password = password
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._banner = ""

    def __enter__(self) -> "TelnetSession":
        self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self._sock.settimeout(self.timeout)
        self._banner = self._read(1.5)
        if self.login and re.search(r"login\s*:?", self._banner, re.IGNORECASE):
            self._send(self.login)
            after_login = self._read(2.0)
            if re.search(r"password\s*:?", after_login, re.IGNORECASE):
                self._send(self.password)
                self._read(2.5)
        return self

    def __exit__(self, *exc) -> None:
        if self._sock:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def _send(self, line: str) -> None:
        assert self._sock
        self._sock.sendall(line.encode() + b"\r\n")

    def _read(self, seconds: float = 1.0) -> str:
        assert self._sock
        buf = b""
        deadline = time.time() + seconds
        while time.time() < deadline:
            try:
                chunk = self._sock.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            buf += chunk
            deadline = time.time() + 0.35
        return _clean(buf)

    def command(self, command: str, wait: float = 2.5) -> str:
        self._send(command)
        return self._read(wait)


def _clean_name(line: str, mac: str, ip: str) -> str:
    """Пытаемся вытащить из строки осмысленное имя, а не служебные флаги."""
    text = MAC_RE.sub(" ", line)
    text = IP_RE.sub(" ", text)
    junk = {"0x1", "0x2", "0x0", "*", "br-lan", "br0", "eth0", "eth1", "wlan0", "wlan1", "lan", "wan", "dynamic"}
    parts = [p for p in re.split(r"[\s|;,]+", text) if p and p.lower() not in junk]
    parts = [
        p for p in parts
        if not re.fullmatch(r"0x[0-9a-f]+", p, re.IGNORECASE)
        and not p.isdigit()
        and not re.search(r"[0-9a-f]{2}[:-][0-9a-f]{2}", p, re.IGNORECASE)
        and not p.startswith(":")
    ]
    return " ".join(parts)[:40].strip(" :-")


def parse_devices(output: str) -> list[Device]:
    """Достаём MAC/IP из произвольного вывода списка клиентов."""
    devices: dict[str, Device] = {}
    for line in output.splitlines():
        mac_match = MAC_RE.search(line)
        if not mac_match:
            continue
        mac = mac_match.group(0).lower().replace("-", ":")
        ip_match = IP_RE.search(line)
        ip = ip_match.group(0) if ip_match else ""
        name = _clean_name(line, mac_match.group(0), ip)
        devices[mac] = Device(mac=mac, ip=ip, hostname=name, active=True)
    return list(devices.values())


def build_adapter(profile: dict) -> BaseAdapter:
    protocol = str(profile.get("protocol", "keenetic")).lower()
    if protocol in {"keenetic", ""}:
        return KeeneticAdapter(profile)
    if protocol in {"telnet", "generic", "other"}:
        return TelnetAdapter(profile)
    raise KeeneticError(f"Неизвестный протокол: {protocol}")


def manual_devices(profile: dict) -> list[Device]:
    """Устройства, добавленные вручную (для роутеров без списка клиентов)."""
    result = []
    for item in profile.get("manual_devices", []) or []:
        mac = str(item.get("mac", "")).lower().replace("-", ":")
        if not MAC_RE.fullmatch(mac):
            continue
        result.append(Device(mac=mac, ip="", hostname=str(item.get("name", "")), active=False))
    return result


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
