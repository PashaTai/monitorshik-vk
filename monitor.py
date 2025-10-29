#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VK Comment Monitor - мониторинг комментариев в публичных группах и на страницах ВКонтакте
Отправка уведомлений о новых комментариях в Telegram
Поддерживает: группы (сообщества) и личные страницы пользователей
"""

import os
import time
import re
from datetime import datetime, timedelta
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


def resolve_vk_owner(owner_input: str) -> tuple:
    """
    Преобразует любой формат идентификатора в (owner_id, owner_type, screen_name)
    
    Поддерживаемые форматы:
    - Для групп: 12345678, club12345678, -12345678, parfenchikov_karelia
    - Для пользователей: id12345678, aparfenchikov, durov
    - Полные ссылки: https://vk.com/aparfenchikov, https://vk.com/parfenchikov_karelia
    
    Returns:
        tuple: (owner_id, owner_type, screen_name)
        owner_id: положительный для пользователей, отрицательный для групп
        owner_type: 'user' или 'group'
        screen_name: исходное имя для логов
    """
    owner_input = owner_input.strip()
    original_input = owner_input
    
    # Убираем знак минус, если есть (признак группы)
    if owner_input.startswith('-'):
        owner_input = owner_input[1:]
        is_group = True
    else:
        is_group = False
    
    # Проверяем префикс id (пользователь)
    if owner_input.startswith('id'):
        match = re.match(r'id(\d+)', owner_input)
        if match:
            user_id = int(match.group(1))
            log(f"Detected user ID: {user_id}")
            return (user_id, 'user', original_input)
    
    # Проверяем префиксы club/public (группа)
    if owner_input.startswith('club') or owner_input.startswith('public'):
        match = re.match(r'(club|public)(\d+)', owner_input)
        if match:
            group_id = int(match.group(2))
            log(f"Detected group ID: {group_id}")
            return (-group_id, 'group', original_input)
    
    # Если это чистое число
    if owner_input.isdigit():
        num_id = int(owner_input)
        if is_group:
            log(f"Detected group ID from negative number: {num_id}")
            return (-num_id, 'group', original_input)
        # Числа без префикса требуют проверки через API
        owner_input = str(num_id)
    
    # Извлекаем screen_name из URL
    url_match = re.match(r'https?://vk\.com/([a-zA-Z0-9_]+)', owner_input)
    if url_match:
        owner_input = url_match.group(1)
    
    # Используем utils.resolveScreenName для получения ID и типа
    log(f"Resolving screen name: {owner_input}")
    response = vk_api_call('utils.resolveScreenName', {'screen_name': owner_input})
    
    if response:
        obj_type = response.get('type')
        obj_id = response.get('object_id')
        
        if obj_type == 'user':
            log(f"Resolved to user ID: {obj_id}")
            return (obj_id, 'user', owner_input)
        elif obj_type == 'group':
            log(f"Resolved to group ID: {obj_id}")
            return (-obj_id, 'group', owner_input)
    
    log(f"Failed to resolve owner: {original_input}", 'ERROR')
    return (None, None, None)


def get_wall_posts(owner_id: int, count: int = 10) -> List[Dict]:
    """
    Получает последние посты со стены
    
    Args:
        owner_id: ID владельца стены (положительный для пользователей, отрицательный для групп)
        count: Количество постов для получения
    
    Returns:
        Список постов
    """
    response = vk_api_call('wall.get', {
        'owner_id': owner_id,
        'count': count,
        'filter': 'owner'  # Только посты от владельца
    })
    
    if not response:
        return []
    
    posts = response.get('items', [])
    log(f"Fetched {len(posts)} posts from owner {owner_id}")
    
    return posts


def get_post_comments(owner_id: int, post_id: int, count: int = 20) -> List[Dict]:
    """
    Получает комментарии к посту
    
    Args:
        owner_id: ID владельца стены (положительный для пользователей, отрицательный для групп)
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


