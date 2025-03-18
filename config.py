import os

class Config:
    # Базовый класс конфигурации
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'
    
    # База данных SQLite
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'rss_aggregator.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Настройки для RSS-лент
    RSS_FEED_TITLE = "Агрегированная RSS-лента"
    RSS_FEED_DESCRIPTION = "Лента, созданная RSS Aggregator"
    RSS_FEED_LANGUAGE = "ru"
    
    # Настройки для обновления данных (в секундах)
    UPDATE_INTERVAL = 3600  # Обновлять RSS каждый час
    
    # Количество элементов на страницу
    ITEMS_PER_PAGE = 20
    
    # Директория для хранения временных файлов
    TEMP_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'temp')
    
    # URL-префикс для создаваемых RSS-лент
    BASE_URL = os.environ.get('BASE_URL') or 'http://localhost:5000'
    
    # Настройки для Selenium (если используется)
    HEADLESS_BROWSER = True
    
    @staticmethod
    def init_app(app):
        # Создаем необходимые директории
        os.makedirs(Config.TEMP_FOLDER, exist_ok=True)


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}