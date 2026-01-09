"""
Тесты для проверки нового асинхронного клиента Google Sheets
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sheets.client import GoogleSheetsCache, get_sheet_data_with_cache, write_transaction
from models.transaction import TransactionData
from datetime import datetime
from config import DATA_SHEET_NAME


@pytest.mark.asyncio
async def test_google_sheets_cache_initialization():
    """Тест инициализации асинхронного кэша Google Sheets"""
    cache = GoogleSheetsCache()
    
    assert cache._gc is None
    assert cache._sheets == {}
    assert cache._last_gc_time is None
    assert cache._data_cache == {}
    assert cache._cache_timestamps == {}


@pytest.mark.asyncio
async def test_get_client_creates_connection():
    """Тест создания асинхронного подключения к Google Sheets"""
    cache = GoogleSheetsCache()
    
    with patch('sheets.client.asyncio.to_thread') as mock_to_thread:
        mock_client = MagicMock()
        mock_to_thread.return_value = mock_client
        
        client = await cache.get_client()
        
        assert client == mock_client
        mock_to_thread.assert_called_once()


@pytest.mark.asyncio
async def test_get_worksheet_returns_cached_instance():
    """Тест получения кэшированного экземпляра листа"""
    cache = GoogleSheetsCache()
    
    with patch.object(cache, 'get_client') as mock_get_client:
        mock_gc = MagicMock()
        mock_sh = MagicMock()
        mock_ws = MagicMock()
        
        mock_get_client.return_value = mock_gc
        mock_gc.open_by_url.return_value = mock_sh
        mock_sh.worksheet.return_value = mock_ws
        
        worksheet = await cache.get_worksheet('TestSheet')
        
        assert worksheet == mock_ws
        assert 'TestSheet' in cache._sheets
        assert cache._sheets['TestSheet'] == mock_ws


@pytest.mark.asyncio
async def test_get_sheet_data_with_cache_returns_cached_data():
    """Тест получения данных из листа с использованием кэша"""
    cache = GoogleSheetsCache()
    
    # Заполням кэш данными
    test_data = [['header1', 'header2'], ['value1', 'value2']]
    cache.cache_data('TestSheet', test_data)
    
    with patch('sheets.client._sheets_cache', cache):
        result = await get_sheet_data_with_cache('TestSheet')
        
        assert result == test_data


@pytest.mark.asyncio
async def test_get_sheet_data_with_cache_fetches_from_api_if_not_cached():
    """Тест получения данных из API если они не закэшированы"""
    cache = GoogleSheetsCache()
    
    with patch('sheets.client._sheets_cache', cache):
        with patch('sheets.client.get_google_sheet_client') as mock_get_client:
            mock_worksheet = MagicMock()
            mock_worksheet.get_all_values.return_value = [['data1', 'data2']]
            mock_get_client.return_value = mock_worksheet
            
            result = await get_sheet_data_with_cache('TestSheet')
            
            assert result == [['data1', 'data2']]
            # Проверяем, что данные были закэшированы
            cached_result = cache.get_cached_data('TestSheet')
            assert cached_result == [['data1', 'data2']]


@pytest.mark.asyncio
async def test_write_transaction_calls_append_rows():
    """Тест записи транзакции вызывает append_rows"""
    transaction = TransactionData(
        type="Расход",
        category="Продукты",
        amount=100.0,
        comment="Покупка",
        username="test_user",
        user_id=123,
        retailer_name="Магазин",
        items_list="",
        payment_info="",
        transaction_dt=datetime.now()
    )
    
    with patch('sheets.client.get_google_sheet_client') as mock_get_client:
        mock_worksheet = MagicMock()
        mock_get_client.return_value = mock_worksheet
        mock_to_thread = AsyncMock()
        
        with patch('sheets.client.asyncio.to_thread', side_effect=mock_to_thread):
            await write_transaction(transaction)
            
            # Проверяем, что был вызван asyncio.to_thread хотя бы один раз
            assert mock_to_thread.call_count >= 1
            # Проверяем, что среди вызовов был вызов ws.append_rows
            # Находим вызов, связанный с append_rows
            append_rows_call = None
            for call in mock_to_thread.call_args_list:
                args, kwargs = call
                if len(args) > 0 and 'append_rows' in str(args[0]):
                    append_rows_call = call
                    break
            
            assert append_rows_call is not None, "append_rows не был вызван"
            args, kwargs = append_rows_call
            # Проверяем, что первый аргумент связан с append_rows
            assert 'append_rows' in str(args[0])
            assert len(args) >= 2  # Должны быть функция и аргументы
            assert len(args[1]) == 1  # Один ряд данных
            assert len(args[1][0]) == 10  # 10 колонок


@pytest.mark.asyncio
async def test_cache_invalidates_after_write_transaction():
    """Тест инвалидации кэша после записи транзакции"""
    cache = GoogleSheetsCache()
    # Импортируем DATA_SHEET_NAME в начале функции
    from config import DATA_SHEET_NAME
    
    # Предварительно закэшируем данные
    test_data = [['header1', 'header2'], ['value1', 'value2']]
    cache.cache_data(DATA_SHEET_NAME, test_data)

    transaction = TransactionData(
        type="Расход",
        category="Продукты",
        amount=100.0,
        comment="Покупка",
        username="test_user",
        user_id=123,
        retailer_name="Магазин",
        items_list="",
        payment_info="",
        transaction_dt=datetime.now()
    )

    with patch('sheets.client._sheets_cache', cache):
        with patch('sheets.client.get_google_sheet_client') as mock_get_client:
            mock_worksheet = MagicMock()
            mock_get_client.return_value = mock_worksheet
            mock_to_thread = AsyncMock()

            with patch('sheets.client.asyncio.to_thread', side_effect=mock_to_thread):
                await write_transaction(transaction)
                
                # После записи транзакции кэш данных транзакций должен быть очищен
                cached_data = cache.get_cached_data(DATA_SHEET_NAME)
                # Проверим, что кэш был очищен - данные должны быть None
                assert cached_data is None



if __name__ == '__main__':
    pytest.main([__file__, '-v'])