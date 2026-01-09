# System Architecture

## Tech Stack
- **Language**: Python 3.11+
- **Bot Framework**: aiogram 3.x (Asyncio)
- **Database**: SQLite (aiosqlite)
- **External Storage**: Google Sheets API (gspread-asyncio)
- **NLP/ML**: pymorphy3, custom TF-IDF classifier

## Architectural Patterns (Strictly Enforced)
- **Repository Pattern**: Весь SQL-код должен быть инкапсулирован в `TransactionRepository` и `UserRepository`. Сервисы не имеют прямого доступа к БД.
- **Service Layer**: Бизнес-логика (расчеты, валидация) живет в `TransactionService`, `AuthService` и `AnalyticsService`.
- **Dependency Injection**: Все сервисы внедряются в диспетчер через `dp.workflow_data` и передаются в хендлеры через аннотации типов.
- **Local-First**: Транзакция считается успешной сразу после записи в SQLite. Синхронизация с облаком выполняется фоновым процессом `SyncWorker`.
- **Auth Middleware**: Проверка прав пользователя и инъекция объекта `current_user` происходит на уровне Middleware до попадания в хендлеры. AuthMiddleware интегрирована с UserRepository для проверки наличия пользователя в системе и его роли.

## Data Flow
1. **Input**: Telegram Message -> Middleware (Auth) -> Handler.
2. **Logic**: Handler -> Service -> Repository.
3. **Storage**: Repository (SQLite) -> Commit.
4. **Sync**: SyncWorker -> Repository (fetch unsynced) -> Google Sheets.