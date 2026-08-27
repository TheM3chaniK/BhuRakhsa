"""Clean all uploaded citizen cases and evidence records from PostgreSQL.
Preserves users, administrative areas, officer assignments, and reference properties.
"""

import asyncio
from sqlalchemy import text
from app.db.session import async_session_factory


async def clean_cases_data():
    print("🧹 Purging all uploaded citizen cases and evidence records...")
    async with async_session_factory() as db:
        await db.execute(text("TRUNCATE TABLE cases CASCADE;"))
        await db.execute(text("TRUNCATE TABLE documents CASCADE;"))
        await db.execute(text("TRUNCATE TABLE audit_events CASCADE;"))
        await db.commit()
        print("✨ All uploaded citizen cases successfully removed! Users and areas preserved.")


if __name__ == "__main__":
    asyncio.run(clean_cases_data())
