import feedparser
from datetime import datetime
import pytz
from dateutil import parser as date_parser
import logging
from .storage import db, Feed, FeedItem, AggregatedFeed
from flask import current_app

logger = logging.getLogger(__name__)

def fetch_rss_feed(feed_url):
    """
    Парсит RSS-ленту по указанному URL
    
    Args:
        feed_url (str): URL RSS-ленты
        
    Returns:
        dict: Словарь с заголовком, описанием и элементами ленты
    """
    try:
        parsed_feed = feedparser.parse(feed_url)
        
        # Проверка на наличие ошибок
        if hasattr(parsed_feed, 'bozo_exception'):
            logger.error(f"Error parsing feed {feed_url}: {parsed_feed.bozo_exception}")
            return None
            
        feed_data = {
            'title': parsed_feed.feed.get('title', 'Untitled Feed'),
            'description': parsed_feed.feed.get('description', ''),
            'entries': []
        }
        
        for entry in parsed_feed.entries:
            # Обработка даты публикации
            published = None
            if hasattr(entry, 'published'):
                try:
                    published = date_parser.parse(entry.published)
                except:
                    pass
            elif hasattr(entry, 'updated'):
                try:
                    published = date_parser.parse(entry.updated)
                except:
                    pass
                    
            # Если дата не найдена, используем текущую
            if not published:
                published = datetime.utcnow()
                
            # Если дата без временной зоны, предполагаем UTC
            if published.tzinfo is None:
                published = pytz.UTC.localize(published)
                
            # Преобразуем в UTC для хранения
            published = published.astimezone(pytz.UTC).replace(tzinfo=None)
            
            # Подготовка данных элемента
            item = {
                'title': entry.get('title', 'Untitled'),
                'link': entry.get('link', ''),
                'description': entry.get('description', entry.get('summary', '')),
                'guid': entry.get('id', entry.get('link', '')),
                'published': published
            }
            
            feed_data['entries'].append(item)
            
        return feed_data
    except Exception as e:
        logger.error(f"Error fetching feed {feed_url}: {str(e)}")
        return None


def update_feed(feed):
    """
    Обновляет элементы для конкретной ленты
    
    Args:
        feed (Feed): Объект ленты из БД
    
    Returns:
        bool: Успешно ли обновление
    """
    try:
        print(f"Обновление ленты: {feed.name} (тип: {feed.feed_type})")
        if feed.feed_type == 'rss':
            feed_data = fetch_rss_feed(feed.url)
            print(f"Данные RSS получены: {feed_data is not None}")
        else:
            # Для лент на основе скрапинга используем другой модуль
            from .scraper import scrape_feed
            print(f"Запуск скрапинга для ленты: {feed.name}")
            feed_data = scrape_feed(feed)
            print(f"Результат скрапинга: {feed_data is not None}")
            
        if not feed_data:
            print(f"Нет данных для ленты: {feed.name}")
            return False
            
        print(f"Количество элементов: {len(feed_data['entries'])}")
        
        # Обновление элементов ленты
        new_count = 0
        for entry in feed_data['entries']:
            # Проверяем существование элемента по GUID
            existing_item = FeedItem.query.filter_by(
                feed_id=feed.id, 
                guid=entry['guid']
            ).first()
            
            if not existing_item:
                # Если published - строка, преобразуем ее в datetime
                if isinstance(entry['published'], str):
                    try:
                        from datetime import datetime
                        published = datetime.strptime(entry['published'], '%Y-%m-%d %H:%M:%S')
                    except:
                        published = datetime.utcnow()
                else:
                    published = entry['published']

                # Создаем новый элемент
                new_item = FeedItem(
                    feed_id=feed.id,
                    title=entry['title'],
                    link=entry['link'],
                    description=entry['description'],
                    guid=entry['guid'],
                    published=published
                )
                db.session.add(new_item)
                new_count += 1
                
        # Обновляем время последнего обновления ленты
        feed.last_updated = datetime.utcnow()
        db.session.commit()
        
        print(f"Лента {feed.name} обновлена: {new_count} новых элементов")
        return True
    except Exception as e:
        db.session.rollback()
        print(f"Ошибка при обновлении ленты {feed.name}: {str(e)}")
        logger.error(f"Error updating feed {feed.name}: {str(e)}")
        return False

def update_all_feeds():
    """Обновляет все активные ленты"""
    feeds = Feed.query.filter_by(active=True).all()
    for feed in feeds:
        update_feed(feed)
        
    # Обновляем время последнего обновления для агрегированных лент
    aggregated_feeds = AggregatedFeed.query.filter_by(active=True).all()
    for agg_feed in aggregated_feeds:
        agg_feed.last_updated = datetime.utcnow()
    db.session.commit()


def get_aggregated_feed_items(aggregated_feed, limit=None, page=None, per_page=None):
    """
    Получает элементы для агрегированной ленты
    
    Args:
        aggregated_feed (AggregatedFeed): Объект агрегированной ленты
        limit (int, optional): Ограничение количества элементов
        page (int, optional): Номер страницы (для пагинации)
        per_page (int, optional): Элементов на страницу
        
    Returns:
        list: Список объектов FeedItem
    """
    feed_ids = [feed.id for feed in aggregated_feed.feeds.filter_by(active=True).all()]
    
    if not feed_ids:
        return []
        
    # Запрос для получения элементов из всех лент, отсортированных по дате
    query = FeedItem.query.filter(FeedItem.feed_id.in_(feed_ids)).order_by(FeedItem.published.desc())
    
    # Пагинация или лимит
    if page and per_page:
        # В SQLAlchemy 1.4 с Flask-SQLAlchemy 2.5.1 метод paginate имеет другую сигнатуру
        return query.paginate(page, per_page, error_out=False)
    elif limit:
        return query.limit(limit).all()
    else:
        return query.all()