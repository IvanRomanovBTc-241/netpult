# NetPult Mobile (Android, APK)

Мобильное приложение на Python (Flet). Ставится на телефон как обычный APK,
ходит к роутеру напрямую по локальной сети — сервер не нужен.

## Что умеет

- Список устройств в домашней сети: имя, IP, MAC, Wi-Fi-сеть, скорость линка.
- Кнопка «Отключить» / «Вернуть» — режет устройству доступ к сети на роутере.
- Настройки роутера хранятся на телефоне (адрес, логин, пароль).

Поддерживается **Keenetic** (проверено на KN-1610, KeeneticOS 3.8.5).
Дальше по плану: OpenWrt (ubus), Asus, MikroTik.

## Запуск на компьютере (быстрая проверка UI)

```bash
cd netpult-mobile
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

flet run src/main.py
```

Откроется окно приложения — можно сразу потыкать список и кнопки.

## Сборка APK

Нужно один раз поставить:

1. **Flutter SDK** (стабильная ветка) и добавить `flutter\bin` в PATH.
2. **Android SDK** (проще всего через Android Studio) + JDK 17.
3. Проверить: `flutter doctor` — должно быть без ошибок по Android.

Потом:

```bash
cd netpult-mobile
pip install -r requirements.txt
flet build apk --project netpult --module-name main
```

Готовый файл появится в `build/apk/`. Его можно закинуть на телефон и установить
(Android спросит разрешение на установку из неизвестного источника).

Для публикации в Google Play/RuStore нужен подписанный релиз:

```bash
flet build apk --release --android-signing-key-store path\to\key.jks ...
```

или `flet build aab` для Play.

## Структура

```
src/main.py            — UI на Flet: настройки, список устройств, блокировка
src/netpult/keenetic.py — клиент CLI роутера Keenetic (telnet), разбор устройств
pyproject.toml         — метаданные сборки APK
```

## Важно знать

- Телефон и роутер должны быть в одной сети (домашний Wi-Fi). Из мобильного
  интернета роутер недоступен.
- Логин/пароль роутера хранятся в `client_storage` приложения. Это не шифрованное
  хранилище Android — для личного пользования нормально, для публикации стоит
  перейти на `flutter_secure_storage` через flet-плагин.
- Команда блокировки: `ip hotspot host <mac> deny`, возврат — `permit`.
  Устройство остаётся видимым в списке, но без доступа к сети.
