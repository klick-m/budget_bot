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
- **Repository Inheritance**: TransactionRepository наследуется от UserRepository, обеспечивая доступ ко всем методам управления пользователями и гарантируя создание обеих таблиц (users и transactions) при инициализации базы данных.
- **User Object Model**: Middleware теперь передает объект User (Pydantic модель) вместо словаря, что улучшает типизацию и предотвращает ошибки доступа к атрибутам.
- **Removed Feature**: Функционал monthly_limit был удален из системы, что упростило логику управления бюджетом и устранило связанную с ним сложность.
- **FSM Admin Panel**: Интерактивная админ-панель реализована с использованием Finite State Machine (FSM) для управления состоянием сессии администратора. Используется `aiogram.fsm.context.FSMContext` для отслеживания текущего состояния админ-панели (главное меню, меню управления пользователями, меню статистики и т.д.).

## Data Flow
1. **Input**: Telegram Message -> Middleware (Auth) -> Handler.
2. **Logic**: Handler -> Service -> Repository.
3. **Storage**: Repository (SQLite) -> Commit.
4. **Sync**: SyncWorker -> Repository (fetch unsynced) -> Google Sheets.

## Admin Panel Architecture
- **AdminPanel Class**: Центральный класс для обработки интерактивной админ-панели с FSM.
- **FSM States**: Используются состояния из `AdminStates` (main_menu, users_menu, stats_menu, reports_menu, settings_menu) для управления потоком взаимодействия.
- **State Management**: Каждое действие администратора изменяет состояние FSM, что позволяет управлять навигацией между различными меню админ-панели.
- **Callback Handlers**: Обработчики callback'ов управляют переходами между состояниями FSM и обеспечивают интерактивное меню для административных операций.
- **Access Control**: Все FSM-обработчики проверяют права администратора перед выполнением действий.