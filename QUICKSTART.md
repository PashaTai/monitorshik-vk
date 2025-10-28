# ⚡ Быстрый старт за 5 минут

> Самая короткая инструкция для запуска VK Comment Monitor

## 📋 Что нужно перед началом

- [ ] Python 3.7+ установлен
- [ ] Аккаунт ВКонтакте
- [ ] Аккаунт Telegram

---

## 🚀 Шаг 1: Получить токены (3 минуты)

### VK токен

1. Откройте [vk.com/apps?act=manage](https://vk.com/apps?act=manage)
2. **Создать приложение** → **Standalone** → Любое название
3. Скопируйте **ID приложения** из URL (например: `12345678`)
4. Откройте в браузере (замените `APP_ID`):
```
https://oauth.vk.com/authorize?client_id=APP_ID&display=page&redirect_uri=https://oauth.vk.com/blank.html&scope=wall,offline&response_type=token&v=5.131
```
5. Скопируйте токен из адресной строки после `access_token=`

### Telegram токен и Chat ID

1. Найдите [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте `/newbot` → придумайте имя → скопируйте токен
3. Найдите [@userinfobot](https://t.me/userinfobot)
4. Отправьте ему любое сообщение → скопируйте ваш ID
5. **ВАЖНО**: Найдите своего бота и отправьте ему `/start`

---

## 💻 Шаг 2: Установка (1 минута)

### Linux / macOS / WSL:
```bash
# Клонируйте или создайте директорию
mkdir vk-bot && cd vk-bot

# Скачайте файлы или скопируйте monitor.py и requirements.txt

# Установите зависимости
pip3 install -r requirements.txt
```

### Windows:
```powershell
# Создайте папку
mkdir vk-bot
cd vk-bot

# Скопируйте файлы monitor.py и requirements.txt

# Установите зависимости
pip install -r requirements.txt
```

---

## ⚙️ Шаг 3: Настройка (1 минута)

Создайте файл `.env` в директории проекта:

```bash
# Linux / macOS / WSL
cp env.example .env
nano .env

# Windows
copy env.example .env
notepad .env
```

**Заполните токены в `.env`:**
```bash
VK_ACCESS_TOKEN=vk1.a.ваш_токен_от_vk
VK_GROUP_ID=parfenchikov_karelia
TELEGRAM_BOT_TOKEN=123456789:AAH_ваш_токен_от_botfather
TELEGRAM_CHAT_ID=ваш_chat_id_из_userinfobot
```

**Форматы `VK_GROUP_ID`** (любой подойдёт):
- `parfenchikov_karelia` (короткое имя)
- `12345678` (числовой ID)
- `club12345678` (с префиксом)
- `https://vk.com/parfenchikov_karelia` (полная ссылка)

---

## ✅ Шаг 4: Проверка (30 секунд)

```bash
python3 check_config.py
```

Должно быть:
```
✓ Переменные окружения: PASSED
✓ VK токен: PASSED
✓ VK группа: PASSED
✓ Telegram бот: PASSED

✓ Все проверки пройдены успешно!
```

**Если ошибки** - читайте вывод, он подскажет что не так.

---

## 🎯 Шаг 5: Запуск!

```bash
python3 monitor.py
```

Вы должны увидеть:
```
[2025-10-28 14:25:30] [INFO] VK Comment Monitor Starting...
[2025-10-28 14:25:31] [INFO] Monitoring group: Парфенчиков|Карелия (ID: 12345678)
[2025-10-28 14:25:32] [INFO] --- Cycle #1 ---
[2025-10-28 14:25:35] [INFO] Initialization complete. Loaded 47 existing comments into cache.
[2025-10-28 14:25:35] [INFO] Now monitoring for NEW comments...
```

**Протестируйте:**
1. Откройте группу ВК в браузере
2. Напишите тестовый комментарий под любым постом
3. Через ~60 секунд должно прийти уведомление в Telegram! 🎉

**Остановка:** `Ctrl+C`

---

## 🌐 Бонус: Запуск на сервере 24/7

Если есть VPS/облако с Ubuntu:

```bash
# 1. Подключитесь к серверу
ssh ubuntu@your_server_ip

# 2. Установите Python (если нет)
sudo apt update && sudo apt install python3 python3-pip -y

# 3. Создайте директорию
mkdir ~/vk-bot && cd ~/vk-bot

# 4. Загрузите файлы (с локальной машины)
scp monitor.py requirements.txt env.example vk-monitor.service ubuntu@your_server_ip:~/vk-bot/

# 5. На сервере: установите и настройте
pip3 install -r requirements.txt
cp env.example .env
nano .env  # Заполните токены

# 6. Проверка
python3 check_config.py

# 7. Установите systemd сервис
sudo cp vk-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable vk-monitor.service
sudo systemctl start vk-monitor.service

# 8. Проверьте статус
sudo systemctl status vk-monitor.service

# 9. Смотрите логи
sudo journalctl -u vk-monitor.service -f
```

**Готово!** Теперь мониторинг работает 24/7, автоматически перезапускается при падении и стартует после перезагрузки сервера.

---

## 🆘 Проблемы?

### Ошибка VK API
```bash
# Проверьте токен
python3 -c "from dotenv import load_dotenv; import os, requests; load_dotenv(); r = requests.get('https://api.vk.com/method/users.get', params={'access_token': os.getenv('VK_ACCESS_TOKEN'), 'v': '5.131'}); print(r.json())"
```

### Telegram не отправляет
```bash
# Проверьте бота (замените <TOKEN> и <CHAT_ID>)
curl -X POST "https://api.telegram.org/bot<TOKEN>/sendMessage" -d "chat_id=<CHAT_ID>&text=Test"
```

### Всё остальное
Запустите диагностику: `python3 check_config.py`

---

**Время на настройку: 5 минут**  
**Сложность: Легко** 🟢  
**Результат: Мониторинг 24/7** ✅

