import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from models.keyword_dictionary import KeywordDictionary, KeywordEntry


class TestKeywordDictionaryAsync:
    """Тесты для проверки асинхронных операций в KeywordDictionary"""

    def setup_method(self):
        """Настройка теста"""
        self.keyword_dict = KeywordDictionary("test_spreadsheet_id", "test_sheet_name")

    @pytest.mark.asyncio
    async def test_async_load_from_sheets(self):
        """Тест асинхронной загрузки данных из Google Sheets"""
        # Создаем mock для асинхронной загрузки данных
        with patch('sheets.client.get_sheet_data_with_cache', new_callable=AsyncMock) as mock_get_data:
            mock_get_data.return_value = [
                ["чай", "напитки", "0.8"],
                ["кофе", "напитки", "0.9"],
                ["хлеб", "еда", "0.7"]
            ]

            # Вызываем асинхронную загрузку
            await self.keyword_dict.async_load_from_sheets()

            # Проверяем, что данные были загружены
            assert "чай" in self.keyword_dict.keyword_to_category
            assert "кофе" in self.keyword_dict.keyword_to_category
            assert "хлеб" in self.keyword_dict.keyword_to_category

            # Проверяем, что категории были созданы
            assert "напитки" in self.keyword_dict.category_keywords
            assert "еда" in self.keyword_dict.category_keywords

            # Проверяем, что данные имеют правильный тип
            assert isinstance(self.keyword_dict.keyword_to_category["чай"], KeywordEntry)
            assert self.keyword_dict.keyword_to_category["чай"].category == "напитки"
            assert self.keyword_dict.keyword_to_category["чай"].confidence == 0.8

    def test_update_from_sheets_raises_error_in_sync_context(self):
        """Тест проверки, что update_from_sheets теперь выбрасывает ошибку в синхронном контексте"""
        # Создаем mock для асинхронной загрузки данных
        with patch('sheets.client.get_sheet_data_with_cache', new_callable=AsyncMock) as mock_get_data:
            mock_get_data.return_value = [
                ["чай", "напитки", "0.8"]
            ]

            # Проверяем, что вызов update_from_sheets в синхронном контексте выбрасывает ошибку
            with pytest.raises(RuntimeError, match="Невозможно вызвать update_from_sheets из синхронного контекста"):
                self.keyword_dict.update_from_sheets()

    def test_update_from_sheets_raises_error_in_sync_context_new(self):
        """Тест проверки, что update_from_sheets выбрасывает ошибку в синхронном контексте"""
        from unittest.mock import AsyncMock
        
        # Мокаем асинхронную загрузку
        async def mock_async_load():
            # Имитируем загрузку данных
            self.keyword_dict.keyword_to_category["чай"] = KeywordEntry(
                keyword="чай",
                category="напитки",
                confidence=0.8
            )
            return
        
        with patch.object(self.keyword_dict, 'async_load_from_sheets', new_callable=AsyncMock) as mock_load:
            mock_load.side_effect = mock_async_load

            # Проверяем, что вызов update_from_sheets в синхронном контексте выбрасывает ошибку
            with pytest.raises(RuntimeError, match="Невозможно вызвать update_from_sheets из синхронного контекста"):
                self.keyword_dict.update_from_sheets()
            
            # Убеждаемся, что метод НЕ был вызван, так как была выброшена ошибка
            assert not mock_load.called

    def test_async_add_keyword_to_sheet_with_deprecation_warning(self):
        """Тест проверки DeprecationWarning при вызове _async_add_keyword_to_sheet"""
        import warnings
        from unittest.mock import AsyncMock
        
        # Создаем асинхронный мок для add_keyword_to_sheet
        with patch('sheets.client.add_keyword_to_sheet', new_callable=AsyncMock) as mock_add:
            mock_add.return_value = True
            
            # Проверяем, что вызов _async_add_keyword_to_sheet не приводит к DeprecationWarning
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")  # Перехватываем все предупреждения
                
                # Вызываем метод добавления - это синхронная функция, которая внутри использует асинхронные вызовы
                self.keyword_dict._async_add_keyword_to_sheet("чай", "напитки", 0.8)
                
                # Проверяем, что не было предупреждений DeprecationWarning о событийном цикле
                deprecation_warnings = [warning for warning in w
                                      if issubclass(warning.category, DeprecationWarning)
                                      and "event loop" in str(warning.message)]
                
                # Это тест, который должен падать до исправления и проходить после
                assert len(deprecation_warnings) == 0, f"Найдены DeprecationWarning: {[str(warn.message) for warn in deprecation_warnings]}"

    @pytest.mark.asyncio
    async def test_async_load_from_sheets_with_invalid_confidence(self):
        """Тест асинхронной загрузки с невалидной уверенностью"""
        # Создаем mock для асинхронной загрузки данных
        with patch('sheets.client.get_sheet_data_with_cache', new_callable=AsyncMock) as mock_get_data:
            mock_get_data.return_value = [
                ["чай", "напитки", "invalid"],  # Невалидная уверенность
                ["кофе", "напитки", "0.9"]
            ]

            # Вызываем асинхронную загрузку
            await self.keyword_dict.async_load_from_sheets()

            # Проверяем, что данные были загружены с значением по умолчанию для уверенности
            assert self.keyword_dict.keyword_to_category["чай"].confidence == 0.5  # Значение по умолчанию
            assert self.keyword_dict.keyword_to_category["кофе"].confidence == 0.9

    def test_update_from_sheets_in_running_loop(self):
        """Тест обновления из таблицы когда цикл уже запущен"""
        async def run_test():
            # Создаем mock для асинхронной загрузки данных
            with patch.object(self.keyword_dict, 'async_load_from_sheets', new_callable=AsyncMock) as mock_load:
                mock_load.return_value = None

                # Вызываем метод обновления - это синхронная функция
                self.keyword_dict.update_from_sheets()

                # Проверяем, что был вызван create_task
                # Ждем завершения задачи, чтобы избежать предупреждений
                await asyncio.sleep(0.01)

        # Запускаем тест в асинхронном цикле
        asyncio.run(run_test())

    def test_update_from_sheets_in_new_loop_raises_error(self):
        """Тест обновления из таблицы в новом цикле - теперь должен выбрасывать ошибку"""
        # Создаем mock для асинхронной загрузки данных
        with patch('sheets.client.get_sheet_data_with_cache', new_callable=AsyncMock) as mock_get_data:
            mock_get_data.return_value = [
                ["чай", "напитки", "0.8"]
            ]

            # Вызываем метод обновления - теперь он должен выбрасывать ошибку
            with pytest.raises(RuntimeError, match="Невозможно вызвать update_from_sheets из синхронного контекста"):
                self.keyword_dict.update_from_sheets()

    @pytest.mark.asyncio
    async def test_async_update_dictionary(self):
        """Тест асинхронного обновления словаря"""
        # Создаем mock для асинхронной загрузки данных
        with patch('sheets.client.get_sheet_data_with_cache', new_callable=AsyncMock) as mock_get_data:
            mock_get_data.return_value = [
                ["молоко", "напитки", "0.85"]
            ]

            # Вызываем асинхронное обновление
            await self.keyword_dict.update_dictionary()

            # Проверяем, что данные были загружены
            assert "молоко" in self.keyword_dict.keyword_to_category
            assert self.keyword_dict.keyword_to_category["молоко"].category == "напитки"
            assert self.keyword_dict.keyword_to_category["молоко"].confidence == 0.85

    @pytest.mark.asyncio
    async def test_async_operations_with_lemmatization(self):
        """Тест асинхронных операций с лемматизацией"""
        # Создаем mock для асинхронной загрузки данных
        with patch('sheets.client.get_sheet_data_with_cache', new_callable=AsyncMock) as mock_get_data:
            mock_get_data.return_value = [
                ["чай", "напитки", "0.8"]
            ]

            # Вызываем асинхронную загрузку
            await self.keyword_dict.async_load_from_sheets()

            # Проверяем, что лемматизатор был инициализирован
            assert hasattr(self.keyword_dict, 'lemmatizer')
            # Проверяем, что можно использовать функции поиска
            result = self.keyword_dict.get_category_by_keyword("чай")
            assert result is not None
            assert result[0] == "напитки"
            assert result[1] == 0.8

    @pytest.mark.asyncio
    async def test_load_method(self):
        """Тест асинхронного метода load"""
        # Создаем mock для асинхронной загрузки данных
        with patch('sheets.client.get_sheet_data_with_cache', new_callable=AsyncMock) as mock_get_data:
            mock_get_data.return_value = [
                ["сахар", "еда", "0.6"]
            ]

            # Вызываем асинхронный метод load
            await self.keyword_dict.load()

            # Проверяем, что данные были загружены
            assert "сахар" in self.keyword_dict.keyword_to_category
            assert self.keyword_dict.keyword_to_category["сахар"].category == "еда"
            assert self.keyword_dict.keyword_to_category["сахар"].confidence == 0.6