#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VK Comment Monitor - мониторинг комментариев в публичных группах ВКонтакте
Отправка уведомлений о новых комментариях в Telegram
"""

import os
import time
import re
from datetime import datetime
from typing import Optional, List, Dict, Any
import requests
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Конфигурация из .env
VK_ACCESS_TOKEN = os.getenv('VK_ACCESS_TOKEN')
VK_GROUP_ID = os.getenv('VK_GROUP_ID')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Параметры мониторинга
POSTS_TO_CHECK = int(os.getenv('POSTS_TO_CHECK', '10'))
COMMENTS_PER_POST = int(os.getenv('COMMENTS_PER_POST', '20'))
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '60'))
REQUEST_DELAY = float(os.getenv('REQUEST_DELAY', '0.4'))
CACHE_LIMIT = int(os.getenv('CACHE_LIMIT', '1000'))

# VK API настройки
VK_API_VERSION = '5.131'
VK_API_BASE = 'https://api.vk.com/method/'

# In-memory кэш обработанных комментариев
seen_comments = set()

# Флаг первого запуска (для умной инициализации)
is_first_run = True


def log(message: str, level: str = 'INFO'):
    """Логирование с временной меткой"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{timestamp}] [{level}] {message}')


def vk_api_call(method: str, params: Dict[str, Any]) -> Optional[Dict]:
    """
    Универсальная функция для вызова VK API методов
    
    Args:
        method: Название метода API (например, 'wall.get')
        params: Параметры запроса
    
    Returns:
        Ответ API или None при ошибке
    """
    params['access_token'] = VK_ACCESS_TOKEN
    params['v'] = VK_API_VERSION
    
    url = f'{VK_API_BASE}{method}'
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if 'error' in data:
            error = data['error']
            log(f"VK API Error: {error.get('error_msg', 'Unknown error')} (code: {error.get('error_code')})", 'ERROR')
            return None
        
        return data.get('response')
    
    except requests.exceptions.RequestException as e:
        log(f"Network error calling VK API: {e}", 'ERROR')
        return None
    
    except Exception as e:
        log(f"Unexpected error calling VK API: {e}", 'ERROR')
        return None


def resolve_vk_group(group_input: str) -> Optional[int]:
    """
    Преобразует любой формат идентификатора группы в числовой ID
    
    Поддерживаемые форматы:
    - Числовой ID: 12345678
    - С префиксами: club12345678, public12345678, -12345678
    - Screen name: parfenchikov_karelia
    - Полная ссылка: https://vk.com/parfenchikov_karelia
    
    Returns:
        Положительный числовой ID группы или None при ошибке
    """
    group_input = group_input.strip()
    
    # Убираем знак минус, если есть
    if group_input.startswith('-'):
        group_input = group_input[1:]
    
    # Проверяем префиксы club/public
    if group_input.startswith('club') or group_input.startswith('public'):
        match = re.match(r'(club|public)(\d+)', group_input)
        if match:
            return int(match.group(2))
    
    # Если это чистое число
    if group_input.isdigit():
        return int(group_input)
    
    # Извлекаем screen_name из URL
    url_match = re.match(r'https?://vk\.com/([a-zA-Z0-9_]+)', group_input)
    if url_match:
        group_input = url_match.group(1)
    
    # Используем utils.resolveScreenName для получения ID
    log(f"Resolving screen name: {group_input}")
    response = vk_api_call('utils.resolveScreenName', {'screen_name': group_input})
    
    if response and response.get('type') == 'group':
        group_id = response.get('object_id')
        log(f"Resolved to group ID: {group_id}")
        return group_id
    
    log(f"Failed to resolve group: {group_input}", 'ERROR')
    return None


def get_wall_posts(group_id: int, count: int = 10) -> List[Dict]:
    """
    Получает последние посты со стены группы
    
    Args:
        group_id: ID группы (положительное число)
        count: Количество постов для получения
    
    Returns:
        Список постов
    """
    owner_id = -abs(group_id)  # Для групп используется отрицательный ID
    
    response = vk_api_call('wall.get', {
        'owner_id': owner_id,
        'count': count,
        'filter': 'owner'  # Только посты от имени сообщества
    })
    
    if not response:
        return []
    
    posts = response.get('items', [])
    log(f"Fetched {len(posts)} posts from group {group_id}")
    
    return posts


