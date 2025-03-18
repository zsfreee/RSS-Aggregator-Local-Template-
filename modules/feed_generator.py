import feedgenerator
from datetime import datetime
import pytz
from flask import url_for
from .storage import Feed, FeedItem, AggregatedFeed
import logging

logger = logging.getLogger(__name__)

def generate_feed(items, title, description, link, language='ru'):
    """
    Создает RSS-ленту из списка элементов
    
    Args:
        items (list): Список объектов FeedItem
        title (str): Заголовок ленты
        description (str): Описание ленты
        link (str): Ссылка на ленту
        language (str): Язык ленты
        
    Returns:
        str: XML-представление ленты RSS
    """
    try:
        # Создаем объект канала RSS
        feed = feedgenerator.Rss201rev2Feed(
            title=title,
            link=link,
            description=description,
            language=language,
            lastBuildDate=datetime.utcnow().replace(tzinfo=pytz.UTC)
        )
        
        # Добавляем элементы в ленту
        for item in items:
            # Устанавливаем дату публикации (с учетом временной зоны)
            pubdate = item.published
            if pubdate and pubdate.tzinfo is None:
                pubdate = pubdate.replace(tzinfo=pytz.UTC)
            elif not pubdate:
                pubdate = datetime.utcnow().replace(tzinfo=pytz.UTC)
                
            feed.add_item(
                title=item.title,
                link=item.link,
                description=item.description,
                pubdate=pubdate,
                unique_id=item.guid or item.link
            )
            
        # Генерируем XML
        return feed.writeString('utf-8')
    except Exception as e:
        logger.error(f"Error generating feed: {str(e)}")
        return None


def generate_aggregated_feed(aggregated_feed, base_url, limit=50):
    """
    Создает агрегированную RSS-ленту
    
    Args:
        aggregated_feed (AggregatedFeed): Объект агрегированной ленты
        base_url (str): Базовый URL приложения
        limit (int): Ограничение количества элементов
        
    Returns:
        str: XML-представление агрегированной ленты RSS
    """
    from .aggregator import get_aggregated_feed_items
    
    # Получаем элементы для агрегированной ленты
    items = get_aggregated_feed_items(aggregated_feed, limit=limit)
    
    # Формируем ссылку на ленту
    link = f"{base_url}/feed/{aggregated_feed.slug}"
    
    # Генерируем ленту
    return generate_feed(
        items, 
        aggregated_feed.name, 
        aggregated_feed.description or f"Aggregated feed: {aggregated_feed.name}",
        link
    )


def generate_single_feed(feed, base_url, limit=50):
    """
    Создает RSS-ленту для одиночного источника
    
    Args:
        feed (Feed): Объект ленты
        base_url (str): Базовый URL приложения
        limit (int): Ограничение количества элементов
        
    Returns:
        str: XML-представление ленты RSS
    """
    # Получаем элементы для ленты
    items = FeedItem.query.filter_by(feed_id=feed.id).order_by(FeedItem.published.desc()).limit(limit).all()
    
    # Формируем ссылку на ленту
    link = f"{base_url}/source/{feed.id}"
    
    # Генерируем ленту
    return generate_feed(
        items, 
        feed.name, 
        f"Feed: {feed.name}", 
        link
    )