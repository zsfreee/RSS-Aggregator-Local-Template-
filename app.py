import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, abort
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, URL, Optional
import datetime
from slugify import slugify
from apscheduler.schedulers.background import BackgroundScheduler

from config import config
from modules.storage import init_db, db, Feed, FeedItem, AggregatedFeed
from modules.aggregator import update_feed, update_all_feeds, fetch_rss_feed
from modules.feed_generator import generate_aggregated_feed, generate_single_feed
from modules.scraper import (
    get_page_structure, 
    get_element_info, 
    save_screenshot_for_selector,
    test_selectors,
    auto_detect_selectors,
    get_page_for_selector_setup
)

# Создаем приложение
app = Flask(__name__)

# Загружаем конфигурацию
env = os.environ.get('FLASK_ENV', 'default')
app.config.from_object(config[env])
config[env].init_app(app)

# Инициализируем базу данных
init_db(app)

# Формы
class FeedForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired()])
    url = StringField('URL', validators=[DataRequired(), URL()])
    feed_type = SelectField('Тип ленты', choices=[
        ('rss', 'RSS-лента'),
        ('scrape', 'Сайт без RSS (парсинг)')
    ])
    active = BooleanField('Активна', default=True)
    included_in_aggregate = BooleanField('Включать в общую ленту', default=True)
    submit = SubmitField('Сохранить')


class AggregatedFeedForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired()])
    description = TextAreaField('Описание', validators=[Optional()])
    active = BooleanField('Активна', default=True)
    submit = SubmitField('Сохранить')


# Планировщик для автоматического обновления лент
scheduler = BackgroundScheduler()
scheduler.add_job(
    update_all_feeds,
    'interval',
    seconds=app.config['UPDATE_INTERVAL'],
    id='update_feeds'
)
scheduler.start()


@app.route('/')
def index():
    """Главная страница - панель управления"""
    feeds = Feed.query.all()
    aggregated_feeds = AggregatedFeed.query.all()
    return render_template(
        'dashboard.html', 
        feeds=feeds, 
        aggregated_feeds=aggregated_feeds
    )


@app.route('/feeds/add', methods=['GET', 'POST'])
def add_feed():
    """Добавление новой ленты"""
    form = FeedForm()
    
    if form.validate_on_submit():
        new_feed = Feed(
            name=form.name.data,
            url=form.url.data,
            feed_type=form.feed_type.data,
            active=form.active.data,
            included_in_aggregate=form.included_in_aggregate.data
        )
        
        db.session.add(new_feed)
        db.session.commit()
        
        # Если это RSS-лента, пробуем сразу обновить
        if form.feed_type.data == 'rss':
            success = update_feed(new_feed)
            if not success:
                flash('Лента создана, но не удалось загрузить данные. Проверьте URL.', 'warning')
            else:
                flash('Лента успешно создана и обновлена!', 'success')
        else:
            # Для лент на основе парсинга перенаправляем на страницу выбора селекторов
            flash('Лента создана. Теперь настройте селекторы для парсинга.', 'info')
            return redirect(url_for('setup_selectors', feed_id=new_feed.id))
            
        return redirect(url_for('index'))
    
    return render_template('feed_form.html', form=form, title='Добавить ленту')


@app.route('/feeds/<int:feed_id>/edit', methods=['GET', 'POST'])
def edit_feed(feed_id):
    """Редактирование ленты"""
    feed = Feed.query.get_or_404(feed_id)
    form = FeedForm(obj=feed)
    
    if form.validate_on_submit():
        form.populate_obj(feed)
        db.session.commit()
        
        flash('Лента успешно обновлена!', 'success')
        return redirect(url_for('index'))
    
    return render_template('feed_form.html', form=form, title='Редактировать ленту')


@app.route('/feeds/<int:feed_id>/delete', methods=['POST'])
def delete_feed(feed_id):
    """Удаление ленты"""
    feed = Feed.query.get_or_404(feed_id)
    db.session.delete(feed)
    db.session.commit()
    
    flash('Лента успешно удалена!', 'success')
    return redirect(url_for('index'))


