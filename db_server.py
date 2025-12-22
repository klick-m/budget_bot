from mcp.server.fastmcp import FastMCP
import sqlite3
import os

# Инициализируем сервер
mcp = FastMCP("sqlite")
DB_PATH = "transactions.db"

@mcp.tool()
def query_db(sql_query: str) -> str:
    """
    Выполняет SQL-запрос к базе данных transactions.db.
    Используй это для проверки данных (SELECT) или отладки.
    """
    # Проверка на существование файла
    if not os.path.exists(DB_PATH):
        return "Error: Database file transactions.db not found."

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(sql_query)
            
            # Если это SELECT - возвращаем данные
            if sql_query.strip().upper().startswith("SELECT"):
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                if not rows:
                    return "No results found."
                # Форматируем результат как список словарей для читаемости AI
                result = [dict(zip(columns, row)) for row in rows]
                return str(result)
            
            # Если это INSERT/UPDATE - коммитим
            conn.commit()
            return f"Query executed. Rows affected: {cursor.rowcount}"
            
    except Exception as e:
        return f"SQL Error: {str(e)}"

if __name__ == "__main__":
    mcp.run()