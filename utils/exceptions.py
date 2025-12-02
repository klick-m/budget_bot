# utils/exceptions.py

class SheetsError(Exception):
    """Базовое исключение для ошибок при работе с Google Sheets."""
    pass

class SheetConnectionError(SheetsError):
    """Ошибка подключения или авторизации к Google Sheets."""
    pass

class SheetWriteError(SheetsError):
    """Ошибка при записи данных в Google Sheets."""
    pass

class CheckApiError(Exception):
    """Базовое исключение для ошибок при работе с Proverkacheka.com API."""
    pass

class CheckApiTimeout(CheckApiError):
    """Превышено время ожидания ответа от API чеков."""
    pass

class CheckApiRecognitionError(CheckApiError):
    """Чек не распознан или некорректен."""
    pass