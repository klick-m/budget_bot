---
mode: orchestrator
---
# Приемка Задачи (Acceptance)

**ШАГ 1: АУДИТ**
1. Проверь наличие `✅ UNIT TESTS PASSED` и `✅ SMOKE TEST PASSED` в `.context/MEMORY_LOG.md`.

**ШАГ 2: ЗАКРЫТИЕ**
1. Поставь `[x]` в `.context/PROJECT_STATUS.md`.
2. Добавь в `.context/MEMORY_LOG.md` запись `🏁 TASK COMPLETED`.
3. Установи статус `IDLE` в `.context/CURRENT_TASK.md`.

**ШАГ 3: ФИНАЛ**
Задача полностью закрыта.