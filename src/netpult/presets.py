"""Пресеты роутеров: выбор модели сам заполняет протокол и команды."""
from __future__ import annotations

IPTABLES_BLOCK = "iptables -I FORWARD -m mac --mac-source {mac} -j DROP"
IPTABLES_UNBLOCK = "iptables -D FORWARD -m mac --mac-source {mac} -j DROP"

PRESETS: list[dict] = [
    {
        "key": "keenetic",
        "title": "Keenetic",
        "protocol": "keenetic",
        "port": 23,
        "list_cmd": "",
        "block_cmd": "",
        "unblock_cmd": "",
        "note": "Поддержка из коробки: список устройств и блокировка по MAC. Команды не нужны.",
    },
    {
        "key": "openwrt",
        "title": "OpenWrt (и Xiaomi на OpenWrt)",
        "protocol": "telnet",
        "port": 23,
        "list_cmd": "cat /proc/net/arp",
        "block_cmd": IPTABLES_BLOCK,
        "unblock_cmd": IPTABLES_UNBLOCK,
        "note": "Нужен включённый telnet на роутере. Правила iptables сбрасываются при перезагрузке роутера.",
    },
    {
        "key": "asus",
        "title": "Asus (AsusWRT)",
        "protocol": "telnet",
        "port": 23,
        "list_cmd": "cat /var/lib/misc/dnsmasq.leases",
        "block_cmd": IPTABLES_BLOCK,
        "unblock_cmd": IPTABLES_UNBLOCK,
        "note": "Проверено на RT-AC1200L: telnet включается в Администрирование → Система. Правила iptables сбрасываются при перезагрузке роутера.",
    },
    {
        "key": "mikrotik",
        "title": "MikroTik (RouterOS)",
        "protocol": "telnet",
        "port": 23,
        "list_cmd": "/ip dhcp-server lease print",
        "block_cmd": "/ip firewall filter add chain=forward src-mac-address={mac} action=drop",
        "unblock_cmd": "/ip firewall filter remove [find src-mac-address={mac}]",
        "note": "Правила постоянные, переживают перезагрузку.",
    },
    {
        "key": "xiaomi",
        "title": "Xiaomi (заводская прошивка)",
        "protocol": "telnet",
        "port": 23,
        "list_cmd": "",
        "block_cmd": "",
        "unblock_cmd": "",
        "note": "У заводской Xiaomi закрыты telnet и SSH. Нужен адаптер под их HTTP API "
        "или перепрошивка на OpenWrt — скажи модель, добавлю поддержку.",
    },
    {
        "key": "manual",
        "title": "Другое — впишу команды сам",
        "protocol": "telnet",
        "port": 23,
        "list_cmd": "",
        "block_cmd": "",
        "unblock_cmd": "",
        "note": "Заполни команды ниже. {mac} подставится автоматически.",
    },
]

BY_KEY = {p["key"]: p for p in PRESETS}


def apply_preset(profile: dict, key: str) -> dict:
    """Возвращает копию профиля с настройками выбранного пресета."""
    preset = BY_KEY.get(key)
    if not preset:
        return profile
    result = dict(profile)
    result["preset"] = key
    result["protocol"] = preset["protocol"]
    result["port"] = preset["port"]
    result["list_cmd"] = preset["list_cmd"]
    result["block_cmd"] = preset["block_cmd"]
    result["unblock_cmd"] = preset["unblock_cmd"]
    return result


def note_for(key: str) -> str:
    preset = BY_KEY.get(key)
    return preset["note"] if preset else ""
