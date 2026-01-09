# -*- coding: utf-8 -*-
# services/analytics_service.py
import asyncio
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict

import matplotlib.pyplot as plt
import io

from services.repository import TransactionRepository
from config import logger


class AnalyticsService:
    """
    Сервис для аналитики и агрегации транзакций.
    Предоставляет методы для получения статистики по расходам и доходам.
    """
    
    def __init__(self, repository: TransactionRepository):
        self.repository = repository

    async def get_monthly_expenses_by_category(self, user_id: int) -> Dict[str, float]:
        """
        Возвращает агрегированные расходы по категориям за текущий месяц для указанного пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Словарь с категориями и суммами расходов
        """
        # Получаем начало и конец текущего месяца
        now = datetime.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Форматируем даты для SQL-запроса
        start_date = start_of_month.strftime('%Y-%m-%d %H:%M:%S')
        
        async with self.repository._get_connection() as db:
            # Запрашиваем расходы за текущий месяц для конкретного пользователя
            cursor = await db.execute(
                """
                SELECT category, SUM(amount) as total
                FROM transactions
                WHERE user_id = ? 
                AND type = 'Расход'
                AND created_at >= ?
                GROUP BY category
                ORDER BY total DESC
                """,
                (user_id, start_date)
            )
            rows = await cursor.fetchall()
            
            # Формируем результат
            expenses_by_category = {}
            for row in rows:
                category, total = row
                expenses_by_category[category] = float(total)
                
        return expenses_by_category

    async def get_monthly_income_by_category(self, user_id: int) -> Dict[str, float]:
        """
        Возвращает агрегированные доходы по категориям за текущий месяц для указанного пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Словарь с категориями и суммами доходов
        """
        # Получаем начало и конец текущего месяца
        now = datetime.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Форматируем даты для SQL-запроса
        start_date = start_of_month.strftime('%Y-%m-%d %H:%M:%S')
        
        async with self.repository._get_connection() as db:
            # Запрашиваем доходы за текущий месяц для конкретного пользователя
            cursor = await db.execute(
                """
                SELECT category, SUM(amount) as total
                FROM transactions
                WHERE user_id = ? 
                AND type = 'Доход'
                AND created_at >= ?
                GROUP BY category
                ORDER BY total DESC
                """,
                (user_id, start_date)
            )
            rows = await cursor.fetchall()
            
            # Формируем результат
            income_by_category = {}
            for row in rows:
                category, total = row
                income_by_category[category] = float(total)
                
        return income_by_category

    async def get_monthly_summary(self, user_id: int) -> Dict[str, float]:
        """
        Возвращает общий итог расходов и доходов за текущий месяц для указанного пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Словарь с итоговыми суммами расходов и доходов
        """
        # Получаем начало текущего месяца
        now = datetime.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start_date = start_of_month.strftime('%Y-%m-%d %H:%M:%S')
        
        async with self.repository._get_connection() as db:
            # Запрашиваем итоги за текущий месяц для конкретного пользователя
            cursor = await db.execute(
                """
                SELECT type, SUM(amount) as total
                FROM transactions
                WHERE user_id = ? 
                AND created_at >= ?
                GROUP BY type
                """,
                (user_id, start_date)
            )
            rows = await cursor.fetchall()
            
            # Формируем результат
            summary = {"Расход": 0.0, "Доход": 0.0}
            for row in rows:
                trans_type, total = row
                summary[trans_type] = float(total)
                
        return summary

    async def generate_expenses_pie_chart(self, user_id: int, title: str = "Расходы по категориям") -> io.BytesIO:
        """
        Генерирует круговую диаграмму расходов по категориям за текущий месяц.
        
        Args:
            user_id: ID пользователя
            title: Заголовок диаграммы
            
        Returns:
            BytesIO объект с изображением диаграммы
        """
        # Получаем данные по расходам
        expenses_data = await self.get_monthly_expenses_by_category(user_id)
        
        if not expenses_data:
            # Если нет данных, создаем диаграмму с сообщением
            fig, ax = plt.subplots(figsize=(10, 7))
            ax.text(0.5, 0.5, 'Нет данных\nза текущий месяц', 
                   horizontalalignment='center', verticalalignment='center',
                   fontsize=14, transform=ax.transAxes)
            ax.set_title(title, fontsize=16)
            ax.axis('off')  # Скрываем оси, так как нет секторов
        else:
            # Подготовка данных для диаграммы
            categories = list(expenses_data.keys())
            amounts = list(expenses_data.values())
            
            # Создание диаграммы
            fig, ax = plt.subplots(figsize=(10, 7))
            
            # Используем разные цвета для секторов
            colors = plt.cm.Set3(range(len(categories)))
            
            # Построение круговой диаграммы
            wedges, texts, autotexts = ax.pie(
                amounts, 
                labels=categories, 
                autopct='%1.1f%%',
                colors=colors,
                startangle=90,
                textprops={'fontsize': 10}
            )
            
            # Улучшаем внешний вид текста
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')
                
            ax.set_title(title, fontsize=16)
        
        # Сохраняем диаграмму в BytesIO
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', bbox_inches='tight', dpi=100)
        img_buffer.seek(0)
        
        # Закрываем фигуру, чтобы освободить память
        plt.close(fig)
        
        return img_buffer

    async def generate_income_pie_chart(self, user_id: int, title: str = "Доходы по категориям") -> io.BytesIO:
        """
        Генерирует круговую диаграмму доходов по категориям за текущий месяц.
        
        Args:
            user_id: ID пользователя
            title: Заголовок диаграммы
            
        Returns:
            BytesIO объект с изображением диаграммы
        """
        # Получаем данные по доходам
        income_data = await self.get_monthly_income_by_category(user_id)
        
        if not income_data:
            # Если нет данных, создаем диаграмму с сообщением
            fig, ax = plt.subplots(figsize=(10, 7))
            ax.text(0.5, 0.5, 'Нет данных\nза текущий месяц', 
                   horizontalalignment='center', verticalalignment='center',
                   fontsize=14, transform=ax.transAxes)
            ax.set_title(title, fontsize=16)
            ax.axis('off')  # Скрываем оси, так как нет секторов
        else:
            # Подготовка данных для диаграммы
            categories = list(income_data.keys())
            amounts = list(income_data.values())
            
            # Создание диаграммы
            fig, ax = plt.subplots(figsize=(10, 7))
            
            # Используем разные цвета для секторов
            colors = plt.cm.Set3(range(len(categories)))
            
            # Построение круговой диаграммы
            wedges, texts, autotexts = ax.pie(
                amounts, 
                labels=categories, 
                autopct='%1.1f%%',
                colors=colors,
                startangle=90,
                textprops={'fontsize': 10}
            )
            
            # Улучшаем внешний вид текста
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')
                
            ax.set_title(title, fontsize=16)
        
        # Сохраняем диаграмму в BytesIO
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', bbox_inches='tight', dpi=100)
        img_buffer.seek(0)
        
        # Закрываем фигуру, чтобы освободить память
        plt.close(fig)
        
        return img_buffer