def get_post_comments(owner_id: int, post_id: int, count: int = 20) -> List[Dict]:
    """
    Получает комментарии к посту
    
    Args:
        owner_id: ID владельца стены (отрицательный для групп)
        post_id: ID поста
        count: Количество комментариев для получения
    
    Returns:
        Список комментариев
    """
    response = vk_api_call('wall.getComments', {
        'owner_id': owner_id,
        'post_id': post_id,
        'count': count,
        'sort': 'desc',  # Сначала новые
        'need_likes': 0,
        'extended': 1  # Получить информацию о пользователях
    })
    
    if not response:
        return []
    
    comments = response.get('items', [])
    profiles = response.get('profiles', [])
    groups = response.get('groups', [])
    
    # Создаём словарь для быстрого доступа к профилям
    profiles_dict = {profile['id']: profile for profile in profiles}
    groups_dict = {group['id']: group for group in groups}
    
    # Добавляем информацию об авторе к каждому комментарию
    for comment in comments:
        from_id = comment.get('from_id')
        if from_id > 0:  # Пользователь
            comment['author_info'] = profiles_dict.get(from_id, {})
        else:  # Группа
            comment['author_info'] = groups_dict.get(abs(from_id), {})
    
    return comments


def format_telegram_message(comment: Dict, post_url: str, group_name: str) -> str:
    """
    Форматирует комментарий для отправки в Telegram
    
    Args:
        comment: Объект комментария из VK API
        post_url: Ссылка на пост
        group_name: Название группы
    
    Returns:
        Отформатированное сообщение с HTML-разметкой
    """
    # Информация об авторе
    author_info = comment.get('author_info', {})
    from_id = comment.get('from_id', 0)
    
    if from_id > 0:  # Пользователь
        first_name = author_info.get('first_name', 'Unknown')
        last_name = author_info.get('last_name', 'User')
        author_name = f"{first_name} {last_name}"
        author_url = f"https://vk.com/id{from_id}"
    else:  # Группа/сообщество
        author_name = author_info.get('name', 'Unknown Group')
        author_url = f"https://vk.com/club{abs(from_id)}"
    
    # Время комментария (timestamp в секундах)
    timestamp = comment.get('date', 0)
    dt = datetime.fromtimestamp(timestamp)
    time_str = dt.strftime('%H:%M %d.%m.%Y')
    
    # Текст комментария
    text = comment.get('text', '[без текста]')
    
    # ID комментария для прямой ссылки
    comment_id = comment.get('id')
    owner_id = comment.get('post_owner_id')
    post_id = comment.get('post_id')
    comment_url = f"https://vk.com/wall{owner_id}_{post_id}?reply={comment_id}"
    
    # Формируем сообщение
    message = f"""💬 <b>Новый комментарий в {group_name}</b>

📄 <b>Пост:</b> <a href="{post_url}">перейти к посту</a>
👤 <b>Автор:</b> <a href="{author_url}">{author_name}</a>
🕐 <b>Время:</b> {time_str}
━━━━━━━━━━━━━━━━━━

💭 <b>Комментарий:</b>
{text}

🔗 <a href="{comment_url}">Перейти к комментарию</a>"""
    
    return message