@app.route('/feeds/<int:feed_id>/update', methods=['POST'])
def manual_update_feed(feed_id):
    """Ручное обновление ленты"""
    feed = Feed.query.get_or_404(feed_id)
    success = update_feed(feed)
    
    # Получаем URL, с которого пришел запрос
    referer = request.referrer
    
    if success:
        flash('Лента успешно обновлена!', 'success')
    else:
        flash('Не удалось обновить ленту. Проверьте настройки.', 'danger')
    
    # Если известен referer и он относится к нашему приложению, возвращаемся туда
    if referer and referer.startswith(request.host_url):
        return redirect(referer)
    
    # Иначе перенаправляем на страницу просмотра ленты
    return redirect(url_for('view_feed', feed_id=feed_id))


@app.route('/feeds/<int:feed_id>/view')
def view_feed(feed_id):
    """Просмотр элементов ленты"""
    feed = Feed.query.get_or_404(feed_id)
    page = request.args.get('page', 1, type=int)
    per_page = app.config['ITEMS_PER_PAGE']
    
    items = FeedItem.query.filter_by(feed_id=feed.id) \
                          .order_by(FeedItem.published.desc()) \
                          .paginate(page, per_page, error_out=False)
                          
    return render_template('feed_details.html', feed=feed, items=items)


@app.route('/feeds/<int:feed_id>/setup_selectors', methods=['GET', 'POST'])
def setup_selectors(feed_id):
    """Настройка селекторов для парсинга"""
    feed = Feed.query.get_or_404(feed_id)
    
    # Убеждаемся, что лента предназначена для парсинга
    if feed.feed_type != 'scrape':
        flash('Эта лента не требует настройки селекторов', 'warning')
        return redirect(url_for('index'))
    
    # Получаем текущие селекторы
    selectors = feed.get_selectors() or {}
    
    if request.method == 'POST':
        print(f"Получен POST-запрос для настройки селекторов ленты {feed.name}")
        # Обновляем селекторы
        new_selectors = {
            'container': request.form.get('container'),
            'item': request.form.get('item'),
            'title': request.form.get('title'),
            'link': request.form.get('link'),
            'description': request.form.get('description'),
            'image': request.form.get('image'),
            'date': request.form.get('date'),
            'use_selenium': 'use_selenium' in request.form
        }
        
        print(f"Новые селекторы: {new_selectors}")
        feed.set_selectors(new_selectors)
        db.session.commit()
        print(f"Селекторы сохранены в базе данных")
        
        # Пробуем обновить ленту с новыми селекторами
        print(f"Запускаем обновление ленты {feed.name}")
        success = update_feed(feed)
        print(f"Результат обновления: {success}")
        
        if success:
            flash('Селекторы успешно настроены и лента обновлена!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Селекторы сохранены, но не удалось обновить ленту. Проверьте настройки.', 'warning')
    
    # Анализируем структуру страницы для предложения селекторов
    page_structure = get_page_structure(feed.url)
    
    # Добавляем информацию о ссылке на RSS-ленту
    rss_url = url_for('get_source_feed', feed_id=feed.id, _external=True)
    
    return render_template(
        'selector.html', 
        feed=feed, 
        selectors=selectors,
        page_structure=page_structure,
        rss_url=rss_url
    )


@app.route('/api/proxy_page', methods=['POST'])
def proxy_page():
    """API для получения HTML страницы через прокси"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Data not provided'}), 400
    
    url = data.get('url')
    use_selenium = data.get('use_selenium', False)
    
    if not url:
        return jsonify({'error': 'URL not provided'}), 400
        
    # Получаем HTML страницы с подготовкой для выбора селекторов
    html = get_page_for_selector_setup(url, use_selenium)
    if not html:
        return jsonify({'error': 'Failed to fetch page'}), 500
        
    # Возвращаем HTML
    return html


@app.route('/api/test_selectors', methods=['POST'])
def api_test_selectors():
    """API для тестирования селекторов"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Data not provided'}), 400
    
    url = data.get('url')
    selectors = data.get('selectors', {})
    use_selenium = data.get('use_selenium', False)
    
    if not url:
        return jsonify({'error': 'URL not provided'}), 400
    
    if not selectors or not selectors.get('container') or not selectors.get('item'):
        return jsonify({
            'success': False,
            'message': 'Missing required selectors: container and item'
        }), 200
    
    # Тестируем селекторы
    result = test_selectors(url, selectors, use_selenium)
    
    return jsonify(result)


