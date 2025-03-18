/**
 * Скрипт для интерактивного выбора CSS селекторов (аналог rss.app)
 */

document.addEventListener('DOMContentLoaded', function() {
    // Элементы интерфейса
    const previewUrl = document.getElementById('preview-url');
    const previewIframe = document.getElementById('preview-iframe');
    const previewContainer = document.getElementById('preview-container');
    const loadPreviewBtn = document.getElementById('load-preview');
    const autoModeSwitch = document.getElementById('autoMode');
    const testSelectorsBtn = document.getElementById('test-selectors');
    const resetSelectorsBtn = document.getElementById('reset-selectors');
    const selectElementBtns = document.querySelectorAll('.select-element-btn');
    const loadingIndicator = document.getElementById('preview-loading');
    const previewError = document.getElementById('preview-error');
    const previewInfo = document.getElementById('preview-info');
    const extractedItems = document.getElementById('extracted-items');
    const matchingEntries = document.getElementById('matching-entries');
    const entriesCount = document.getElementById('entries-count');
    
    // Селекторы полей
    const selectors = {
        container: document.getElementById('container'),
        item: document.getElementById('item'),
        title: document.getElementById('title'),
        link: document.getElementById('link'),
        description: document.getElementById('description'),
        image: document.getElementById('image'),
        date: document.getElementById('date')
    };
    
    // Цвета для выделения элементов
    const highlightClasses = {
        container: 'selector-container',
        item: 'selector-item',
        title: 'selector-title',
        link: 'selector-link',
        description: 'selector-description',
        image: 'selector-image',
        date: 'selector-date'
    };
    
    // Состояние приложения
    let isSelectionMode = false;
    let currentSelectionTarget = null;
    let lastHoveredElement = null;
    let foundEntries = [];
    let selectedEntries = [];
    
    /**
     * Загрузка предварительного просмотра
     */
    function loadPreview() {
        const url = previewUrl.value.trim();
        
        if (!url) {
            showError('Пожалуйста, введите URL для предварительного просмотра');
            return;
        }
        
        // Сбрасываем состояние и показываем индикатор загрузки
        resetHighlights();
        previewIframe.src = '';
        previewError.style.display = 'none';
        previewInfo.style.display = 'block';
        loadingIndicator.style.display = 'block';
        
        // Запрашиваем страницу через прокси
        fetch('/api/proxy_page', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                url: url,
                use_selenium: document.getElementById('use_selenium').checked
            }),
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Ошибка запроса: ${response.status}`);
            }
            return response.text();
        })
        .then(html => {
            // Создаем Blob и URL для него
            const blob = new Blob([html], { type: 'text/html' });
            const blobUrl = URL.createObjectURL(blob);
            
            // Загружаем HTML в iframe
            previewIframe.onload = function() {
                loadingIndicator.style.display = 'none';
                
                try {
                    setupIframeInteractivity();
                    
                    // Если есть заполненные селекторы, подсвечиваем их
                    highlightCurrentSelectors();
                    
                    // Автоматически определяем селекторы, если не указаны
                    if (autoModeSwitch.checked && !selectors.container.value && !selectors.item.value) {
                        autoDetectSelectors();
                    }
                } catch (error) {
                    console.error('Ошибка при настройке iframe:', error);
                    showError('Не удалось инициализировать предпросмотр. Возможно, страница блокирует доступ');
                }
            };
            
            previewIframe.onerror = function() {
                loadingIndicator.style.display = 'none';
                showError('Не удалось загрузить контент. Проверьте URL и попробуйте снова');
            };
            
            // Загружаем blob в iframe
            previewIframe.src = blobUrl;
        })
        .catch(error => {
            loadingIndicator.style.display = 'none';
            showError(`Ошибка при загрузке предпросмотра: ${error.message}`);
        });
    }
    
    /**
     * Настройка интерактивности iframe
     */
    function setupIframeInteractivity() {
        const iframeDoc = previewIframe.contentDocument || previewIframe.contentWindow.document;
        
        // Добавляем стили для подсветки элементов
        const styleElement = document.createElement('style');
        styleElement.textContent = `
            * {
                cursor: pointer !important;
            }
            
            .hover-highlight {
                outline: 2px dashed #fd7e14 !important;
                background-color: rgba(253, 126, 20, 0.1) !important;
            }
            
            .selector-container {
                outline: 3px solid rgba(255, 193, 7, 0.8) !important;
                background-color: rgba(255, 193, 7, 0.1) !important;
            }
            
            .selector-item {
                outline: 3px solid rgba(13, 110, 253, 0.8) !important;
                background-color: rgba(13, 110, 253, 0.1) !important;
            }
            
            .selector-title {
                outline: 3px solid rgba(25, 135, 84, 0.8) !important;
                background-color: rgba(25, 135, 84, 0.1) !important;
            }
            
            .selector-link {
                outline: 3px solid rgba(13, 202, 240, 0.8) !important;
                background-color: rgba(13, 202, 240, 0.1) !important;
            }
            
            .selector-description {
                outline: 3px solid rgba(108, 117, 125, 0.8) !important;
                background-color: rgba(108, 117, 125, 0.1) !important;
            }
            
            .selector-image {
                outline: 3px solid rgba(220, 53, 69, 0.8) !important;
                background-color: rgba(220, 53, 69, 0.1) !important;
            }
            
            .selector-date {
                outline: 3px solid rgba(111, 66, 193, 0.8) !important;
                background-color: rgba(111, 66, 193, 0.1) !important;
            }
        `;
        iframeDoc.head.appendChild(styleElement);
        
        // Добавляем обработчики событий
        const allElements = iframeDoc.querySelectorAll('*');
        allElements.forEach(el => {
            // Игнорируем html, body, head, script и т.д.
            if (['HTML', 'BODY', 'HEAD', 'SCRIPT', 'STYLE', 'LINK', 'META'].includes(el.tagName)) {
                return;
            }
            
            // Обработчик наведения мыши
            el.addEventListener('mouseover', function(e) {
                e.stopPropagation();
                
                // Снимаем подсветку с предыдущего элемента
                if (lastHoveredElement && lastHoveredElement !== this) {
                    lastHoveredElement.classList.remove('hover-highlight');
                }
                
                // Подсвечиваем текущий элемент
                this.classList.add('hover-highlight');
                lastHoveredElement = this;
            });
            
            // Обработчик клика
            el.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                // Если включен режим выбора конкретного элемента
                if (isSelectionMode && currentSelectionTarget) {
                    selectElementForTarget(this, currentSelectionTarget);
                    return false;
                }
                
                // Если автоматический режим, определяем все селекторы
                if (autoModeSwitch.checked) {
                    // Автоматически определяем селекторы для всех нужных частей
                    const autoSelectors = getSelectorsFromElement(this);
                    applyDetectedSelectors(autoSelectors);
                    
                    // Подсвечиваем выбранные элементы
                    highlightCurrentSelectors();
                    
                    // Тестируем селекторы
                    testSelectors();
                } else {
                    // В ручном режиме просто предлагаем выбрать тип элемента
                    detectElementType(this);
                }
                
                return false;
            });
        });
    }
    
    /**
     * Генерация CSS селектора для элемента
     * @param {Element} element DOM элемент
     * @param {boolean} optimize Оптимизировать ли селектор
     * @returns {string} CSS селектор
     */
    function generateSelector(element, optimize = true) {
        if (!element) return '';
        
        // Базовый селектор с тегом, ID и классами
        const tag = element.tagName.toLowerCase();
        const id = element.id ? `#${element.id}` : '';
        const classes = Array.from(element.classList)
            .filter(cls => !cls.includes('hover-highlight') && !cls.includes('selector-'))
            .join('.');
        
        // Если у элемента есть ID, используем его (самый специфичный селектор)
        if (id) {
            return id;
        }
        
        // Если есть классы, используем их с тегом
        if (classes) {
            return `${tag}.${classes}`;
        }
        
        // Если нужно оптимизировать и нет ID/классов, создаем путь селекторов
        if (optimize) {
            const path = [];
            let current = element;
            let depth = 0;
            const maxDepth = 4; // Ограничение глубины пути
            
            while (current && current.tagName && depth < maxDepth) {
                let currentSelector = current.tagName.toLowerCase();
                
                // Добавляем ID если есть
                if (current.id) {
                    currentSelector = `#${current.id}`;
                    path.unshift(currentSelector);
                    break;
                }
                
                // Добавляем классы если есть
                const currentClasses = Array.from(current.classList)
                    .filter(cls => !cls.includes('hover-highlight') && !cls.includes('selector-'))
                    .join('.');
                
                if (currentClasses) {
                    currentSelector += `.${currentClasses}`;
                }
                
                // Если есть несколько одинаковых элементов, добавляем :nth-child
                const siblings = Array.from(current.parentNode?.children || [])
                    .filter(sibling => sibling.tagName === current.tagName);
                
                if (siblings.length > 1) {
                    const index = siblings.indexOf(current) + 1;
                    if (index > 0) {
                        currentSelector += `:nth-child(${index})`;
                    }
                }
                
                path.unshift(currentSelector);
                current = current.parentNode;
                depth++;
            }
            
            return path.join(' > ');
        }
        
        // Простой селектор с тегом
        return tag;
    }
    
    /**
     * Определение элемента для конкретной цели
     * @param {Element} element DOM элемент
     * @param {string} target Цель (container, item, etc)
     */
    function selectElementForTarget(element, target) {
        // Генерируем селектор для элемента
        const selector = generateSelector(element);
        
        // Устанавливаем селектор в соответствующее поле
        selectors[target].value = selector;
        
        // Выходим из режима выбора
        exitSelectionMode();
        
        // Подсвечиваем элементы
        highlightCurrentSelectors();
        
        // Если выбран контейнер или элемент статьи, тестируем селекторы
        if (target === 'container' || target === 'item') {
            testSelectors();
        }
    }
    
    /**
     * Автоматически определить селекторы на основе клика на элемент
     */
    function autoDetectSelectors() {
        const url = previewUrl.value.trim();
        if (!url) return;
        
        // Запрашиваем автоматическое определение селекторов у сервера
        fetch('/api/auto_detect_selectors', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                url: url,
                use_selenium: document.getElementById('use_selenium').checked
            }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.success && data.selectors) {
                applyDetectedSelectors(data.selectors);
                highlightCurrentSelectors();
                testSelectors();
            } else {
                showError(data.message || 'Не удалось автоматически определить селекторы');
            }
        })
        .catch(error => {
            console.error('Ошибка при автоопределении селекторов:', error);
        });
    }
    
    /**
     * Автоматическое определение селекторов на основе элемента статьи
     * @param {Element} element DOM элемент (предположительно, элемент статьи)
     * @returns {Object} Объект с селекторами
     */
    function getSelectorsFromElement(element) {
        const iframeDoc = previewIframe.contentDocument || previewIframe.contentWindow.document;
        const result = {};
        
        // Определяем, является ли элемент статьей или контейнером
        let itemElement = element;
        let containerElement = element.parentElement;
        
        // Рекурсивный поиск контейнера с похожими элементами
        function findContainer(el, depth = 0) {
            if (!el || !el.parentElement || depth > 5) return null;
            
            const parent = el.parentElement;
            const siblings = Array.from(parent.children).filter(child => {
                if (child === el) return false; // Исключаем сам элемент
                
                // Проверяем по тегу
                if (child.tagName !== el.tagName) return false;
                
                // Сравниваем классы, игнорируя наши подсветки
                const elClassList = Array.from(el.classList).filter(c => !c.includes('hover-highlight') && !c.includes('selector-'));
                const childClassList = Array.from(child.classList).filter(c => !c.includes('hover-highlight') && !c.includes('selector-'));
                
                // Если нет классов или классы совпадают
                return elClassList.length === 0 || 
                       childClassList.length === 0 ||
                       elClassList.some(cls => childClassList.includes(cls));
            });
            
            if (siblings.length > 0) {
                return {
                    container: parent,
                    item: el,
                    similarCount: siblings.length
                };
            }
            
            return findContainer(parent, depth + 1);
        }
        
        // Пытаемся найти контейнер
        const containerInfo = findContainer(itemElement);
        
        if (containerInfo) {
            containerElement = containerInfo.container;
            itemElement = containerInfo.item;
        } else {
            // Если не нашли подходящий контейнер, используем ближайшего родителя
            if (element.parentElement) {
                itemElement = element;
                containerElement = element.parentElement;
            }
        }
        
        // Генерируем селекторы для контейнера и элемента
        result.item = generateSelector(itemElement);
        result.container = generateSelector(containerElement);
        
        // Ищем заголовок
        let titleElement = itemElement.querySelector('h1, h2, h3, h4, h5, h6');
        if (!titleElement) {
            // Ищем по классам, часто используемым для заголовков
            titleElement = itemElement.querySelector('.title, .heading, .header, [class*="title"], [class*="heading"], [class*="header"]');
        }
        if (titleElement) {
            result.title = generateSelector(titleElement, false);
        }
        
        // Ищем ссылку
        let linkElement = null;
        // Сначала ищем в/около заголовка
        if (titleElement) {
            linkElement = titleElement.closest('a') || titleElement.querySelector('a');
        }
        // Если не нашли, ищем любую ссылку
        if (!linkElement) {
            const links = itemElement.querySelectorAll('a');
            if (links.length > 0) {
                linkElement = links[0]; // Берем первую ссылку
            }
        }
        if (linkElement) {
            result.link = generateSelector(linkElement, false);
        }
        
        // Ищем изображение
        const imageElement = itemElement.querySelector('img');
        if (imageElement) {
            result.image = generateSelector(imageElement, false);
        }
        
        // Ищем дату
        let dateElement = itemElement.querySelector('time, [datetime], .date, .time, [class*="date"], [class*="time"], [class*="posted"]');
        if (dateElement) {
            result.date = generateSelector(dateElement, false);
        }
        
        // Ищем описание (обычно параграф текста)
        let descriptionElement = null;
        const paragraphs = itemElement.querySelectorAll('p');
        if (paragraphs.length > 0) {
            // Выбираем самый длинный параграф как описание
            let maxLength = 0;
            Array.from(paragraphs).forEach(p => {
                const textLength = p.textContent.trim().length;
                if (textLength > maxLength) {
                    maxLength = textLength;
                    descriptionElement = p;
                }
            });
        }
        // Если не нашли параграфов, ищем элементы с типичными классами для описания
        if (!descriptionElement) {
            descriptionElement = itemElement.querySelector('.description, .summary, .excerpt, .content, [class*="desc"], [class*="content"], [class*="text"]');
        }
        if (descriptionElement) {
            result.description = generateSelector(descriptionElement, false);
        }
        
        return result;
    }
    
    /**
     * Определение наиболее вероятного типа элемента
     * @param {Element} element DOM элемент
     */
    function detectElementType(element) {
        // Проверяем различные признаки элемента
        if (element.tagName === 'IMG') {
            // Изображение
            selectElementForTarget(element, 'image');
            return;
        }
        
        if (element.tagName === 'A' || element.closest('a')) {
            // Ссылка или элемент внутри ссылки
            selectElementForTarget(element.tagName === 'A' ? element : element.closest('a'), 'link');
            return;
        }
        
        if (['H1', 'H2', 'H3', 'H4', 'H5', 'H6'].includes(element.tagName)) {
            // Заголовок
            selectElementForTarget(element, 'title');
            return;
        }
        
        if (element.tagName === 'TIME' || element.hasAttribute('datetime')) {
            // Дата публикации
            selectElementForTarget(element, 'date');
            return;
        }
        
        if (element.tagName === 'P') {
            // Параграф - вероятно, описание
            selectElementForTarget(element, 'description');
            return;
        }
        
        // Проверяем по классам и атрибутам
        const className = element.className.toLowerCase();
        const id = element.id.toLowerCase();
        
        if (className.includes('title') || className.includes('heading') || id.includes('title') || id.includes('heading')) {
            selectElementForTarget(element, 'title');
            return;
        }
        
        if (className.includes('date') || className.includes('time') || id.includes('date') || id.includes('time')) {
            selectElementForTarget(element, 'date');
            return;
        }
        
        if (className.includes('desc') || className.includes('content') || className.includes('text') || 
            id.includes('desc') || id.includes('content') || id.includes('text')) {
            selectElementForTarget(element, 'description');
            return;
        }
        
        // Если все условия не сработали, предполагаем, что это элемент статьи
        selectElementForTarget(element, 'item');
    }
    
    /**
     * Применение определенных селекторов
     * @param {Object} detectedSelectors Объект с селекторами
     */
    function applyDetectedSelectors(detectedSelectors) {
        for (const [type, selector] of Object.entries(detectedSelectors)) {
            if (selector && selectors[type]) {
                selectors[type].value = selector;
            }
        }
    }
    
    /**
     * Подсветка элементов согласно текущим селекторам
     */
    function highlightCurrentSelectors() {
        if (!previewIframe.contentDocument) return;
        
        // Сбрасываем текущие подсветки
        resetHighlights();
        
        // Подсвечиваем элементы для каждого селектора
        for (const [type, input] of Object.entries(selectors)) {
            if (!input.value) continue;
            
            try {
                const elements = previewIframe.contentDocument.querySelectorAll(input.value);
                elements.forEach(el => {
                    el.classList.add(highlightClasses[type]);
                });
            } catch (error) {
                console.warn(`Ошибка в селекторе ${type}: ${error.message}`);
            }
        }
    }
    
    /**
     * Сброс всех подсветок
     */
    function resetHighlights() {
        if (!previewIframe.contentDocument) return;
        
        // Удаляем все классы подсветки
        for (const className of Object.values(highlightClasses)) {
            const elements = previewIframe.contentDocument.querySelectorAll(`.${className}`);
            elements.forEach(el => {
                el.classList.remove(className);
            });
        }
        
        // Удаляем подсветки при наведении
        const hoverElements = previewIframe.contentDocument.querySelectorAll('.hover-highlight');
        hoverElements.forEach(el => {
            el.classList.remove('hover-highlight');
        });
    }
    
    /**
     * Вход в режим выбора элемента
     * @param {string} target Цель выбора (container, item, etc.)
     */
    function enterSelectionMode(target) {
        isSelectionMode = true;
        currentSelectionTarget = target;
        previewInfo.innerHTML = `
            <i class="fas fa-crosshairs"></i> 
            <span>Выберите элемент для <strong>${getTargetName(target)}</strong>. Кликните на нужный элемент на странице.</span>
            <button type="button" class="btn btn-sm btn-outline-secondary ms-2" id="cancel-selection">
                Отмена
            </button>
        `;
        
        // Добавляем обработчик для кнопки отмены
        document.getElementById('cancel-selection').addEventListener('click', exitSelectionMode);
    }
    
    /**
     * Выход из режима выбора элемента
     */
    function exitSelectionMode() {
        isSelectionMode = false;
        currentSelectionTarget = null;
        previewInfo.innerHTML = `
            <i class="fas fa-info-circle"></i> 
            <span>Наведите курсор на элемент статьи и кликните для автоматического определения селекторов.</span>
        `;
    }
    
    /**
     * Получение названия цели выбора
     * @param {string} target Цель выбора (container, item, etc.)
     * @returns {string} Название цели на русском
     */
    function getTargetName(target) {
        const names = {
            container: 'контейнера',
            item: 'элемента статьи',
            title: 'заголовка',
            link: 'ссылки',
            description: 'описания',
            image: 'изображения',
            date: 'даты'
        };
        
        return names[target] || target;
    }
    
    /**
     * Отображение ошибки
     * @param {string} message Сообщение об ошибке
     */
    function showError(message) {
        previewError.style.display = 'block';
        previewError.querySelector('#error-message').textContent = message;
    }
    
    /**
     * Тестирование текущих селекторов
     */
    function testSelectors() {
        const url = previewUrl.value.trim();
        if (!url) {
            showError('Введите URL для тестирования селекторов');
            return;
        }
        
        // Собираем текущие селекторы из полей
        const currentSelectors = {};
        for (const [type, input] of Object.entries(selectors)) {
            if (input.value) {
                currentSelectors[type] = input.value;
            }
        }
        
        // Проверяем наличие обязательных селекторов
        if (!currentSelectors.container || !currentSelectors.item) {
            showError('Необходимо указать селекторы для контейнера и элемента статьи');
            return;
        }
        
        // Отправляем запрос на тестирование селекторов
        fetch('/api/test_selectors', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                url: url,
                selectors: currentSelectors,
                use_selenium: document.getElementById('use_selenium').checked
            }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                foundEntries = data.entries;
                updateFoundEntriesDisplay(data.entries);
                updateExtractedItemsDisplay(data.entries);
                entriesCount.textContent = `Найдено: ${data.entries.length} элементов`;
            } else {
                showError(data.message || 'Не удалось извлечь данные с указанными селекторами');
                updateFoundEntriesDisplay([]);
                updateExtractedItemsDisplay([]);
                entriesCount.textContent = 'Найдено: 0 элементов';
            }
        })
        .catch(error => {
            showError(`Ошибка при тестировании селекторов: ${error.message}`);
            updateFoundEntriesDisplay([]);
            updateExtractedItemsDisplay([]);
            entriesCount.textContent = 'Найдено: 0 элементов';
        });
    }
    
    /**
     * Обновление отображения найденных статей
     * @param {Array} entries Массив найденных статей
     */
    function updateFoundEntriesDisplay(entries) {
        if (!entries || entries.length === 0) {
            matchingEntries.innerHTML = `
                <div class="alert alert-info">
                    <i class="fas fa-info-circle"></i> Не найдено статей. Проверьте селекторы и попробуйте снова.
                </div>
            `;
            return;
        }
        
        let html = `<div class="list-group">`;
        
        entries.forEach((entry, index) => {
            // Ограничиваем количество отображаемых статей
            if (index >= 15) return;
            
            const title = entry.title || 'Без заголовка';
            const date = entry.published || '';
            
            html += `
                <div class="list-group-item">
                    <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1">${title}</h6>
                        <small>${date}</small>
                    </div>
                    <p class="mb-1 small entry-url">${entry.link}</p>
                </div>
            `;
        });
        
        if (entries.length > 15) {
            html += `
                <div class="list-group-item text-center text-muted">
                    <small>Показано 15 из ${entries.length} найденных статей</small>
                </div>
            `;
        }
        
        html += `</div>`;
        matchingEntries.innerHTML = html;
    }
    
    /**
     * Обновление отображения извлеченных элементов
     * @param {Array} entries Массив найденных статей
     */
    function updateExtractedItemsDisplay(entries) {
        if (!entries || entries.length === 0) {
            extractedItems.innerHTML = `
                <div class="alert alert-info">
                    <i class="fas fa-info-circle"></i> Не найдено статей. Проверьте селекторы и попробуйте снова.
                </div>
            `;
            return;
        }
        
        let html = `<div class="row">`;
        
        // Отображаем только первые 5 статей для наглядности
        const displayEntries = entries.slice(0, 5);
        
        displayEntries.forEach(entry => {
            const title = entry.title || 'Без заголовка';
            const description = entry.description 
                ? (entry.description.length > 150 ? entry.description.substring(0, 150) + '...' : entry.description)
                : 'Нет описания';
            
            html += `
                <div class="col-md-12 mb-3">
                    <div class="entry-card">
                        <div class="entry-header">
                            <h5>${title}</h5>
                        </div>
                        <div class="entry-body">
                            <div class="row">
                                ${entry.image ? `
                                    <div class="col-md-3">
                                        <img src="${entry.image}" class="entry-image" alt="${title}">
                                    </div>
                                    <div class="col-md-9">
                                ` : `<div class="col-md-12">`}
                                    <p>${description}</p>
                                </div>
                            </div>
                        </div>
                        <div class="entry-footer">
                            <a href="${entry.link}" target="_blank" class="btn btn-sm btn-primary">
                                Перейти к статье
                            </a>
                            <small class="text-muted">${entry.published || ''}</small>
                        </div>
                    </div>
                </div>
            `;
        });
        
        if (entries.length > 5) {
            html += `
                <div class="col-md-12 text-center mt-2 mb-3">
                    <p class="text-muted">Показано 5 из ${entries.length} найденных статей</p>
                </div>
            `;
        }
        
        html += `</div>`;
        extractedItems.innerHTML = html;
    }
    
    // Инициализация обработчиков событий
    function initEventHandlers() {
        // Загрузка предпросмотра
        loadPreviewBtn.addEventListener('click', loadPreview);
        
        // Кнопки выбора элементов
        selectElementBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                const target = this.getAttribute('data-target');
                enterSelectionMode(target);
            });
        });
        
        // Тестирование селекторов
        testSelectorsBtn.addEventListener('click', testSelectors);
        
        // Сброс селекторов
        resetSelectorsBtn.addEventListener('click', function() {
            if (confirm('Вы уверены, что хотите сбросить все селекторы?')) {
                // Очищаем все поля ввода
                for (const input of Object.values(selectors)) {
                    input.value = '';
                }
                
                // Сбрасываем подсветки
                resetHighlights();
                
                // Очищаем предпросмотр
                updateFoundEntriesDisplay([]);
                updateExtractedItemsDisplay([]);
                entriesCount.textContent = 'Найдено: 0 элементов';
            }
        });
        
        // Обновление подсветки при изменении селекторов вручную
        for (const [type, input] of Object.entries(selectors)) {
            input.addEventListener('input', function() {
                highlightCurrentSelectors();
            });
        }
    }
    
    // Запускаем инициализацию
    initEventHandlers();
});