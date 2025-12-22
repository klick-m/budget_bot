---
mode: qa
---
# QA Проверка (Smoke Testing)

**ШАГ 1: ПРОВЕРКА ВХОДА**
1. Убедись, что последняя запись в `.context/MEMORY_LOG.md` — это `✅ UNIT TESTS PASSED`.

**ШАГ 2: ИСПЫТАНИЕ**
1. Запусти `python scripts/smoke_test.py`.
2. Используй инструмент `sqlite` (MCP), чтобы проверить реальное состояние таблиц в БД.

**ШАГ 3: ОТЧЕТ**
* **ЕСЛИ УСПЕХ:** Добавь в лог `✅ SMOKE TEST PASSED` и вызови `/accept_task`.
* **ЕСЛИ ОШИБКА:** Добавь в лог `❌ RUNTIME ERROR` и вызови `/debug`.