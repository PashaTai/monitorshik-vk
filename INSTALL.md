# 🚀 Быстрая установка VK Comment Monitor

## Локальная установка (для тестирования)

```bash
# 1. Установите зависимости
pip3 install -r requirements.txt

# 2. Настройте конфигурацию
cp .env.example .env
nano .env  # Заполните токены

# 3. Запустите
python3 monitor.py
```

## Установка на сервер Ubuntu (24/7)

```bash
# 1. Подключитесь к серверу
ssh ubuntu@YOUR_VM_IP

# 2. Обновите систему
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip -y

# 3. Создайте директорию
mkdir -p ~/vk-bot
cd ~/vk-bot

# 4. Загрузите файлы (с локальной машины)
scp monitor.py requirements.txt .env.example vk-monitor.service ubuntu@YOUR_VM_IP:~/vk-bot/

# 5. На сервере: установите зависимости
pip3 install -r requirements.txt

# 6. Настройте .env
cp .env.example .env
nano .env  # Заполните токены

# 7. Тестовый запуск (Ctrl+C для остановки)
python3 monitor.py

# 8. Установите systemd сервис
sudo cp vk-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable vk-monitor.service
sudo systemctl start vk-monitor.service

# 9. Проверьте статус
sudo systemctl status vk-monitor.service
sudo journalctl -u vk-monitor.service -f
```

## Быстрая проверка работоспособности

### 1. Проверка VK токена
```bash
python3 -c "
import requests
import os
from dotenv import load_dotenv
load_dotenv()
token = os.getenv('VK_ACCESS_TOKEN')
r = requests.get(f'https://api.vk.com/method/users.get?access_token={token}&v=5.131')
print(r.json())
"
```

### 2. Проверка Telegram бота
```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/sendMessage" \
  -d "chat_id=<YOUR_CHAT_ID>&text=Тест VK Monitor"
```

### 3. Проверка группы ВК
Откройте группу в браузере в режиме инкогнито и убедитесь, что комментарии видны без авторизации.

## Полезные команды

```bash
# Просмотр логов в реальном времени
sudo journalctl -u vk-monitor.service -f

# Перезапуск сервиса
sudo systemctl restart vk-monitor.service

# Остановка сервиса
sudo systemctl stop vk-monitor.service

# Просмотр статуса
sudo systemctl status vk-monitor.service

# Отключение автозапуска
sudo systemctl disable vk-monitor.service
```

## Что должно произойти при первом запуске

1. ✅ Скрипт разрешит ID группы (выведет название группы)
2. ✅ Загрузит существующие комментарии (выведет "Initialization complete")
3. ✅ Начнёт мониторинг каждые 60 секунд
4. ✅ При появлении нового комментария отправит уведомление в Telegram

## Частые ошибки

| Ошибка | Причина | Решение |
|--------|---------|---------|
| `Missing required environment variables` | Не заполнен .env | Проверьте все поля в .env |
| `Failed to resolve VK group` | Неверный ID группы | Попробуйте screen_name вместо ID |
| `VK API Error: Access denied` | Невалидный токен или закрытые комментарии | Получите новый токен, проверьте группу |
| `Telegram bot not responding` | Не запущен бот или неверный Chat ID | Отправьте /start боту |
| `Service failed to start` | Неверные пути в service файле | Отредактируйте пути в vk-monitor.service |

---

Подробная документация: [README.md](README.md)

