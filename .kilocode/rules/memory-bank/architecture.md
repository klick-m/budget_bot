# System Architecture

## Технологический стек
- **Язык:** Python 3.11+
- **Фреймворк бота:** aiogram 3.x (Asyncio)
- **База данных:** SQLite (aiosqlite) — локальное хранилище.
- **Внешнее хранилище:** Google Sheets API (gspread-asyncio).
- **ML/NLP:** pymorphy3 (лемматизация), кастомный классификатор на базе TF-IDF.

## Структура проекта
- `handlers/`: Слайсы логики (receipts, manual, smart_input, admin). Используют FSM для управления состояниями.
- `services/`:
    - `TransactionService`: Фасад для обработки транзакций.
    - `TransactionRepository`: Слой доступа к SQLite.
    - `SyncWorker`: Фоновый процесс синхронизации.
    - `AuthService`: Служба аутентификации пользователей.
- `models/`: Pydantic-модели данных, логика словаря ключевых слов и модель пользователя.
- `sheets/`: Клиент для работы с Google Таблицами с кэшированием и обработкой ошибок 429.
- `utils/`: Классификатор категорий, клавиатуры, сообщения.

## Ключевые паттерны
- **Local-First:** Сначала запись в `transactions.db`, затем асинхронная отправка в облако через `SyncWorker`.
- **Dependency Injection:** Сервисы (например, `TransactionService`) внедряются в диспетчер через `dp.workflow_data` и доступны в хендлерах.
- **FSM (Finite State Machine):** Управление сложными сценариями ввода (ручной ввод, обработка чеков, разделение чека).
- **Repository Pattern:** Изоляция логики работы с БД в `TransactionRepository`.
- **Authentication Layer:** Слой аутентификации с проверкой пользователей через `AuthService`.