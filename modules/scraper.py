import requests
from bs4 import BeautifulSoup
import hashlib
import logging
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from flask import current_app
import os
import json
import re
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

def get_html(url, use_selenium=False):
    """
    Получает HTML страницы
    
    Args:
        url (str): URL страницы
        use_selenium (bool): Использовать ли Selenium для страниц с JavaScript
        
    Returns:
        str: HTML содержимое страницы
    """
    try:
        if use_selenium:
            return get_html_selenium(url)
        else:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            return response.text
    except Exception as e:
        logger.error(f"Error fetching HTML from {url}: {str(e)}")
        return None


def get_html_selenium(url):
    """
    Получает HTML страницы с использованием Selenium (для страниц с JavaScript)
    
    Args:
        url (str): URL страницы
        
    Returns:
        str: HTML содержимое страницы
    """
    driver = None
    try:
        # Настройка опций Chrome
        chrome_options = Options()
        if current_app.config.get('HEADLESS_BROWSER', True):
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Инициализация драйвера
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Загрузка страницы
        driver.get(url)
        time.sleep(5)  # Даем странице время загрузиться
        
        return driver.page_source
    except Exception as e:
        logger.error(f"Error using Selenium for {url}: {str(e)}")
        return None
    finally:
        if driver:
            driver.quit()


