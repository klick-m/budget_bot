"""
Global Service Locator для внедрения зависимостей в обработчики.
"""

# Глобальные переменные для хранения сервисов
_transaction_service = None


def set_transaction_service(service):
    """Устанавливает глобальный экземпляр TransactionService."""
    global _transaction_service
    _transaction_service = service


def get_transaction_service():
    """Возвращает глобальный экземпляр TransactionService."""
    global _transaction_service
    return _transaction_service