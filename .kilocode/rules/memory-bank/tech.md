# Technical Stack & Setup

## Зависимости
- `aiogram`: Асинхронное взаимодействие с Telegram API.
- `gspread`, `gspread-asyncio`: Работа с Google Sheets API.
- `aiosqlite`: Асинхронный драйвер для локальной БД SQLite.
- `pydantic`: Валидация данных транзакций и моделей API.
- `pymorphy3`: Морфологический анализ для улучшения точности классификации.
- `aiohttp`: Клиент для работы с API чеков и скачивания файлов.

## Конфигурация
Настройки хранятся в `.env` и загружаются через `config.py`:
- `BOT_TOKEN`: Токен Telegram бота.
- `ALLOWED_USER_IDS`: Список ID пользователей с доступом.
- `GOOGLE_SHEET_URL`: Ссылка на основную таблицу Google Sheets.
- `SERVICE_ACCOUNT_FILE`: Путь к JSON-файлу сервисного аккаунта Google.
- `CHECK_API_TOKEN`: Токен для API Proverkacheka.com.

## Особенности реализации
- **Обработка UTF-8:** Специфичные настройки для Windows в `config.py` для корректного вывода логов в консоль.
- **Кэширование:** `GoogleSheetsCache` в `sheets/client.py` предотвращает лишние вызовы API и обрабатывает ошибку 429 (Rate Limit).
- **Миграции:** Базовая логика проверки и обновления структуры таблиц SQLite в `TransactionRepository.init_db`.
- **ML Модель:** Состояние классификатора сохраняется в `category_classifier_model.pkl`.