def format_telegram_message(comment: Dict, post_url: str, owner_name: str) -> str:
    """
    Форматирует комментарий для отправки в Telegram
    
    Args:
        comment: Объект комментария из VK API
        post_url: Ссылка на пост
        owner_name: Название группы или имя владельца страницы
    
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
        author_id = from_id
    else:  # Группа/сообщество
        author_name = author_info.get('name', 'Unknown Group')
        author_url = f"https://vk.com/club{abs(from_id)}"
        author_id = abs(from_id)
    
    # Время комментария (timestamp в секундах) - МОСКОВСКОЕ ВРЕМЯ
    timestamp = comment.get('date', 0)
    dt = datetime.fromtimestamp(timestamp) + timedelta(hours=3)  # +3 часа для московского времени
    time_str = dt.strftime('%H:%M %d.%m.%Y')
    
    # Текст комментария
    text = comment.get('text', '').strip()
    
    # Проверка на наличие медиафайлов
    attachments = comment.get('attachments', [])
    has_media = len(attachments) > 0
    
    # ID комментария для прямой ссылки
    comment_id = comment.get('id')
    owner_id = comment.get('post_owner_id')
    post_id = comment.get('post_id')
    comment_url = f"https://vk.com/wall{owner_id}_{post_id}?reply={comment_id}"
    
    # Формируем сообщение в зависимости от наличия текста
    if text:
        # Стандартный формат с текстом
        message = f"""🔵 <b>VK</b> | {owner_name}
👤 <a href="{author_url}">{author_name}</a>
🆔 <code>{author_id}</code>
🕐 {time_str}
━━━━━━━━━━━━━━━━━━
<blockquote>{text}</blockquote>

<a href="{post_url}">🔗 Открыть пост</a>
<a href="{comment_url}">💬 Открыть комментарий</a>"""
    else:
        # Альтернативный формат для медиафайлов
        message = f"""🔵 <b>VK</b> | {owner_name}
👤 <a href="{author_url}">{author_name}</a>
🆔 <code>{author_id}</code>
🕐 {time_str}
━━━━━━━━━━━━━━━━━━
<b>Пользователь прислал медиафайл, пожалуйста откройте комментарий чтобы увидеть содержание</b>

<a href="{post_url}">🔗 Открыть пост</a>
<a href="{comment_url}">💬 Открыть комментарий</a>"""
    
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


def get_owner_info(owner_id: int, owner_type: str) -> Dict:
    """
    Получает информацию о владельце стены
    
    Args:
        owner_id: ID владельца (положительный для пользователей, отрицательный для групп)
        owner_type: 'user' или 'group'
    
    Returns:
        Словарь с информацией о владельце
    """
    if owner_type == 'user':
        response = vk_api_call('users.get', {
            'user_ids': owner_id,
            'fields': 'screen_name'
        })
        
        if response and len(response) > 0:
            user = response[0]
            return {
                'name': f"{user.get('first_name', '')} {user.get('last_name', '')}",
                'id': owner_id,
                'screen_name': user.get('screen_name', '')
            }
    else:  # group
        response = vk_api_call('groups.getById', {
            'group_id': abs(owner_id)
        })
        
        if response and len(response) > 0:
            group = response[0]
            group['id'] = owner_id  # Сохраняем отрицательный ID
            return group
    
    return {'name': 'Unknown Owner', 'id': owner_id}


def process_comments(owner_id: int, owner_name: str):
    """
    Основная функция обработки комментариев
    
    Args:
        owner_id: ID владельца для мониторинга (положительный для пользователей, отрицательный для групп)
        owner_name: Название группы или имя пользователя
    """
    global is_first_run, seen_comments
    
    # Получаем последние посты
    posts = get_wall_posts(owner_id, POSTS_TO_CHECK)
    
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
            message = format_telegram_message(comment, post_url, owner_name)
            
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
    
    # Преобразуем идентификатор в (owner_id, owner_type, screen_name)
    owner_id, owner_type, screen_name = resolve_vk_owner(VK_GROUP_ID)
    
    if not owner_id:
        log(f"Failed to resolve VK owner: {VK_GROUP_ID}", 'ERROR')
        log("Please check VK_GROUP_ID in your .env file.", 'ERROR')
        return
    
    # Получаем информацию о владельце
    owner_info = get_owner_info(owner_id, owner_type)
    owner_name = owner_info.get('name', 'Unknown Owner')
    owner_type_ru = 'пользователя' if owner_type == 'user' else 'группы'
    
    log(f"Monitoring {owner_type_ru}: {owner_name} (ID: {owner_id})")
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
                process_comments(owner_id, owner_name)
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

