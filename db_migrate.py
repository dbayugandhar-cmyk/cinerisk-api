import asyncio, os, asyncpg

async def migrate():
    db = await asyncpg.connect(os.environ["DATABASE_URL"])
    print("Connected to Railway PostgreSQL")
    await db.execute("""
        CREATE TABLE IF NOT EXISTS scan_results (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            incident_id   UUID,
            film_title    TEXT,
            scan_time     TIMESTAMPTZ DEFAULT NOW(),
            hits_found    INTEGER DEFAULT 0,
            platforms     TEXT[],
            first_hit_url TEXT,
            gap_minutes   INTEGER,
            scan_query    TEXT
        )
    """)
    print("scan_results table ready")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_scan_film ON scan_results (film_title, scan_time DESC)")
    print("index created")
    await db.close()
    print("Migration complete")

asyncio.run(migrate())