@app.route('/api/auto_detect_selectors', methods=['POST'])
def auto_detect_selectors_api():
    """API для автоматического определения селекторов"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Data not provided'}), 400
    
    url = data.get('url')
    use_selenium = data.get('use_selenium', False)
    
    if not url:
        return jsonify({'error': 'URL not provided'}), 400
    
    # Автоматически определяем селекторы
    selectors = auto_detect_selectors(url, use_selenium)
    
    if not selectors:
        return jsonify({
            'success': False,
            'message': 'Could not detect selectors automatically'
        }), 200
    
    return jsonify({
        'success': True,
        'selectors': selectors
    })


@app.route('/api/page_info', methods=['POST'])
def page_info():
    """API для получения информации о странице"""
    data = request.get_json()
    url = data.get('url') if data else None
    
    if not url:
        return jsonify({'error': 'URL not provided'}), 400
        
    structure = get_page_structure(url)
    if not structure:
        return jsonify({'error': 'Failed to analyze page'}), 500
        
    return jsonify(structure)


@app.route('/api/element_info', methods=['POST'])
def element_info():
    """API для получения информации об элементе"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Data not provided'}), 400
    
    url = data.get('url')
    selector = data.get('selector')
    
    if not url or not selector:
        return jsonify({'error': 'URL or selector not provided'}), 400
        
    info = get_element_info(url, selector)
    if not info:
        return jsonify({'error': 'Element not found'}), 404
        
    return jsonify(info)


@app.route('/aggregate/add', methods=['GET', 'POST'])
def add_aggregated_feed():
    """Добавление новой агрегированной ленты"""
    form = AggregatedFeedForm()
    
    if form.validate_on_submit():
        # Создаем уникальный slug
        slug = slugify(form.name.data)
        
        # Проверяем уникальность slug
        existing = AggregatedFeed.query.filter_by(slug=slug).first()
        if existing:
            slug = f"{slug}-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        new_feed = AggregatedFeed(
            name=form.name.data,
            description=form.description.data,
            slug=slug,
            active=form.active.data
        )
        
        # Добавляем все активные ленты, отмеченные для включения в агрегированные
        feeds = Feed.query.filter_by(active=True, included_in_aggregate=True).all()
        for feed in feeds:
            new_feed.feeds.append(feed)
        
        db.session.add(new_feed)
        db.session.commit()
        
        flash('Агрегированная лента успешно создана!', 'success')
        return redirect(url_for('index'))
    
    return render_template('aggregated_feed_form.html', form=form, title='Добавить агрегированную ленту')


@app.route('/aggregate/<int:agg_id>/edit', methods=['GET', 'POST'])
def edit_aggregated_feed(agg_id):
    """Редактирование агрегированной ленты"""
    agg_feed = AggregatedFeed.query.get_or_404(agg_id)
    form = AggregatedFeedForm(obj=agg_feed)
    
    if form.validate_on_submit():
        agg_feed.name = form.name.data
        agg_feed.description = form.description.data
        agg_feed.active = form.active.data
        
        db.session.commit()
        
        flash('Агрегированная лента успешно обновлена!', 'success')
        return redirect(url_for('index'))
    
    return render_template('aggregated_feed_form.html', form=form, title='Редактировать агрегированную ленту')


