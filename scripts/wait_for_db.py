import asyncio

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import make_engine


async def main() -> None:
    engine = make_engine(get_settings())
    try:
        for _attempt in range(30):
            try:
                async with engine.connect() as connection:
                    await connection.execute(text("SELECT 1"))
                print("PostgreSQL is ready")
                return
            except Exception:
                await asyncio.sleep(2)
        raise SystemExit("PostgreSQL did not become ready")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
