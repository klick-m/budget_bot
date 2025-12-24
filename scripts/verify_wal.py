import asyncio
import aiosqlite

async def check():
    async with aiosqlite.connect("transactions.db") as db:
        cursor = await db.execute("PRAGMA journal_mode;")
        mode = await cursor.fetchone()
        print(f"Current mode: {mode[0]}")
        assert mode[0].lower() == 'wal', "WAL mode not active!"

if __name__ == "__main__":
    asyncio.run(check())