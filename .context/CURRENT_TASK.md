# Текущая Активная Задача
**ID:** REF-001
⚠️ **CRITICAL:** Before starting, ensure you are NOT on the `main` branch. Ask the user to create a feature branch if needed.
**Описание:** Создание TransactionService и очистка handlers/transactions.py.
**Исполнитель:** Code (Backend)

**Чек-лист выполнения:**
- [x] Создать файл `services/transaction_service.py`.
- [x] Перенести логику сбора DTO транзакции из хендлеров в сервис.
- [x] Перенести логику записи в Google Sheets (вызовы client.py) внутрь сервиса.
- [x] Внедрить вызов сервиса в `handlers/transactions.py`, убрав "спагетти-код".
- [x] Проверить, что FSM корректно работает с новым сервисом.