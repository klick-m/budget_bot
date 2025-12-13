import re
from typing import Dict, Optional


def parse_transaction_text(text: str) -> Dict[str, Optional[str]]:
    """
    Parse transaction text to extract amount and category.
    
    Args:
        text: Input text like "300 кофе"
        
    Returns:
        Dict with 'amount' and 'category' keys
    """
    # Find the first number in the text (including decimal numbers)
    number_match = re.search(r'\d+(?:[.,]\d+)?', text)
    
    if not number_match:
        return {'amount': None, 'category': None}
    
    amount_str = number_match.group()
    amount = float(amount_str.replace(',', '.'))
    
    # Get the rest of the text after removing the first number
    category_part = text[:number_match.start()] + text[number_match.end():]
    # Clean up extra spaces
    category = ' '.join(category_part.split()).strip()
    
    return {'amount': amount, 'category': category or 'Без категории'}