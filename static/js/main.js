/**
 * Основные JavaScript функции для RSS Агрегатора
 */

document.addEventListener('DOMContentLoaded', function() {
    // Управление сообщениями об ошибках и уведомлениями
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000); // Закрываем уведомления через 5 секунд
    });
    
    // Включение всплывающих подсказок Bootstrap
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Функционал для форматирования отображения описаний лент
    const feedDescriptions = document.querySelectorAll('.feed-item-description');
    feedDescriptions.forEach(description => {
        // Удаляем опасные скрипты из описаний (простая защита)
        description.innerHTML = description.innerHTML.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
        
        // Ограничиваем размер изображений
        const images = description.querySelectorAll('img');
        images.forEach(img => {
            img.style.maxWidth = '100%';
            img.style.height = 'auto';
        });
        
        // Добавляем атрибут target="_blank" ко всем ссылкам
        const links = description.querySelectorAll('a');
        links.forEach(link => {
            link.setAttribute('target', '_blank');
            link.setAttribute('rel', 'noopener noreferrer');
        });
    });
    
    // Функционал для проверки доступности сайта при добавлении/редактировании ленты
    const checkUrlBtn = document.getElementById('check_url');
    if (checkUrlBtn) {
        checkUrlBtn.addEventListener('click', function() {
            const urlInput = document.getElementById('feed_url');
            const url = urlInput.value.trim();
            const feedbackEl = document.getElementById('url_feedback');
            
            if (!url) {
                feedbackEl.innerHTML = '<div class="text-danger">Пожалуйста, введите URL</div>';
                return;
            }
            
            // Проверка корректности URL
            try {
                new URL(url);
            } catch (e) {
                feedbackEl.innerHTML = '<div class="text-danger">Некорректный URL. Пример: https://example.com/rss</div>';
                return;
            }
            
            // Отображаем индикатор загрузки
            feedbackEl.innerHTML = '<div class="text-info"><span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Проверка URL...</div>';
            
            // Здесь будет AJAX запрос для проверки URL в реальном приложении
            // Для демонстрации просто имитируем успешную проверку через некоторое время
            setTimeout(() => {
                const feedType = document.getElementById('feed_type').value;
                if (feedType === 'rss') {
                    // Проверка RSS ленты
                    if (url.includes('rss') || url.includes('feed') || url.includes('atom')) {
                        feedbackEl.innerHTML = '<div class="text-success">URL выглядит как RSS-лента. Проверьте после добавления.</div>';
                    } else {
                        feedbackEl.innerHTML = '<div class="text-warning">URL не похож на RSS-ленту. Возможно, вы указали обычный URL сайта?</div>';
                    }
                } else {
                    // Проверка обычного сайта
                    feedbackEl.innerHTML = '<div class="text-success">URL доступен. После добавления вы сможете настроить парсинг.</div>';
                }
            }, 1500);
        });
    }
});

/**
 * Функция для форматирования даты
 * @param {Date|string} date - Объект Date или строка с датой
 * @param {boolean} includeTime - Включать ли время в формат
 * @returns {string} Отформатированная дата
 */
function formatDate(date, includeTime = true) {
    if (!date) return '';
    
    const d = new Date(date);
    if (isNaN(d.getTime())) return '';
    
    const day = d.getDate().toString().padStart(2, '0');
    const month = (d.getMonth() + 1).toString().padStart(2, '0');
    const year = d.getFullYear();
    
    if (!includeTime) {
        return `${day}.${month}.${year}`;
    }
    
    const hours = d.getHours().toString().padStart(2, '0');
    const minutes = d.getMinutes().toString().padStart(2, '0');
    
    return `${day}.${month}.${year} ${hours}:${minutes}`;
}

/**
 * Функция для обрезки текста до определенной длины
 * @param {string} text - Исходный текст
 * @param {number} maxLength - Максимальная длина
 * @returns {string} Обрезанный текст с многоточием, если необходимо
 */
function truncateText(text, maxLength = 100) {
    if (!text || text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}