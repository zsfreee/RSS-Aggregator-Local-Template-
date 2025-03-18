from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class Feed(db.Model):
    """Модель для хранения информации о лентах RSS"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    feed_type = db.Column(db.String(50), nullable=False)  # 'rss', 'scrape'
    url = db.Column(db.String(500), nullable=False)
    active = db.Column(db.Boolean, default=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Для скрапинга на основе CSS селекторов
    selectors = db.Column(db.Text, nullable=True)  # JSON строка с селекторами
    
    # Для работы с агрегированными лентами
    included_in_aggregate = db.Column(db.Boolean, default=True)
    
    items = db.relationship('FeedItem', backref='feed', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Feed {self.name}>'
    
    def get_selectors(self):
        """Возвращает словарь селекторов"""
        if self.selectors:
            return json.loads(self.selectors)
        return {}
    
    def set_selectors(self, selectors_dict):
        """Сохраняет словарь селекторов как JSON"""
        self.selectors = json.dumps(selectors_dict)


class FeedItem(db.Model):
    """Модель для хранения элементов ленты"""
    id = db.Column(db.Integer, primary_key=True)
    feed_id = db.Column(db.Integer, db.ForeignKey('feed.id'), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    link = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text, nullable=True)
    guid = db.Column(db.String(500), nullable=True)
    published = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<FeedItem {self.title}>'


class AggregatedFeed(db.Model):
    """Модель для хранения агрегированных лент"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    active = db.Column(db.Boolean, default=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связь многие-ко-многим с Feed
    feeds = db.relationship('Feed', 
                           secondary='aggregated_feed_association',
                           backref=db.backref('aggregated_feeds', lazy='dynamic'),
                           lazy='dynamic')
    
    def __repr__(self):
        return f'<AggregatedFeed {self.name}>'


# Таблица связи между AggregatedFeed и Feed
aggregated_feed_association = db.Table('aggregated_feed_association',
    db.Column('aggregated_feed_id', db.Integer, db.ForeignKey('aggregated_feed.id'), primary_key=True),
    db.Column('feed_id', db.Integer, db.ForeignKey('feed.id'), primary_key=True)
)


def init_db(app):
    """Инициализация базы данных"""
    db.init_app(app)
    with app.app_context():
        db.create_all()