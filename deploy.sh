#!/bin/bash

# Скрипт для быстрого деплоя VK Comment Monitor на сервер
# Использование: ./deploy.sh user@host

set -e

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Проверка аргументов
if [ -z "$1" ]; then
    echo -e "${RED}Ошибка: не указан хост${NC}"
    echo "Использование: $0 user@host"
    echo "Пример: $0 ubuntu@123.45.67.89"
    exit 1
fi

SERVER=$1
REMOTE_DIR="~/vk-bot"

echo -e "${GREEN}=== VK Comment Monitor Deployment ===${NC}\n"

# Проверка наличия .env файла
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Внимание: файл .env не найден${NC}"
    echo "Не забудьте создать .env на сервере после деплоя!"
    echo ""
fi

echo -e "${GREEN}1. Создание директории на сервере...${NC}"
ssh $SERVER "mkdir -p $REMOTE_DIR"

echo -e "${GREEN}2. Копирование файлов...${NC}"
scp monitor.py requirements.txt .env.example vk-monitor.service check_config.py $SERVER:$REMOTE_DIR/

# Если есть .env, предлагаем скопировать
if [ -f ".env" ]; then
    echo -e "${YELLOW}Найден локальный .env файл. Скопировать на сервер? (y/n)${NC}"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        scp .env $SERVER:$REMOTE_DIR/
        echo -e "${GREEN}✓ .env скопирован${NC}"
    fi
fi

echo -e "${GREEN}3. Установка зависимостей на сервере...${NC}"
ssh $SERVER "cd $REMOTE_DIR && pip3 install -r requirements.txt"

echo -e "${GREEN}4. Настройка systemd сервиса...${NC}"
ssh $SERVER "sudo cp $REMOTE_DIR/vk-monitor.service /etc/systemd/system/ && sudo systemctl daemon-reload"

echo -e "\n${GREEN}=== Деплой завершён ===${NC}\n"
echo -e "Следующие шаги:"
echo -e "  1. Подключитесь к серверу: ${YELLOW}ssh $SERVER${NC}"
echo -e "  2. Перейдите в директорию: ${YELLOW}cd $REMOTE_DIR${NC}"
echo -e "  3. Настройте .env (если не скопировали): ${YELLOW}cp .env.example .env && nano .env${NC}"
echo -e "  4. Проверьте конфигурацию: ${YELLOW}python3 check_config.py${NC}"
echo -e "  5. Запустите сервис: ${YELLOW}sudo systemctl enable vk-monitor.service && sudo systemctl start vk-monitor.service${NC}"
echo -e "  6. Проверьте статус: ${YELLOW}sudo systemctl status vk-monitor.service${NC}"
echo -e "  7. Смотрите логи: ${YELLOW}sudo journalctl -u vk-monitor.service -f${NC}"
echo ""

