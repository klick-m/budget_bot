# -*- coding: utf-8 -*-
"""
Тесты для проверки обработки ошибок API в функции parse_check_from_api
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import aiohttp
from aiohttp import ClientTimeout
import logging
from io import StringIO

from utils.receipt_logic import parse_check_from_api
from utils.exceptions import CheckApiTimeout, CheckApiRecognitionError


class TestReceiptApiErrors:
    """Тесты для проверки обработки ошибок API чеков"""

    @pytest.mark.asyncio
    async def test_parse_check_from_api_400_error(self):
        """Тест: Проверка обработки HTTP 400 ошибки"""
        image_data = b"fake image data"
        
        # Создаем мок-сессию и ответ
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value="Bad Request")
        mock_response.json = AsyncMock(side_effect=Exception("Not JSON for 400"))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        
        with patch('config.CHECK_API_TOKEN', 'test_token'), \
             patch('config.CHECK_API_URL', 'https://proverkacheka.com/api/v1/check/get'), \
             patch('config.CHECK_API_TIMEOUT', 10):
            
            with pytest.raises(CheckApiRecognitionError) as exc_info:
                await parse_check_from_api(image_data, session=mock_session)
            
            assert "HTTP Error 400" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_parse_check_from_api_401_error(self):
        """Тест: Проверка обработки HTTP 401 ошибки"""
        image_data = b"fake image data"
        
        # Создаем мок-сессию и ответ
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.text = AsyncMock(return_value="Unauthorized")
        mock_response.json = AsyncMock(side_effect=Exception("Not JSON for 401"))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        
        with patch('config.CHECK_API_TOKEN', 'test_token'), \
             patch('config.CHECK_API_URL', 'https://proverkacheka.com/api/v1/check/get'), \
             patch('config.CHECK_API_TIMEOUT', 10):
            
            with pytest.raises(CheckApiRecognitionError) as exc_info:
                await parse_check_from_api(image_data, session=mock_session)
            
            assert "HTTP Error 401" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_parse_check_from_api_403_error(self):
        """Тест: Проверка обработки HTTP 403 ошибки"""
        image_data = b"fake image data"
        
        # Создаем мок-сессию и ответ
        mock_response = AsyncMock()
        mock_response.status = 403
        mock_response.text = AsyncMock(return_value="Forbidden")
        mock_response.json = AsyncMock(side_effect=Exception("Not JSON for 403"))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        
        with patch('config.CHECK_API_TOKEN', 'test_token'), \
             patch('config.CHECK_API_URL', 'https://proverkacheka.com/api/v1/check/get'), \
             patch('config.CHECK_API_TIMEOUT', 10):
            
            with pytest.raises(CheckApiRecognitionError) as exc_info:
                await parse_check_from_api(image_data, session=mock_session)
            
            assert "HTTP Error 403" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_parse_check_from_api_429_error_with_retry(self):
        """Тест: Проверка обработки HTTP 429 ошибки с повторной попыткой"""
        image_data = b"fake image data"
        
        # Создаем мок-сессию и сначала возвращаем 429 ошибку, затем успешный ответ
        first_response = AsyncMock()
        first_response.status = 429
        first_response.text = AsyncMock(return_value="Too Many Requests")
        
        second_response = AsyncMock()
        second_response.status = 200
        second_response.json = AsyncMock(return_value={
            "code": 1,
            "data": {
                "json": {
                    "user": "Test Retailer",
                    "totalSum": 10,
                    "items": [{"name": "Test Item"}],
                    "dateTime": "2023-01-01T10:00"
                }
            }
        })
        
        # Используем side_effect для возврата разных ответов при разных вызовах
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(side_effect=[first_response, second_response])
        
        with patch('config.CHECK_API_TOKEN', 'test_token'), \
             patch('config.CHECK_API_URL', 'https://proverkacheka.com/api/v1/check/get'), \
             patch('config.CHECK_API_TIMEOUT', 10), \
             patch('asyncio.sleep', new=AsyncMock()):  # Мокируем sleep, чтобы тесты не ждали
                
                # Запускаем функцию - она должна выполниться успешно после повторных попыток
                result = await parse_check_from_api(image_data, session=mock_session)
                
                assert result.retailer_name == "Test Retailer"
                assert result.amount == 0.1  # 10 копеек / 10 = 0.1 рубля

    @pytest.mark.asyncio
    async def test_parse_check_from_api_500_error_with_retry(self):
        """Тест: Проверка обработки HTTP 500 ошибки с повторной попыткой"""
        image_data = b"fake image data"
        
        # Создаем мок-сессию и сначала возвращаем 500 ошибку, затем успешный ответ
        first_response = AsyncMock()
        first_response.status = 500
        first_response.text = AsyncMock(return_value="Internal Server Error")
        first_response.__aenter__ = AsyncMock(return_value=first_response)
        first_response.__aexit__ = AsyncMock(return_value=None)
        
        second_response = AsyncMock()
        second_response.status = 200
        second_response.json = AsyncMock(return_value={
            "code": 1,
            "data": {
                "json": {
                    "user": "Test Retailer",
                    "totalSum": 1000,
                    "items": [{"name": "Test Item"}],
                    "dateTime": "2023-01-01T10:00"
                }
            }
        })
        second_response.__aenter__ = AsyncMock(return_value=second_response)
        second_response.__aexit__ = AsyncMock(return_value=None)
        
        # Используем side_effect для возврата разных ответов при разных вызовах
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(side_effect=[first_response, second_response])
        
        with patch('config.CHECK_API_TOKEN', 'test_token'), \
             patch('config.CHECK_API_URL', 'https://proverkacheka.com/api/v1/check/get'), \
             patch('config.CHECK_API_TIMEOUT', 10), \
             patch('asyncio.sleep', new=AsyncMock()):  # Мокируем sleep, чтобы тесты не ждали
                
                # Запускаем функцию - она должна выполниться успешно после повторных попыток
                result = await parse_check_from_api(image_data, session=mock_session)
                
                assert result.retailer_name == "Test Retailer"
                assert result.amount == 10.0

    @pytest.mark.asyncio
    async def test_parse_check_from_api_timeout_error(self):
        """Тест: Проверка обработки таймаута API"""
        image_data = b"fake image data"
        
        # Создаем мок-сессию, которая выбрасывает TimeoutError
        mock_response = AsyncMock()
        mock_response.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        
        with patch('config.CHECK_API_TOKEN', 'test_token'), \
             patch('config.CHECK_API_URL', 'https://proverkacheka.com/api/v1/check/get'), \
             patch('config.CHECK_API_TIMEOUT', 10):
            
            with pytest.raises(CheckApiTimeout) as exc_info:
                await parse_check_from_api(image_data, session=mock_session)
            
            assert "Превышено время ожидания" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_parse_check_from_api_connection_error_with_retry(self):
        """Тест: Проверка обработки сетевых ошибок с повторной попыткой"""
        import aiohttp
        
        image_data = b"fake image data"
        
        # Создаем мок-сессию, которая выбрасывает ClientConnectorError
        mock_response = AsyncMock()
        mock_response.__aenter__ = AsyncMock(side_effect=aiohttp.ClientConnectorError(None, OSError("Connection failed")))
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        
        with patch('config.CHECK_API_TOKEN', 'test_token'), \
             patch('config.CHECK_API_URL', 'https://proverkacheka.com/api/v1/check/get'), \
             patch('config.CHECK_API_TIMEOUT', 10), \
             patch('asyncio.sleep', new=AsyncMock()):  # Мокируем sleep, чтобы тесты не ждали
            
            # Проверим, что после нескольких неудачных попыток вызывается ошибка
            with pytest.raises(CheckApiRecognitionError) as exc_info:
                await parse_check_from_api(image_data, session=mock_session)
            
            assert "Не удалось выполнить запрос к API после" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_parse_check_from_api_logging_on_error(self):
        """Тест: Проверка логирования ошибок API"""
        from aioresponses import aioresponses
        
        image_data = b"fake image data"
        
        # Создаем буфер для захвата логов
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.ERROR)
        
        # Получаем логгер
        logger = logging.getLogger('bot_logger')
        original_handlers = logger.handlers[:]
        logger.handlers = [handler] # Устанавливаем только наш обработчик для теста
        
        try:
            with aioresponses() as m:
                # Мокируем POST-запрос к реальному API URL с 400 ошибкой
                m.post(
                    'https://proverkacheka.com/api/v1/check/get', 
                    status=400,
                    payload={"code": 0, "data": {"json": {}}}
                )
                
                with patch('config.CHECK_API_TOKEN', 'test_token'), \
                     patch('config.CHECK_API_URL', 'https://proverkacheka.com/api/v1/check/get'), \
                     patch('config.CHECK_API_TIMEOUT', 10):
                    
                    with pytest.raises(CheckApiRecognitionError):
                        await parse_check_from_api(image_data)
                    
                    # Проверяем, что сообщение об ошибке было записано в лог
                    log_contents = log_capture.getvalue()
                    assert "HTTP Error 400" in log_contents
                    assert "https://proverkacheka.com/api/v1/check/get" in log_contents
        finally:
            # Восстанавливаем исходные обработчики логгера
            logger.handlers = original_handlers

    @pytest.mark.asyncio
    async def test_parse_check_from_api_api_specific_error_codes(self):
        """Тест: Проверка обработки специфичных кодов ошибок API"""
        image_data = b"fake image data"
        
        # Тестируем разные коды ошибок API
        for api_code in [0, 2, 3, 4, 5]:
            # Создаем мок-сессию и ответ с нужным кодом ошибки API
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "code": api_code,
                "data": {
                    "json": {}
                }
            })
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            
            mock_session = AsyncMock()
            mock_session.post = AsyncMock(return_value=mock_response)
            
            with patch('config.CHECK_API_TOKEN', 'test_token'), \
                 patch('config.CHECK_API_URL', 'https://proverkacheka.com/api/v1/check/get'), \
                 patch('config.CHECK_API_TIMEOUT', 10):
                
                with pytest.raises(CheckApiRecognitionError) as exc_info:
                    await parse_check_from_api(image_data, session=mock_session)
                
                # Проверяем, что в сообщении об ошибке есть описание кода
                error_descriptions = {
                    0: "чек некорректен",
                    2: "данные чека пока не получены",
                    3: "превышено кол-во запросов",
                    4: "ожидание перед повторным запросом",
                    5: "прочее (данные не получены)"
                }
                assert error_descriptions[api_code] in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_parse_check_from_api_502_error_with_retry(self):
        """Тест: Проверка обработки HTTP 502 ошибки с повторной попыткой"""
        image_data = b"fake image data"
        
        # Создаем мок-сессию и сначала возвращаем 502 ошибку, затем успешный ответ
        first_response = AsyncMock()
        first_response.status = 502
        first_response.text = AsyncMock(return_value="Bad Gateway")
        
        second_response = AsyncMock()
        second_response.status = 200
        second_response.json = AsyncMock(return_value={
            "code": 1,
            "data": {
                "json": {
                    "user": "Test Retailer",
                    "totalSum": 100,
                    "items": [{"name": "Test Item"}],
                    "dateTime": "2023-01-01T10:00"
                }
            }
        })
        
        # Используем side_effect для возврата разных ответов при разных вызовах
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(side_effect=[first_response, second_response])
        
        with patch('config.CHECK_API_TOKEN', 'test_token'), \
             patch('config.CHECK_API_URL', 'https://proverkacheka.com/api/v1/check/get'), \
             patch('config.CHECK_API_TIMEOUT', 10), \
             patch('asyncio.sleep', new=AsyncMock()):  # Мокируем sleep, чтобы тесты не ждали
                
                # Запускаем функцию - она должна выполниться успешно после повторных попыток
                result = await parse_check_from_api(image_data, session=mock_session)
                
                assert result.retailer_name == "Test Retailer"
                assert result.amount == 10.0

    @pytest.mark.asyncio
    async def test_parse_check_from_api_503_error_with_retry(self):
        """Тест: Проверка обработки HTTP 503 ошибки с повторной попыткой"""
        image_data = b"fake image data"
        
        # Создаем мок-сессию и сначала возвращаем 503 ошибку, затем успешный ответ
        first_response = AsyncMock()
        first_response.status = 503
        first_response.text = AsyncMock(return_value="Service Unavailable")
        
        second_response = AsyncMock()
        second_response.status = 200
        second_response.json = AsyncMock(return_value={
            "code": 1,
            "data": {
                "json": {
                    "user": "Test Retailer",
                    "totalSum": 2000,
                    "items": [{"name": "Test Item"}],
                    "dateTime": "2023-01-01T10:00"
                }
            }
        })
        
        # Используем side_effect для возврата разных ответов при разных вызовах
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(side_effect=[first_response, second_response])
        
        with patch('config.CHECK_API_TOKEN', 'test_token'), \
             patch('config.CHECK_API_URL', 'https://proverkacheka.com/api/v1/check/get'), \
             patch('config.CHECK_API_TIMEOUT', 10), \
             patch('asyncio.sleep', new=AsyncMock()):  # Мокируем sleep, чтобы тесты не ждали
                
                # Запускаем функцию - она должна выполниться успешно после повторных попыток
                result = await parse_check_from_api(image_data, session=mock_session)
                
                assert result.retailer_name == "Test Retailer"
                assert result.amount == 20.0

    @pytest.mark.asyncio
    async def test_parse_check_from_api_client_os_error_with_retry(self):
        """Тест: Проверка обработки сетевых ошибок типа ClientOSError с повторной попыткой"""
        import aiohttp
        
        image_data = b"fake image data"
        
        # Создаем мок-сессию, которая выбрасывает ClientOSError
        mock_response = AsyncMock()
        mock_response.__aenter__ = AsyncMock(side_effect=aiohttp.ClientOSError("Network error"))
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        
        with patch('config.CHECK_API_TOKEN', 'test_token'), \
             patch('config.CHECK_API_URL', 'https://proverkacheka.com/api/v1/check/get'), \
             patch('config.CHECK_API_TIMEOUT', 10), \
             patch('asyncio.sleep', new=AsyncMock()):  # Мокируем sleep, чтобы тесты не ждали
            
            # Проверим, что после нескольких неудачных попыток вызывается ошибка
            with pytest.raises(CheckApiRecognitionError) as exc_info:
                await parse_check_from_api(image_data, session=mock_session)
            
            assert "Не удалось выполнить запрос к API после" in str(exc_info.value)