"""NetPult — пульт управления домашней сетью (Flet 1.x, Android APK).

Возможности:
  * несколько профилей роутеров разных фирм (адрес, протокол, логин, пароль);
  * Keenetic — поддержка «из коробки», другие роутеры — через telnet-команды;
  * ручное добавление устройства по MAC (если роутер не отдаёт список клиентов);
  * отключение/возврат доступа и расписание (по времени).

Доступ к роутеру — напрямую по локальной сети, без облака.
"""
from __future__ import annotations

import asyncio
import uuid

import flet as ft

from netpult.adapters import build_adapter, manual_devices
from netpult.keenetic import Device, KeeneticError
from netpult.presets import BY_KEY, PRESETS, note_for
from netpult.scheduler import Scheduler
from netpult.storage import Store, describe, parse_hhmm, rule_key

ACTIVE_KEY = "active_host"
PROTOCOLS = {"keenetic": "Keenetic (из коробки)", "telnet": "Другой роутер (telnet-команды)"}


async def main(page: ft.Page) -> None:
    page.title = "NetPult"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 16

    prefs = ft.SharedPreferences()
    store = Store(prefs)

    state = {
        "profiles": await store.profiles(),
        "rules": await store.rules(),
        "active": None,
        "devices": [],
    }
    active_host = await prefs.get(ACTIVE_KEY)
    if active_host:
        state["active"] = next((p for p in state["profiles"] if p.get("host") == active_host), None)

    status = ft.Text("", color=ft.Colors.AMBER, size=12)
    progress = ft.ProgressRing(width=16, height=16, visible=False, stroke_width=2)
    routers_box = ft.Column(spacing=8)
    devices_box = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
    devices_title = ft.Text("Устройства", size=14, weight=ft.FontWeight.W_600, visible=False)

    # ---------- служебное ----------

    async def save_profiles() -> None:
        await store.save_profiles(state["profiles"])
        scheduler.set_profiles(state["profiles"])

    async def persist_active() -> None:
        if state["active"]:
            await prefs.set(ACTIVE_KEY, str(state["active"].get("host", "")))

    def busy(text: str, on: bool = True) -> None:
        status.value = text
        progress.visible = on
        page.update()

    async def reload_devices(show_errors: bool = True) -> None:
        profile = state["active"]
        if not profile:
            return
        busy("Подключаюсь к роутеру…")
        try:
            found = await asyncio.to_thread(_fetch_devices, profile)
            state["devices"] = found
            status.value = f"{profile.get('name') or profile.get('host')}: устройств {len(found)}"
        except (OSError, KeeneticError) as exc:
            state["devices"] = manual_devices(profile)
            if show_errors:
                status.value = f"Не удалось получить список: {exc}"
        finally:
            progress.visible = False
        render_devices()
        page.update()

    # ---------- расписание ----------

    async def on_schedule_changed() -> None:
        status.value = "Расписание применено"
        page.update()

    scheduler = Scheduler(store, on_change=on_schedule_changed)
    scheduler.set_profiles(state["profiles"])

    async def open_schedule(device: Device) -> None:
        profile = state["active"]
        if not profile:
            return
        key = rule_key(str(profile.get("host", "")), device.mac)
        rule = state["rules"].get(key, {})
        enabled = ft.Switch(label="Включить расписание", value=bool(rule.get("enabled")))
        off_field = ft.TextField(label="Отключать в (ЧЧ:ММ)", value=str(rule.get("off", "00:00")), width=220)
        on_field = ft.TextField(label="Включать в (ЧЧ:ММ)", value=str(rule.get("on", "08:00")), width=220)
        error = ft.Text("", color=ft.Colors.RED_300, size=12)

        async def save_rule(_) -> None:
            if enabled.value:
                if parse_hhmm(off_field.value or "") is None or parse_hhmm(on_field.value or "") is None:
                    error.value = "Время в формате ЧЧ:ММ, например 00:00"
                    page.update()
                    return
                if off_field.value.strip() == on_field.value.strip():
                    error.value = "Время отключения и включения совпадает"
                    page.update()
                    return
            state["rules"][key] = {
                "enabled": bool(enabled.value),
                "off": (off_field.value or "00:00").strip(),
                "on": (on_field.value or "08:00").strip(),
            }
            await store.save_rules(state["rules"])
            page.pop_dialog()
            render_devices()
            page.update()

        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text(f"Расписание: {device.label}", size=16),
                content=ft.Column(
                    [
                        ft.Text(
                            "Пока приложение запущено, оно само выключит и включит интернет этому устройству.",
                            size=11,
                            color=ft.Colors.BLUE_GREY_200,
                        ),
                        enabled,
                        off_field,
                        on_field,
                        error,
                    ],
                    tight=True,
                    spacing=10,
                    width=280,
                ),
                actions=[
                    ft.TextButton("Отмена", on_click=lambda e: page.pop_dialog()),
                    ft.FilledButton("Сохранить", on_click=save_rule),
                ],
            )
        )

    # ---------- устройства ----------

    def render_devices() -> None:
        devices_box.controls.clear()
        devices_title.visible = bool(state["active"])
        if not state["active"]:
            page.update()
            return
        profile = state["active"]
        if not state["devices"]:
            hint = (
                "Список пуст. Для этого роутера можно добавить устройство по MAC вручную — "
                "кнопка «+» справа."
                if str(profile.get("protocol")) == "telnet"
                else "Список пуст — проверь адрес, логин и пароль."
            )
            devices_box.controls.append(ft.Text(hint, size=12, color=ft.Colors.BLUE_GREY_200))
        host = str(profile.get("host", ""))
        for d in sorted(state["devices"], key=lambda x: (x.blocked, not x.active, x.label.lower())):
            rule = state["rules"].get(rule_key(host, d.mac), {})
            color = ft.Colors.RED if d.blocked else (ft.Colors.GREEN if d.active else ft.Colors.BLUE_GREY)
            subtitle = " · ".join(part for part in [d.ip, d.mac, d.ssid] if part)
            caption = describe(rule)
            devices_box.controls.append(
                ft.Container(
                    padding=10,
                    border_radius=12,
                    bgcolor=ft.Colors.with_opacity(0.07, ft.Colors.WHITE),
                    content=ft.Row(
                        [
                            ft.Container(width=10, height=10, border_radius=5, bgcolor=color),
                            ft.Column(
                                [
                                    ft.Text(d.label, weight=ft.FontWeight.W_600, size=14, no_wrap=True),
                                    ft.Text(subtitle, size=10, color=ft.Colors.BLUE_GREY_200),
                                    ft.Text(caption, size=10, color=ft.Colors.AMBER) if caption else ft.Container(height=0),
                                ],
                                spacing=1,
                                expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.SCHEDULE,
                                tooltip="Расписание",
                                icon_color=ft.Colors.AMBER if caption else ft.Colors.BLUE_GREY_300,
                                on_click=lambda e, dev=d: page.run_task(open_schedule, dev),
                            ),
                            ft.FilledButton(
                                "Вернуть" if d.blocked else "Отключить",
                                style=ft.ButtonStyle(
                                    bgcolor=ft.Colors.RED_900 if d.blocked else ft.Colors.BLUE_GREY_700,
                                ),
                                on_click=lambda e, dev=d: page.run_task(toggle_device, dev),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                )
            )
        page.update()

    async def toggle_device(device: Device) -> None:
        profile = state["active"]
        if not profile:
            return
        busy(f"{'Возвращаю' if device.blocked else 'Отключаю'} {device.label}…")
        try:
            await asyncio.to_thread(_set_access, profile, device.mac, device.blocked)
            status.value = "Готово"
        except (OSError, KeeneticError) as exc:
            status.value = f"Ошибка: {exc}"
        await reload_devices(show_errors=False)

    async def open_manual_device_dialog() -> None:
        profile = state["active"]
        if not profile:
            return
        mac_field = ft.TextField(label="MAC устройства", hint_text="aa:bb:cc:dd:ee:ff")
        name_field = ft.TextField(label="Название", hint_text="Телевизор на кухне")
        error = ft.Text("", color=ft.Colors.RED_300, size=12)

        async def save(_) -> None:
            mac = (mac_field.value or "").strip().lower().replace("-", ":")
            if len(mac.split(":")) != 6:
                error.value = "MAC в формате aa:bb:cc:dd:ee:ff"
                page.update()
                return
            items = profile.setdefault("manual_devices", [])
            items.append({"mac": mac, "name": (name_field.value or "").strip() or mac})
            await save_profiles()
            page.pop_dialog()
            await reload_devices()

        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Добавить устройство", size=16),
                content=ft.Column([mac_field, name_field, error], tight=True, spacing=10, width=280),
                actions=[
                    ft.TextButton("Отмена", on_click=lambda e: page.pop_dialog()),
                    ft.FilledButton("Добавить", on_click=save),
                ],
            )
        )

    # ---------- профили ----------

    async def connect_profile(profile: dict) -> None:
        state["active"] = profile
        await persist_active()
        render_routers()
        await reload_devices()

    async def delete_profile(profile: dict) -> None:
        state["profiles"] = [p for p in state["profiles"] if p.get("id") != profile.get("id")]
        if state["active"] and state["active"].get("id") == profile.get("id"):
            state["active"] = None
            state["devices"] = []
        for key in list(state["rules"]):
            if key.startswith(str(profile.get("host", "")).lower() + "|"):
                state["rules"].pop(key, None)
        await store.save_rules(state["rules"])
        await save_profiles()
        render_routers()
        render_devices()

    async def open_profile_dialog(profile: dict | None = None) -> None:
        editing = profile is not None
        data = profile or {}
        name = ft.TextField(label="Название (Дом, Мама, дача…)", value=data.get("name", ""))
        host = ft.TextField(label="Адрес роутера", value=data.get("host", "192.168.1.1"))
        protocol = ft.Dropdown(
            label="Протокол (ставится автоматически)",
            value=str(data.get("protocol", "keenetic")),
            options=[ft.dropdown.Option(key, label) for key, label in PROTOCOLS.items()],
        )
        preset_dd = ft.Dropdown(
            label="Модель роутера",
            value=str(data.get("preset", "keenetic")),
            options=[ft.dropdown.Option(p["key"], p["title"]) for p in PRESETS],
        )
        preset_note = ft.Text(note_for(str(data.get("preset", "keenetic"))), size=10, color=ft.Colors.BLUE_GREY_200)
        port = ft.TextField(
            label="Порт",
            value=str(data.get("port", 23)),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=110,
        )
        login = ft.TextField(label="Логин", value=data.get("login", "admin"))
        password = ft.TextField(label="Пароль", value=data.get("password", ""), password=True, can_reveal_password=True)

        list_cmd = ft.TextField(
            label="Команда «показать устройства»",
            value=data.get("list_cmd", ""),
            hint_text="например: cat /proc/net/arp",
            multiline=True,
            min_lines=1,
            max_lines=2,
        )
        block_cmd = ft.TextField(
            label="Команда «заблокировать» ({mac})",
            value=data.get("block_cmd", ""),
            hint_text="iptables -I FORWARD -m mac --mac-source {mac} -j DROP",
            multiline=True,
            min_lines=1,
            max_lines=2,
        )
        unblock_cmd = ft.TextField(
            label="Команда «разблокировать» ({mac})",
            value=data.get("unblock_cmd", ""),
            hint_text="iptables -D FORWARD -m mac --mac-source {mac} -j DROP",
            multiline=True,
            min_lines=1,
            max_lines=2,
        )
        telnet_box = ft.Column([port, list_cmd, block_cmd, unblock_cmd], spacing=10, visible=False)
        error = ft.Text("", color=ft.Colors.RED_300, size=12)

        def toggle_protocol(_) -> None:
            telnet_box.visible = protocol.value == "telnet"
            page.update()

        def on_preset(_) -> None:
            preset = BY_KEY.get(preset_dd.value or "")
            if not preset:
                return
            protocol.value = preset["protocol"]
            port.value = str(preset["port"])
            list_cmd.value = preset["list_cmd"]
            block_cmd.value = preset["block_cmd"]
            unblock_cmd.value = preset["unblock_cmd"]
            preset_note.value = preset["note"]
            telnet_box.visible = preset["protocol"] == "telnet"
            page.update()

        protocol.on_select = toggle_protocol
        preset_dd.on_select = on_preset
        telnet_box.visible = protocol.value == "telnet"

        async def save(_) -> None:
            host_value = (host.value or "").strip()
            if not host_value:
                error.value = "Укажи адрес роутера"
                page.update()
                return
            item = {
                "id": data.get("id") or uuid.uuid4().hex[:8],
                "name": (name.value or "").strip() or host_value,
                "host": host_value,
                "protocol": protocol.value or "keenetic",
                "preset": preset_dd.value or "manual",
                "port": int(port.value or 23) if str(port.value or "23").isdigit() else 23,
                "login": (login.value or "").strip(),
                "password": password.value or "",
                "list_cmd": (list_cmd.value or "").strip(),
                "block_cmd": (block_cmd.value or "").strip(),
                "unblock_cmd": (unblock_cmd.value or "").strip(),
                "manual_devices": data.get("manual_devices", []),
            }
            if editing:
                state["profiles"] = [item if p.get("id") == item["id"] else p for p in state["profiles"]]
                if state["active"] and state["active"].get("id") == item["id"]:
                    state["active"] = item
            else:
                state["profiles"].append(item)
                state["active"] = item
            await save_profiles()
            await persist_active()
            page.pop_dialog()
            render_routers()
            await reload_devices()

        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Изменить роутер" if editing else "Новый роутер", size=16),
                content=ft.Column(
                    [
                        name,
                        host,
                        preset_dd,
                        preset_note,
                        protocol,
                        telnet_box,
                        login,
                        password,
                        error,
                    ],
                    tight=True,
                    spacing=10,
                    width=320,
                    scroll=ft.ScrollMode.AUTO,
                ),
                actions=[
                    ft.TextButton("Отмена", on_click=lambda e: page.pop_dialog()),
                    ft.FilledButton("Сохранить", on_click=save),
                ],
            )
        )

    def render_routers() -> None:
        routers_box.controls.clear()
        if not state["profiles"]:
            routers_box.controls.append(
                ft.Text("Добавь роутер: адрес, протокол, логин и пароль администратора.", size=12, color=ft.Colors.BLUE_GREY_200)
            )
        for profile in state["profiles"]:
            is_active = bool(state["active"]) and state["active"].get("id") == profile.get("id")
            proto = PROTOCOLS.get(str(profile.get("protocol", "keenetic")), "")
            routers_box.controls.append(
                ft.Container(
                    padding=10,
                    border_radius=12,
                    bgcolor=ft.Colors.with_opacity(0.12 if is_active else 0.06, ft.Colors.BLUE if is_active else ft.Colors.WHITE),
                    content=ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text(profile.get("name") or profile.get("host"), weight=ft.FontWeight.W_600, size=14),
                                    ft.Text(f"{profile.get('host')} · {proto}", size=9, color=ft.Colors.BLUE_GREY_200),
                                ],
                                spacing=1,
                                expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.EDIT,
                                tooltip="Изменить",
                                icon_color=ft.Colors.BLUE_GREY_200,
                                on_click=lambda e, p=profile: page.run_task(open_profile_dialog, p),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                tooltip="Удалить",
                                icon_color=ft.Colors.BLUE_GREY_200,
                                on_click=lambda e, p=profile: page.run_task(delete_profile, p),
                            ),
                            ft.FilledButton(
                                "Активен" if is_active else "Подключить",
                                disabled=is_active,
                                on_click=lambda e, p=profile: page.run_task(connect_profile, p),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                )
            )
        page.update()

    # ---------- страница ----------

    page.add(
        ft.Row([ft.Text("NetPult", size=22, weight=ft.FontWeight.BOLD), progress], spacing=10),
        ft.Text("Пульт домашней сети", size=11, color=ft.Colors.BLUE_GREY_200),
        ft.Row(
            [
                ft.Text("Роутеры", size=14, weight=ft.FontWeight.W_600),
                ft.IconButton(
                    icon=ft.Icons.ADD,
                    tooltip="Добавить роутер",
                    on_click=lambda e: page.run_task(open_profile_dialog, None),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        routers_box,
        ft.Divider(),
        ft.Row(
            [
                devices_title,
                ft.Row(
                    [
                        ft.IconButton(
                            icon=ft.Icons.ADD_LINK,
                            tooltip="Добавить устройство по MAC",
                            on_click=lambda e: page.run_task(open_manual_device_dialog),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.REFRESH,
                            tooltip="Обновить",
                            on_click=lambda e: page.run_task(reload_devices),
                        ),
                    ],
                    spacing=0,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        devices_box,
        status,
    )

    render_routers()
    render_devices()
    scheduler.start()
    if state["active"]:
        await reload_devices()


def _fetch_devices(profile: dict) -> list[Device]:
    found = build_adapter(profile).list_devices()
    known = {d.mac for d in found}
    for manual in manual_devices(profile):
        if manual.mac not in known:
            found.append(manual)
    return found


def _set_access(profile: dict, mac: str, allow: bool) -> None:
    build_adapter(profile).set_access(mac, allow)


if __name__ == "__main__":
    ft.run(main)
