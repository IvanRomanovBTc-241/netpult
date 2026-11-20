"""NetPult — мобильное приложение (Flet 1.x, Python → Android APK).

Экраны: настройки роутера → список устройств → блокировка/разблокировка.
Доступ к роутеру — напрямую по локальной сети (telnet CLI), сервер не нужен.
"""
from __future__ import annotations

import asyncio

import flet as ft

from netpult.keenetic import Device, Keenetic, KeeneticError

STORAGE_HOST = "router_host"
STORAGE_LOGIN = "router_login"
STORAGE_PASSWORD = "router_password"


async def main(page: ft.Page) -> None:
    page.title = "NetPult"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 16

    prefs = ft.SharedPreferences()
    host = ft.TextField(label="Адрес роутера", value=await prefs.get(STORAGE_HOST) or "192.168.1.1")
    login = ft.TextField(label="Логин", value=await prefs.get(STORAGE_LOGIN) or "admin")
    password = ft.TextField(
        label="Пароль",
        value=await prefs.get(STORAGE_PASSWORD) or "",
        password=True,
        can_reveal_password=True,
    )
    status = ft.Text("", color=ft.Colors.AMBER)
    devices_column = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
    progress = ft.ProgressRing(width=18, height=18, visible=False)

    async def router() -> Keenetic:
        await prefs.set(STORAGE_HOST, host.value.strip())
        await prefs.set(STORAGE_LOGIN, login.value.strip())
        await prefs.set(STORAGE_PASSWORD, password.value)
        return Keenetic(host.value.strip(), login.value.strip(), password.value)

    async def load_devices(_=None) -> None:
        progress.visible = True
        status.value = "Читаю список устройств…"
        page.update()
        try:
            client = await router()
            found = await asyncio.to_thread(lambda: _devices(client))
            render(found)
            status.value = f"Устройств: {len(found)}"
        except (OSError, KeeneticError) as exc:
            status.value = f"Ошибка: {exc}"
        finally:
            progress.visible = False
            page.update()

    async def toggle(device: Device, _=None) -> None:
        status.value = f"{'Возвращаю' if device.blocked else 'Отключаю'} {device.label}…"
        page.update()
        try:
            client = await router()
            await asyncio.to_thread(lambda: _set_access(client, device.mac, device.blocked))
            status.value = "Готово"
        except (OSError, KeeneticError) as exc:
            status.value = f"Ошибка: {exc}"
        await load_devices()

    def render(found: list[Device]) -> None:
        devices_column.controls.clear()
        if not found:
            devices_column.controls.append(ft.Text("Устройств не найдено"))
            page.update()
            return
        for d in sorted(found, key=lambda x: (x.blocked, not x.active, x.label.lower())):
            color = ft.Colors.RED if d.blocked else (ft.Colors.GREEN if d.active else ft.Colors.BLUE_GREY)
            subtitle = " · ".join(
                part for part in [d.ip, d.mac, d.ssid, f"{d.txrate} Мбит" if d.txrate else ""] if part
            )
            devices_column.controls.append(
                ft.Container(
                    padding=12,
                    border_radius=12,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.WHITE),
                    content=ft.Row(
                        [
                            ft.Container(width=10, height=10, border_radius=5, bgcolor=color),
                            ft.Column(
                                [
                                    ft.Text(d.label, weight=ft.FontWeight.W_600, size=15),
                                    ft.Text(subtitle, size=11, color=ft.Colors.BLUE_GREY_200),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.FilledButton(
                                "Вернуть" if d.blocked else "Отключить",
                                on_click=lambda e, dev=d: page.run_task(toggle, dev),
                                style=ft.ButtonStyle(
                                    bgcolor=ft.Colors.RED_900 if d.blocked else ft.Colors.BLUE_GREY_700,
                                ),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                )
            )
        page.update()

    settings = ft.ExpansionTile(
        title=ft.Text("Настройки роутера"),
        subtitle=ft.Text("Keenetic: адрес, логин, пароль", size=11),
        controls=[ft.Column([host, login, password], spacing=10)],
    )

    page.add(
        ft.Row([ft.Text("NetPult", size=22, weight=ft.FontWeight.BOLD), progress], spacing=10),
        ft.Text("Устройства в домашней сети", size=12, color=ft.Colors.BLUE_GREY_200),
        settings,
        ft.Row([ft.FilledButton("Обновить", on_click=lambda e: page.run_task(load_devices))]),
        status,
        ft.Divider(),
        devices_column,
    )

    await load_devices()


def _devices(client: Keenetic) -> list[Device]:
    with client as r:
        return r.devices()


def _set_access(client: Keenetic, mac: str, allow: bool) -> None:
    with client as r:
        r.set_access(mac, allow=allow)


if __name__ == "__main__":
    ft.run(main)