@app.route('/aggregate/<int:agg_id>/feeds', methods=['GET', 'POST'])
def manage_aggregated_feed_sources(agg_id):
    """Управление источниками для агрегированной ленты"""
    agg_feed = AggregatedFeed.query.get_or_404(agg_id)
    
    if request.method == 'POST':
        # Обновляем список источников
        feed_ids = request.form.getlist('feed_ids', type=int)
        
        # Очищаем текущие источники
        agg_feed.feeds = []
        
        # Добавляем выбранные источники
        for feed_id in feed_ids:
            feed = Feed.query.get(feed_id)
            if feed:
                agg_feed.feeds.append(feed)
        
        db.session.commit()
        
        flash('Источники агрегированной ленты обновлены!', 'success')
        return redirect(url_for('index'))
    
    # Получаем все доступные ленты
    all_feeds = Feed.query.filter_by(active=True).all()
    
    # Получаем ID лент, уже включенных в агрегированную ленту
    included_feed_ids = [feed.id for feed in agg_feed.feeds]
    
    return render_template(
        'manage_sources.html', 
        agg_feed=agg_feed, 
        all_feeds=all_feeds,
        included_feed_ids=included_feed_ids
    )


@app.route('/aggregate/<int:agg_id>/delete', methods=['POST'])
def delete_aggregated_feed(agg_id):
    """Удаление агрегированной ленты"""
    agg_feed = AggregatedFeed.query.get_or_404(agg_id)
    db.session.delete(agg_feed)
    db.session.commit()
    
    flash('Агрегированная лента успешно удалена!', 'success')
    return redirect(url_for('index'))


@app.route('/aggregate/<int:agg_id>/view')
def view_aggregated_feed(agg_id):
    """Просмотр элементов агрегированной ленты"""
    from modules.aggregator import get_aggregated_feed_items
    
    agg_feed = AggregatedFeed.query.get_or_404(agg_id)
    page = request.args.get('page', 1, type=int)
    per_page = app.config['ITEMS_PER_PAGE']
    
    items_pagination = get_aggregated_feed_items(
        agg_feed, 
        page=page, 
        per_page=per_page
    )
    
    return render_template(
        'aggregated_feed_details.html', 
        agg_feed=agg_feed, 
        items=items_pagination
    )


@app.route('/feed/<slug>')
def get_public_feed(slug):
    """Публичный доступ к агрегированной ленте"""
    agg_feed = AggregatedFeed.query.filter_by(slug=slug, active=True).first_or_404()
    
    xml = generate_aggregated_feed(
        agg_feed, 
        app.config['BASE_URL']
    )
    
    return Response(xml, mimetype='application/rss+xml')


@app.route('/source/<int:feed_id>')
def get_source_feed(feed_id):
    """Публичный доступ к исходной ленте"""
    feed = Feed.query.filter_by(id=feed_id, active=True).first_or_404()
    
    xml = generate_single_feed(
        feed, 
        app.config['BASE_URL']
    )
    
    return Response(xml, mimetype='application/rss+xml')


@app.route('/api/check_rss', methods=['POST'])
def check_rss():
    """API для проверки RSS-ленты"""
    data = request.get_json()
    url = data.get('url') if data else None
    
    if not url:
        return jsonify({'error': 'URL not provided'}), 400
        
    feed_data = fetch_rss_feed(url)
    if not feed_data:
        return jsonify({'valid': False, 'message': 'Не удалось загрузить или распознать RSS-ленту'}), 200
        
    return jsonify({
        'valid': True,
        'title': feed_data['title'],
        'description': feed_data['description'],
        'item_count': len(feed_data['entries'])
    }), 200


@app.route('/update_all', methods=['POST'])
def trigger_update_all():
    """Ручное обновление всех лент"""
    update_all_feeds()
    flash('Все ленты обновлены!', 'success')
    return redirect(url_for('index'))


@app.teardown_appcontext
def shutdown_scheduler(exception=None):
    """Остановка планировщика при завершении работы приложения"""
    if scheduler.running:
        scheduler.shutdown()


# Запуск приложения
if __name__ == '__main__':
    app.run(debug=True)
