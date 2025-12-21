import re
from typing import Optional, Tuple, Dict, Any


class InputParser:
    """
    Парсер для быстрого ввода транзакций.
    Поддерживает форматы: "Текст Число", "Число Текст", "Просто Число".
    """
    
    def __init__(self):
        # Регулярное выражение для поиска чисел (целые и дробные)
        self.number_pattern = r'(\d+(?:[.,]\d{1,2})?)'
        
    def parse_user_input(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Парсит пользовательский ввод и возвращает словарь с информацией о транзакции.
        
        Args:
            text: Входной текст от пользователя
            
        Returns:
            Словарь с ключами 'amount' (float) и 'comment' (str), или None если парсинг не удался
        """
        text = text.strip()
        if not text:
            return None
            
        # Находим все числа в строке
        numbers = re.findall(self.number_pattern, text)
        
        if not numbers:
            return None
        
        # Берем первое найденное число как сумму
        amount_str = numbers[0]
        amount = float(amount_str.replace(',', '.'))
        
        # Убираем число из строки, чтобы получить комментарий
        remaining_text = re.sub(self.number_pattern, '', text, 1).strip()
        
        # Убираем лишние символы и пробелы
        remaining_text = re.sub(r'[^\w\s]', ' ', remaining_text)
        # Убираем множественные пробелы, оставляя только один
        remaining_text = ' '.join(remaining_text.split())
        
        # Если после удаления числа остался какой-то текст, это будет комментарием
        comment = remaining_text if remaining_text else ""
        
        return {
            'amount': amount,
            'comment': comment
        }
    
    def parse_transaction(self, text: str) -> Optional[Tuple[float, str]]:
        """
        Упрощенный метод для парсинга транзакции.
        
        Args:
            text: Входной текст от пользователя
            
        Returns:
            Кортеж (сумма, комментарий) или None если парсинг не удался
        """
        parsed = self.parse_user_input(text)
        if parsed:
            return parsed['amount'], parsed['comment']
        return None