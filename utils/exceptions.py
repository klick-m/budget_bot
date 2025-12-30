# utils/exceptions.py

class BudgetBotError(Exception):
    """Базовое исключение для ошибок бота."""
    pass

class SheetsError(BudgetBotError):
    """Базовое исключение для ошибок при работе с Google Sheets."""
    pass

class SheetConnectionError(SheetsError):
    """Ошибка подключения или авторизации к Google Sheets."""
    pass

class SheetWriteError(SheetsError):
    """Ошибка при записи данных в Google Sheets."""
    pass

class TransactionError(BudgetBotError):
    """Базовое исключение для ошибок транзакций."""
    pass

class TransactionSaveError(TransactionError):
    """Ошибка при сохранении транзакции."""
    pass

class CategoryLoadError(TransactionError):
    """Ошибка при загрузке категорий."""
    pass

class CheckApiError(BudgetBotError):
    """Базовое исключение для ошибок при работе с Proverkacheka.com API."""
    pass

class CheckApiTimeout(CheckApiError):
    """Превышено время ожидания ответа от API чеков."""
    pass

class CheckApiRecognitionError(CheckApiError):
    """Чек не распознан или некорректен."""
    pass