def send_telegram_message(message: str, retry_count: int = 3) -> bool:
    """
    Отправляет сообщение в Telegram
    
    Args:
        message: Текст сообщения (HTML-разметка)
        retry_count: Количество попыток при ошибке 429
    
    Returns:
        True если успешно, False при ошибке
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    params = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML',
        'disable_web_page_preview': False
    }
    
    for attempt in range(retry_count):
        try:
            response = requests.post(url, json=params, timeout=10)
            
            if response.status_code == 429:
                # Rate limit exceeded
                retry_after = response.json().get('parameters', {}).get('retry_after', 5)
                log(f"Telegram rate limit hit, waiting {retry_after} seconds", 'WARNING')
                time.sleep(retry_after)
                continue
            
            response.raise_for_status()
            return True
        
        except requests.exceptions.RequestException as e:
            log(f"Error sending Telegram message (attempt {attempt + 1}/{retry_count}): {e}", 'ERROR')
            if attempt < retry_count - 1:
                time.sleep(2)
    
    return False


def get_group_info(group_id: int) -> Dict:
    """
    Получает информацию о группе
    
    Args:
        group_id: ID группы
    
    Returns:
        Словарь с информацией о группе
    """
    response = vk_api_call('groups.getById', {
        'group_id': group_id
    })
    
    if response and len(response) > 0:
        return response[0]
    
    return {'name': 'Unknown Group'}


def process_comments(group_id: int, group_name: str):
    """
    Основная функция обработки комментариев
    
    Args:
        group_id: ID группы для мониторинга
        group_name: Название группы
    """
    global is_first_run, seen_comments
    
    owner_id = -abs(group_id)
    
    # Получаем последние посты
    posts = get_wall_posts(group_id, POSTS_TO_CHECK)
    
    if not posts:
        log("No posts fetched, skipping cycle", 'WARNING')
        return
    
    new_comments_count = 0
    
    for post in posts:
        post_id = post.get('id')
        
        # Формируем URL поста
        post_url = f"https://vk.com/wall{owner_id}_{post_id}"
        
        # Получаем комментарии к посту
        comments = get_post_comments(owner_id, post_id, COMMENTS_PER_POST)
        
        # Задержка между запросами к VK API
        time.sleep(REQUEST_DELAY)
        
        if not comments:
            continue
        
        # Обрабатываем комментарии (от новых к старым из-за sort=desc)
        for comment in comments:
            comment_id = comment.get('id')
            
            if comment_id in seen_comments:
                continue
            
            # Добавляем ID в кэш
            seen_comments.add(comment_id)
            
            # При первом запуске НЕ отправляем уведомления
            if is_first_run:
                continue
            
            # Добавляем информацию о посте в комментарий
            comment['post_owner_id'] = owner_id
            comment['post_id'] = post_id
            
            # Форматируем и отправляем уведомление
            message = format_telegram_message(comment, post_url, group_name)
            
            if send_telegram_message(message):
                new_comments_count += 1
                log(f"Sent notification for comment {comment_id} on post {post_id}")
            else:
                log(f"Failed to send notification for comment {comment_id}", 'ERROR')
            
            # Задержка между сообщениями в Telegram (1.2 секунды)
            time.sleep(1.2)
    
    # После первого прохода снимаем флаг
    if is_first_run:
        is_first_run = False
        log(f"Initialization complete. Loaded {len(seen_comments)} existing comments into cache.")
        log("Now monitoring for NEW comments...")
    elif new_comments_count > 0:
        log(f"Processed {new_comments_count} new comments")
    
    # Ограничение размера кэша
    if len(seen_comments) > CACHE_LIMIT:
        log(f"Cache size exceeded {CACHE_LIMIT}, clearing cache", 'WARNING')
        seen_comments.clear()


def validate_config() -> bool:
    """
    Проверяет наличие всех необходимых переменных конфигурации
    
    Returns:
        True если конфигурация валидна, False иначе
    """
    required_vars = {
        'VK_ACCESS_TOKEN': VK_ACCESS_TOKEN,
        'VK_GROUP_ID': VK_GROUP_ID,
        'TELEGRAM_BOT_TOKEN': TELEGRAM_BOT_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    
    missing_vars = [name for name, value in required_vars.items() if not value]
    
    if missing_vars:
        log(f"Missing required environment variables: {', '.join(missing_vars)}", 'ERROR')
        return False
    
    return True


def main():
    """Главная функция программы"""
    log("=" * 60)
    log("VK Comment Monitor Starting...")
    log("=" * 60)
    
    # Проверка конфигурации
    if not validate_config():
        log("Configuration validation failed. Please check your .env file.", 'ERROR')
        return
    
    # Преобразуем группу в числовой ID
    group_id = resolve_vk_group(VK_GROUP_ID)
    
    if not group_id:
        log(f"Failed to resolve VK group: {VK_GROUP_ID}", 'ERROR')
        log("Please check VK_GROUP_ID in your .env file.", 'ERROR')
        return
    
    # Получаем информацию о группе
    group_info = get_group_info(group_id)
    group_name = group_info.get('name', 'Unknown Group')
    
    log(f"Monitoring group: {group_name} (ID: {group_id})")
    log(f"Parameters: {POSTS_TO_CHECK} posts × {COMMENTS_PER_POST} comments")
    log(f"Check interval: {CHECK_INTERVAL} seconds")
    log("=" * 60)
    
    # Основной цикл мониторинга
    cycle_count = 0
    
    try:
        while True:
            cycle_count += 1
            log(f"--- Cycle #{cycle_count} ---")
            
            try:
                process_comments(group_id, group_name)
            except Exception as e:
                log(f"Error in processing cycle: {e}", 'ERROR')
            
            log(f"Sleeping for {CHECK_INTERVAL} seconds...")
            time.sleep(CHECK_INTERVAL)
    
    except KeyboardInterrupt:
        log("\nShutdown requested by user (Ctrl+C)")
        log(f"Total cycles completed: {cycle_count}")
        log(f"Total comments tracked: {len(seen_comments)}")
        log("VK Comment Monitor stopped.")


if __name__ == '__main__':
    main()

