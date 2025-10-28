#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для проверки конфигурации VK Comment Monitor
Запустите перед основным мониторингом, чтобы убедиться в корректности настроек
"""

import os
import sys
import requests
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Цвета для вывода
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'
BOLD = '\033[1m'


def print_status(message, status):
    """Печать статуса проверки"""
    if status == 'OK':
        print(f"{GREEN}✓{RESET} {message}")
    elif status == 'ERROR':
        print(f"{RED}✗{RESET} {message}")
    elif status == 'WARNING':
        print(f"{YELLOW}⚠{RESET} {message}")
    else:
        print(f"  {message}")


def check_env_variables():
    """Проверка наличия переменных окружения"""
    print(f"\n{BOLD}1. Проверка переменных окружения{RESET}")
    
    required_vars = {
        'VK_ACCESS_TOKEN': os.getenv('VK_ACCESS_TOKEN'),
        'VK_GROUP_ID': os.getenv('VK_GROUP_ID'),
        'TELEGRAM_BOT_TOKEN': os.getenv('TELEGRAM_BOT_TOKEN'),
        'TELEGRAM_CHAT_ID': os.getenv('TELEGRAM_CHAT_ID')
    }
    
    all_ok = True
    for var_name, var_value in required_vars.items():
        if not var_value or var_value.startswith('your_'):
            print_status(f"{var_name}: НЕ ЗАПОЛНЕНА", 'ERROR')
            all_ok = False
        else:
            # Скрываем токены (показываем только первые/последние символы)
            if 'TOKEN' in var_name:
                masked = f"{var_value[:10]}...{var_value[-5:]}" if len(var_value) > 15 else "***"
                print_status(f"{var_name}: {masked}", 'OK')
            else:
                print_status(f"{var_name}: {var_value}", 'OK')
    
    return all_ok


def check_vk_token():
    """Проверка валидности VK токена"""
    print(f"\n{BOLD}2. Проверка VK API токена{RESET}")
    
    token = os.getenv('VK_ACCESS_TOKEN')
    if not token:
        print_status("VK токен не найден", 'ERROR')
        return False
    
    try:
        response = requests.get(
            'https://api.vk.com/method/users.get',
            params={'access_token': token, 'v': '5.131'},
            timeout=10
        )
        data = response.json()
        
        if 'error' in data:
            error = data['error']
            print_status(f"Ошибка VK API: {error.get('error_msg', 'Unknown')}", 'ERROR')
            return False
        
        print_status("VK токен валиден", 'OK')
        return True
    
    except Exception as e:
        print_status(f"Ошибка проверки VK токена: {e}", 'ERROR')
        return False


def check_vk_owner():
    """Проверка доступности группы или страницы VK"""
    print(f"\n{BOLD}3. Проверка группы/страницы VK{RESET}")
    
    token = os.getenv('VK_ACCESS_TOKEN')
    owner_input = os.getenv('VK_GROUP_ID')
    
    if not token or not owner_input:
        print_status("VK токен или VK_GROUP_ID не найдены", 'ERROR')
        return False
    
    owner_id = None
    owner_type = None
    
    # Очищаем входные данные
    clean_input = owner_input.replace('https://vk.com/', '').replace('club', '').replace('public', '').replace('id', '')
    
    # Простая проверка: если это число, пробуем определить тип через API
    if clean_input.isdigit():
        owner_id = int(clean_input)
        # Нужно определить тип через resolveScreenName если это screen_name
    
    # Пробуем разрешить через API
    try:
        response = requests.get(
            'https://api.vk.com/method/utils.resolveScreenName',
            params={
                'access_token': token,
                'screen_name': owner_input.replace('https://vk.com/', '').replace('-', ''),
                'v': '5.131'
            },
            timeout=10
        )
        data = response.json()
        
        if 'error' not in data and data.get('response'):
            owner_type = data['response'].get('type')  # 'user' или 'group'
            obj_id = data['response'].get('object_id')
            
            if owner_type == 'user':
                owner_id = obj_id
            elif owner_type == 'group':
                owner_id = -obj_id
        elif not owner_id:
            print_status(f"Не удалось разрешить владельца: {owner_input}", 'ERROR')
            return False
    except Exception as e:
        print_status(f"Ошибка при разрешении владельца: {e}", 'ERROR')
        return False
    
    # Получаем информацию о владельце
    try:
        if owner_type == 'user' or (owner_id and owner_id > 0):
            # Это пользователь
            response = requests.get(
                'https://api.vk.com/method/users.get',
                params={
                    'access_token': token,
                    'user_ids': abs(owner_id),
                    'v': '5.131'
                },
                timeout=10
            )
            data = response.json()
            
            if 'error' in data:
                print_status(f"Ошибка получения информации о пользователе: {data['error'].get('error_msg')}", 'ERROR')
                return False
            
            user_info = data['response'][0] if data.get('response') else {}
            owner_name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}"
            
            print_status(f"Пользователь найден: {owner_name} (ID: {owner_id})", 'OK')
        else:
            # Это группа
            response = requests.get(
                'https://api.vk.com/method/groups.getById',
                params={
                    'access_token': token,
                    'group_id': abs(owner_id),
                    'v': '5.131'
                },
                timeout=10
            )
            data = response.json()
            
            if 'error' in data:
                print_status(f"Ошибка получения информации о группе: {data['error'].get('error_msg')}", 'ERROR')
                return False
            
            group_info = data['response'][0] if data.get('response') else {}
            owner_name = group_info.get('name', 'Unknown')
            
            print_status(f"Группа найдена: {owner_name} (ID: {owner_id})", 'OK')
        
        # Проверяем доступ к стене
        response = requests.get(
            'https://api.vk.com/method/wall.get',
            params={
                'access_token': token,
                'owner_id': owner_id,
                'count': 1,
                'v': '5.131'
            },
            timeout=10
        )
        data = response.json()
        
        if 'error' in data:
            print_status(f"Нет доступа к стене: {data['error'].get('error_msg')}", 'ERROR')
            return False
        
        print_status("Доступ к стене есть", 'OK')
        
        return True
    
    except Exception as e:
        print_status(f"Ошибка проверки владельца: {e}", 'ERROR')
        return False


def check_telegram_bot():
    """Проверка Telegram бота"""
    print(f"\n{BOLD}4. Проверка Telegram бота{RESET}")
    
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        print_status("Telegram токен или Chat ID не найдены", 'ERROR')
        return False
    
    try:
        # Проверяем бота через getMe
        response = requests.get(
            f'https://api.telegram.org/bot{bot_token}/getMe',
            timeout=10
        )
        data = response.json()
        
        if not data.get('ok'):
            print_status(f"Невалидный Telegram токен: {data.get('description', 'Unknown error')}", 'ERROR')
            return False
        
        bot_info = data.get('result', {})
        bot_username = bot_info.get('username', 'Unknown')
        print_status(f"Telegram бот валиден: @{bot_username}", 'OK')
        
        # Отправляем тестовое сообщение
        response = requests.post(
            f'https://api.telegram.org/bot{bot_token}/sendMessage',
            json={
                'chat_id': chat_id,
                'text': '✅ Проверка конфигурации VK Comment Monitor успешна!',
                'parse_mode': 'HTML'
            },
            timeout=10
        )
        data = response.json()
        
        if not data.get('ok'):
            error_desc = data.get('description', 'Unknown error')
            if 'chat not found' in error_desc.lower():
                print_status(f"Chat ID {chat_id} не найден. Отправьте /start боту @{bot_username}", 'ERROR')
            else:
                print_status(f"Ошибка отправки сообщения: {error_desc}", 'ERROR')
            return False
        
        print_status(f"Тестовое сообщение отправлено в чат {chat_id}", 'OK')
        print_status("Проверьте Telegram - должно прийти сообщение", 'WARNING')
        
        return True
    
    except Exception as e:
        print_status(f"Ошибка проверки Telegram бота: {e}", 'ERROR')
        return False


def main():
    """Главная функция"""
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}VK Comment Monitor - Проверка конфигурации{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}")
    
    # Проверяем наличие .env файла
    if not os.path.exists('.env'):
        print_status("\nФайл .env не найден!", 'ERROR')
        print_status("Скопируйте .env.example в .env и заполните токены", 'WARNING')
        sys.exit(1)
    
    results = []
    
    # Запускаем проверки
    results.append(('Переменные окружения', check_env_variables()))
    results.append(('VK токен', check_vk_token()))
    results.append(('VK группа/страница', check_vk_owner()))
    results.append(('Telegram бот', check_telegram_bot()))
    
    # Итоговый результат
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}Результаты проверки:{RESET}\n")
    
    all_passed = True
    for check_name, result in results:
        status = 'OK' if result else 'ERROR'
        print_status(f"{check_name}: {'PASSED' if result else 'FAILED'}", status)
        if not result:
            all_passed = False
    
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    
    if all_passed:
        print(f"{GREEN}{BOLD}✓ Все проверки пройдены успешно!{RESET}")
        print(f"\nМожете запускать мониторинг:")
        print(f"  python3 monitor.py")
    else:
        print(f"{RED}{BOLD}✗ Обнаружены ошибки в конфигурации{RESET}")
        print(f"\nИсправьте ошибки в файле .env и запустите проверку снова:")
        print(f"  python3 check_config.py")
        sys.exit(1)


if __name__ == '__main__':
    main()