def extract_data_with_selectors(html, selectors, base_url):
    """
    Извлекает данные со страницы с использованием CSS селекторов
    
    Args:
        html (str): HTML страницы
        selectors (dict): Словарь селекторов
        base_url (str): Базовый URL для относительных ссылок
        
    Returns:
        list: Список извлеченных элементов
    """
    
    if not html:
        print("HTML пустой")
        return []
        
    soup = BeautifulSoup(html, 'lxml')
    items = []
    
    # Получаем селектор контейнера и элементов
    container_selector = selectors.get('container', 'body')
    item_selector = selectors.get('item')
    
    print(f"Поиск контейнера по селектору: {container_selector}")
    
    # Находим контейнер
    try:
        container = soup.select_one(container_selector)
        if not container:
            print(f"Контейнер не найден по селектору: {container_selector}")
            return []
        print(f"Контейнер найден: {container.name}")
    except Exception as e:
        print(f"Ошибка при поиске контейнера: {str(e)}")
        return []
    
    # Находим все элементы
    print(f"Поиск элементов по селектору: {item_selector}")
    try:
        if item_selector:
            elements = container.select(item_selector)
            print(f"Найдено элементов: {len(elements)}")
        else:
            elements = [container]
            print("Используем контейнер как единственный элемент")
    except Exception as e:
        print(f"Ошибка при поиске элементов: {str(e)}")
        return []
    
    # Извлекаем данные из каждого элемента
    for element in elements:
        item_data = {}
        
        # Извлекаем заголовок
        if 'title' in selectors:
            try:
                title_element = element.select_one(selectors['title'])
                if title_element:
                    item_data['title'] = title_element.get_text(strip=True)
                else:
                    item_data['title'] = 'No Title'
            except Exception as e:
                logger.warning(f"Error extracting title: {str(e)}")
                item_data['title'] = 'No Title'
        else:
            item_data['title'] = 'No Title'
        
        # Извлекаем ссылку
        if 'link' in selectors:
            try:
                link_element = element.select_one(selectors['link'])
                if link_element and link_element.has_attr('href'):
                    link = link_element['href']
                    # Преобразуем относительные ссылки в абсолютные
                    item_data['link'] = urljoin(base_url, link)
                else:
                    item_data['link'] = base_url
            except Exception as e:
                logger.warning(f"Error extracting link: {str(e)}")
                item_data['link'] = base_url
        else:
            item_data['link'] = base_url
        
        # Извлекаем описание
        if 'description' in selectors:
            try:
                desc_element = element.select_one(selectors['description'])
                if desc_element:
                    item_data['description'] = desc_element.get_text(strip=True)
                else:
                    item_data['description'] = ''
            except Exception as e:
                logger.warning(f"Error extracting description: {str(e)}")
                item_data['description'] = ''
        else:
            item_data['description'] = ''
        
        # Извлекаем изображение
        if 'image' in selectors:
            try:
                img_element = element.select_one(selectors['image'])
                if img_element and img_element.has_attr('src'):
                    img_src = img_element['src']
                    # Преобразуем относительные ссылки в абсолютные
                    item_data['image'] = urljoin(base_url, img_src)
                else:
                    item_data['image'] = ''
            except Exception as e:
                logger.warning(f"Error extracting image: {str(e)}")
                item_data['image'] = ''
        else:
            # Пробуем найти изображения даже без селектора
            try:
                img = element.find('img')
                if img and img.has_attr('src'):
                    item_data['image'] = urljoin(base_url, img['src'])
                else:
                    item_data['image'] = ''
            except:
                item_data['image'] = ''
        
        # Извлекаем дату публикации
        if 'date' in selectors:
            try:
                date_element = element.select_one(selectors['date'])
                if date_element:
                    date_text = date_element.get_text(strip=True)
                    # Попытка преобразования даты
                    item_data['published'] = parse_date(date_text)
                else:
                    item_data['published'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            except Exception as e:
                logger.warning(f"Error extracting date: {str(e)}")
                item_data['published'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        else:
            item_data['published'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        
        # Создаем уникальный GUID на основе ссылки или содержимого
        item_data['guid'] = hashlib.md5(
            (item_data['link'] + item_data['title']).encode()
        ).hexdigest()
        
        items.append(item_data)
    
    return items


def parse_date(date_text):
    """
    Пытается преобразовать текстовую дату в строковое представление даты/времени
    
    Args:
        date_text (str): Текстовое представление даты
        
    Returns:
        str: Строковое представление даты в формате '%Y-%m-%d %H:%M:%S'
    """
    try:
        # Удаляем лишние символы
        date_text = re.sub(r'[^\w\s\-\/\.,:]', '', date_text)
        
        # Пытаемся распознать дату
        from dateutil import parser
        parsed_date = parser.parse(date_text)
        return parsed_date.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')


def scrape_feed(feed):
    """
    Скрапит веб-страницу и преобразует в формат, аналогичный RSS
    """
    print(f"Запущен scrape_feed для {feed.name}")
    selectors = feed.get_selectors()
    print(f"Селекторы: {selectors}")
    
    # Проверяем наличие необходимых селекторов
    if not selectors or 'container' not in selectors or 'item' not in selectors:
        print(f"Отсутствуют необходимые селекторы для ленты {feed.name}")
        logger.error(f"Missing required selectors for feed {feed.name}")
        return None
    
    # Определяем, нужно ли использовать Selenium
    use_selenium = selectors.get('use_selenium', False)
    print(f"Использование Selenium: {use_selenium}")
    
    # Получаем HTML страницы
    html = get_html(feed.url, use_selenium)
    if not html:
        print(f"Не удалось получить HTML для {feed.url}")
        return None
    
    print(f"HTML получен, длина: {len(html)} символов")
    
    # Извлекаем данные
    entries = extract_data_with_selectors(html, selectors, feed.url)
    print(f"Найдено элементов: {len(entries) if entries else 0}")
    
    if not entries or len(entries) == 0:
        print(f"Не найдено элементов для ленты {feed.name}")
        return None
    
    return {
        'title': feed.name,
        'description': f'Scraped feed from {feed.url}',
        'entries': entries
    }


def test_selectors(url, selectors, use_selenium=False):
    """
    Тестирует селекторы на указанном URL и возвращает извлеченные данные
    
    Args:
        url (str): URL страницы
        selectors (dict): Словарь селекторов
        use_selenium (bool): Использовать ли Selenium
        
    Returns:
        dict: Результаты тестирования
    """
    # Проверка наличия необходимых селекторов
    if not selectors.get('container') or not selectors.get('item'):
        return {
            'success': False,
            'message': 'Необходимо указать селекторы для контейнера и элемента статьи'
        }
    
    # Получаем HTML страницы
    html = get_html(url, use_selenium)
    if not html:
        return {
            'success': False,
            'message': 'Не удалось загрузить страницу. Проверьте URL и настройки.'
        }
    
    # Извлекаем данные
    entries = extract_data_with_selectors(html, selectors, url)
    
    if not entries:
        return {
            'success': False,
            'message': 'Не удалось извлечь данные с указанными селекторами.'
        }
    
    return {
        'success': True,
        'entries': entries,
        'count': len(entries)
    }


def get_page_for_selector_setup(url, use_selenium=False):
    """
    Получает HTML страницы и добавляет дополнительные данные для настройки селекторов
    
    Args:
        url (str): URL страницы
        use_selenium (bool): Использовать ли Selenium
        
    Returns:
        str: HTML страницы с добавленным скриптом для выбора селекторов
    """
    html = get_html(url, use_selenium)
    if not html:
        return None
    
    # Добавляем базовый URL, если на странице его нет
    soup = BeautifulSoup(html, 'lxml')
    base_url = urlparse(url)
    base_tag = soup.find('base')
    
    if not base_tag:
        base_tag = soup.new_tag('base')
        base_tag['href'] = f"{base_url.scheme}://{base_url.netloc}"
        if soup.head:
            soup.head.insert(0, base_tag)
    
    # Можно добавить дополнительные скрипты или стили для улучшения интерактивности
    # Например, добавить скрипт, который позволит выбирать элементы и извлекать их селекторы
    
    return str(soup)


def auto_detect_selectors(url, use_selenium=False):
    """
    Автоматически определяет возможные селекторы для страницы
    
    Args:
        url (str): URL страницы
        use_selenium (bool): Использовать ли Selenium
        
    Returns:
        dict: Словарь с рекомендуемыми селекторами
    """
    html = get_html(url, use_selenium)
    if not html:
        return None
    
    soup = BeautifulSoup(html, 'lxml')
    
    # Поиск возможных контейнеров с повторяющимися элементами
    selectors = {}
    
    # Ищем контейнер на основе общих шаблонов
    container_candidates = [
        # Общие классы для контейнеров с новостями/статьями
        'div.news', 'div.articles', 'div.posts', 'div.feed', 'div.content',
        'section.news', 'section.articles', 'section.posts', 'section.content',
        # Семантические теги
        'main', 'article', 'section',
        # Общие ID для контейнеров
        '#content', '#main', '#news', '#posts', '#articles'
    ]
    
    # Проверяем каждый кандидат
    best_container = None
    max_item_count = 0
    
    for selector in container_candidates:
        try:
            container = soup.select_one(selector)
            if not container:
                continue
                
            # Ищем возможные элементы внутри контейнера
            for item_selector in ['article', 'div.item', 'div.post', 'div.entry', 'div.news-item', '.card']:
                items = container.select(item_selector)
                if len(items) > max_item_count:
                    max_item_count = len(items)
                    best_container = selector
                    selectors['container'] = selector
                    selectors['item'] = item_selector
        except:
            continue
    
    # Если не нашли подходящий контейнер, пробуем поискать по другим признакам
    if not best_container:
        # Ищем группы похожих элементов
        repeated_elements = find_repeated_elements(soup)
        if repeated_elements:
            selectors['container'] = repeated_elements['container']
            selectors['item'] = repeated_elements['item']
    
    # Если нашли контейнер и элементы, пробуем определить другие селекторы
    if selectors.get('container') and selectors.get('item'):
        container = soup.select_one(selectors['container'])
        if container:
            first_item = container.select_one(selectors['item'])
            if first_item:
                # Ищем заголовок
                for title_selector in ['h1', 'h2', 'h3', 'h4', '.title', '.heading']:
                    title = first_item.select_one(title_selector)
                    if title:
                        selectors['title'] = title_selector
                        break
                
                # Ищем ссылку
                link = first_item.select_one('a')
                if link:
                    selectors['link'] = 'a'
                
                # Ищем описание
                for desc_selector in ['p', '.description', '.summary', '.text', '.content', '.excerpt']:
                    desc = first_item.select_one(desc_selector)
                    if desc:
                        selectors['description'] = desc_selector
                        break
                
                # Ищем изображение
                img = first_item.select_one('img')
                if img:
                    selectors['image'] = 'img'
                
                # Ищем дату
                for date_selector in ['time', '.date', '.time', '.published', '.posted', '[datetime]']:
                    date = first_item.select_one(date_selector)
                    if date:
                        selectors['date'] = date_selector
                        break
    
    return selectors


def find_repeated_elements(soup):
    """
    Ищет повторяющиеся элементы на странице
    
    Args:
        soup (BeautifulSoup): Объект BeautifulSoup
        
    Returns:
        dict: Словарь с контейнером и селектором элемента
    """
    # Получаем все элементы страницы
    all_elements = soup.find_all(['div', 'article', 'section', 'li'])
    
    candidates = {}
    
    # Ищем элементы с одинаковым classname
    for element in all_elements:
        if not element.get('class'):
            continue
            
        class_name = ' '.join(element.get('class'))
        if class_name not in candidates:
            candidates[class_name] = []
            
        candidates[class_name].append(element)
    
    # Ищем наиболее повторяющиеся элементы
    best_candidates = []
    for class_name, elements in candidates.items():
        if len(elements) >= 3:  # Минимум 3 повторения
            best_candidates.append({
                'class_name': class_name,
                'count': len(elements),
                'elements': elements
            })
    
    # Сортируем по количеству повторений
    best_candidates.sort(key=lambda x: x['count'], reverse=True)
    
    if not best_candidates:
        return None
    
    # Берем лучшего кандидата
    best = best_candidates[0]
    
    # Ищем общего родителя для этих элементов
    parents = {}
    for element in best['elements']:
        parent = element.parent
        if not parent:
            continue
            
        parent_selector = get_selector_path(parent)
        if parent_selector not in parents:
            parents[parent_selector] = 0
            
        parents[parent_selector] += 1
    
    # Находим наиболее часто встречающегося родителя
    best_parent = max(parents.items(), key=lambda x: x[1])[0] if parents else None
    
    if not best_parent:
        return None
    
    # Определяем селектор для элемента
    element_selector = f".{best['class_name'].replace(' ', '.')}"
    
    return {
        'container': best_parent,
        'item': element_selector
    }


def get_selector_path(element, max_depth=3):
    """
    Создает селектор для элемента
    
    Args:
        element (Tag): Элемент BeautifulSoup
        max_depth (int): Максимальная глубина селектора
        
    Returns:
        str: CSS селектор
    """
    if not element or not element.name:
        return ''
    
    path = []
    current = element
    depth = 0
    
    while current and current.name and depth < max_depth:
        selector = current.name
        
        # Добавляем ID если есть
        if current.get('id'):
            selector += f"#{current.get('id')}"
            path.insert(0, selector)
            break
        
        # Добавляем класс если есть
        if current.get('class'):
            selector += f".{'.'.join(current.get('class'))}"
        
        path.insert(0, selector)
        current = current.parent
        depth += 1
    
    return ' > '.join(path)


def save_screenshot_for_selector(url, filename):
    """
    Сохраняет скриншот страницы для выбора селекторов
    
    Args:
        url (str): URL страницы
        filename (str): Имя файла для сохранения скриншота
        
    Returns:
        bool: Успешно ли сохранение
    """
    driver = None
    try:
        # Настройка опций Chrome
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        
        # Инициализация драйвера
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Загрузка страницы
        driver.get(url)
        time.sleep(3)  # Даем странице время загрузиться
        
        # Сохраняем скриншот
        screenshot_path = os.path.join(current_app.config['TEMP_FOLDER'], filename)
        driver.save_screenshot(screenshot_path)
        
        return True
    except Exception as e:
        logger.error(f"Error creating screenshot for {url}: {str(e)}")
        return False
    finally:
        if driver:
            driver.quit()


def get_element_info(url, css_selector):
    """
    Получает информацию об элементе по селектору
    
    Args:
        url (str): URL страницы
        css_selector (str): CSS селектор
        
    Returns:
        dict: Информация об элементе
    """
    try:
        html = get_html(url)
        if not html:
            return None
            
        soup = BeautifulSoup(html, 'lxml')
        element = soup.select_one(css_selector)
        
        if not element:
            return None
            
        # Получаем текст и атрибуты элемента
        text = element.get_text(strip=True)
        attrs = element.attrs
        
        return {
            'tag': element.name,
            'text': text[:100] + ('...' if len(text) > 100 else ''),
            'attributes': attrs,
            'html': str(element)[:500] + ('...' if len(str(element)) > 500 else '')
        }
    except Exception as e:
        logger.error(f"Error getting element info for {css_selector} at {url}: {str(e)}")
        return None

def get_page_structure(url):
    """
    Анализирует структуру страницы и предлагает возможные селекторы
    
    Args:
        url (str): URL страницы
        
    Returns:
        dict: Структура страницы и рекомендуемые селекторы
    """
    try:
        html = get_html(url)
        if not html:
            return None
            
        soup = BeautifulSoup(html, 'lxml')
        
        # Поиск возможных контейнеров с повторяющимися элементами
        suggestions = {
            'article': soup.find_all('article'),
            'div.item': soup.select('div.item'),
            'div.post': soup.select('div.post'),
            'li.news-item': soup.select('li.news-item'),
            'div.news': soup.select('div.news'),
            'div.entry': soup.select('div.entry'),
            'div.card': soup.select('div.card'),
            'div.col': soup.select('div[class*="col"]'),
            '.news-list > *': soup.select('.news-list > *'),
            'main > *': soup.select('main > *'),
            'section > *': soup.select('section > *')
        }
        
        # Находим самый подходящий селектор
        best_selector = None
        max_count = 0
        
        for selector, elements in suggestions.items():
            if len(elements) > max_count:
                max_count = len(elements)
                best_selector = selector
        
        # Дополнительный анализ для поиска статей
        articles_containers = {}
        for tag in ['div', 'section', 'main', 'ul']:
            containers = soup.find_all(tag)
            for container in containers:
                # Если контейнер содержит несколько похожих элементов, это может быть список статей
                children = container.find_all(recursive=False)
                if len(children) < 3:
                    continue
                    
                # Проверяем, содержат ли дочерние элементы ссылки или заголовки
                links_count = 0
                headers_count = 0
                
                for child in children:
                    if child.find('a'):
                        links_count += 1
                    if child.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                        headers_count += 1
                
                # Если большинство дочерних элементов содержат ссылки или заголовки,
                # это вероятно контейнер со статьями
                similarity_score = (links_count + headers_count) / len(children)
                if similarity_score > 0.5:
                    # Создаем селектор для контейнера
                    container_selector = get_selector_path(container)
                    articles_containers[container_selector] = {
                        'children_count': len(children),
                        'links_count': links_count,
                        'headers_count': headers_count,
                        'score': similarity_score
                    }
        
        # Сортируем контейнеры по количеству дочерних элементов и схожести
        sorted_containers = sorted(
            articles_containers.items(), 
            key=lambda x: (x[1]['score'], x[1]['children_count']), 
            reverse=True
        )
        
        # Если нашли подходящие контейнеры, используем лучший из них
        best_container = None
        if sorted_containers:
            best_container = sorted_containers[0][0]
        
        # Определяем итоговый контейнер
        recommended_container = best_container or best_selector or 'body'
        
        # Пытаемся определить селектор для элемента статьи
        item_selector = ''
        if recommended_container != 'body':
            container_element = soup.select_one(recommended_container)
            if container_element:
                # Берем первый дочерний элемент как образец
                children = container_element.find_all(recursive=False)
                if children:
                    first_child = children[0]
                    # Если у дочернего элемента есть тег и он не текстовый узел
                    if hasattr(first_child, 'name') and first_child.name:
                        # Создаем селектор относительно родителя
                        item_selector = first_child.name
                        # Добавляем класс, если есть
                        if first_child.get('class'):
                            item_selector += f".{'.'.join(first_child.get('class'))}"
        
        # Находим типичные элементы статей для предложения
        title_selectors = ['h1', 'h2', 'h3', 'h4', '.title', '.heading']
        link_selectors = ['a', 'a.title', 'h2 a', 'h3 a', '.title a']
        image_selectors = ['img', '.thumbnail img', '.image img', 'picture img']
        date_selectors = ['time', '.date', '.time', '[datetime]']
        
        # Проверяем наличие этих элементов
        has_title = any(len(soup.select(sel)) > 0 for sel in title_selectors)
        has_link = any(len(soup.select(sel)) > 0 for sel in link_selectors)
        has_image = any(len(soup.select(sel)) > 0 for sel in image_selectors)
        has_date = any(len(soup.select(sel)) > 0 for sel in date_selectors)
        
        return {
            'recommended_container': recommended_container,
            'recommended_item': item_selector,
            'element_counts': {selector: len(elements) for selector, elements in suggestions.items()},
            'has_article_tags': len(soup.find_all('article')) > 0,
            'containers': sorted_containers[:5] if sorted_containers else [],
            'has_title': has_title,
            'has_link': has_link,
            'has_image': has_image,
            'has_date': has_date
        }
    except Exception as e:
        logger.error(f"Error analyzing page structure for {url}: {str(e)}")
        return None