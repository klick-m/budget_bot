# Текущая Активная Задача
**ID:** REF-005
⚠️ **CRITICAL:** Ensure you are NOT on the `main` branch. Create `feature/sqlite-db`.

**Описание:** Внедрение SQLite и Асинхронной записи.
Сейчас бот пишет в Google Sheets синхронно, что тормозит UI. Нужно внедрить локальную БД (SQLite) как "First Write" хранилище, а в Google Sheets отправлять данные фоном.

**Исполнитель:** Code (Backend)

**Чек-лист выполнения:**
- [ ] **1. Слой данных (Repository):**
    - Создать `services/repository.py`.
    - Реализовать класс `TransactionRepository` на базе `aiosqlite`.
    - При старте бота создавать таблицу `transactions` (id, user_id, amount, category, raw_text, date, synced_to_sheets).

- [ ] **2. Асинхронность в TransactionService:**
    - Переписать `transaction_service.py`.
    - Метод `save_transaction` должен:
      1. `await repo.add(...)` -> Сохранить в SQLite (мгновенно).
      2. Вернуть пользователю "Успех".
      3. `asyncio.create_task(...)` -> Запустить фоновую отправку в Google Sheets.

- [ ] **3. Отказоустойчивость:**
    - Если Google Sheets недоступен или упал с ошибкой — бот НЕ должен падать.
    - Транзакция остается в SQLite со статусом `synced_to_sheets=0`.