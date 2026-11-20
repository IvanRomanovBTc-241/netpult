# Сборка APK в облаке (GitHub Actions)

Локальная сборка на этой машине падает из-за окружения Gradle/Java, поэтому APK
собирается на Linux-раннере GitHub — там всё уже настроено.

## 1. Создать репозиторий

На github.com: **New repository** → имя, например `netpult` → можно приватный →
**Create repository** (без README, он не нужен).

## 2. Загрузить проект

В обычном cmd, из папки `netpult-mobile`:

```bat
cd /d C:\Users\Ivan\Documents\deepseek-harness\default-workspace\netpult-mobile

git init
git add .
git commit -m "NetPult: приложение и workflow сборки"
git branch -M main
git remote add origin https://github.com/ВАШ_ЛОГИН/netpult.git
git push -u origin main
```

Если git попросит авторизацию — проще всего поставить GitHub CLI (`gh auth login`
через браузер) или создать Personal Access Token и использовать его как пароль.

## 3. Запустить сборку

1. Открыть репозиторий на GitHub → вкладка **Actions**.
2. Слева выбрать **Build APK** → справа **Run workflow** → **Run workflow**.
3. Через 10–20 минут появится зелёная галочка.

## 4. Забрать APK

Внутри успешного запуска внизу страницы — раздел **Artifacts** → скачать
`netpult-apk.zip` → внутри `app-release.apk`.

## Что дальше с APK

1. Перекинуть файл на телефон (кабель, облако, Telegram «Избранное»).
2. Открыть на телефоне, разрешить установку из неизвестных источников.
3. В приложении ввести адрес роутера `192.168.1.1`, логин и пароль администратора.
4. Телефон и роутер должны быть в одной домашней сети.

## Если сборка в облаке упадёт

Лог будет виден прямо в Actions. Скинь последние 50 строк — поправлю workflow.
Версия Flutter зафиксирована (3.47.9), потому что именно её требует flet 1.1.2.
