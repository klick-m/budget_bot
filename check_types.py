import asyncio
from unittest.mock import AsyncMock
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# Проверим, как определить типы
storage = MemoryStorage()
key = ('test', 'chat', 'user')
state = FSMContext(storage, key)

print('FSMContext type:', type(state))
print('Has update_data attr:', hasattr(state, 'update_data'))
print('Has set_state attr:', hasattr(state, 'set_state'))

# Mock auth service
mock_auth = AsyncMock()
print('Mock auth type:', type(mock_auth))
print('Has update_user_role attr:', hasattr(mock_auth, 'update_user_role'))
print('Is FSMContext?', isinstance(state, FSMContext))
print('Is AsyncMock?', isinstance(mock_auth, AsyncMock))