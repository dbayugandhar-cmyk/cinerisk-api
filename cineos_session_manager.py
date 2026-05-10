"""
CINEOS Telegram Session Manager
3 sessions = 3x throughput = no rate limit issues.
Each session uses a different Telegram account.
Rotates automatically when one hits rate limit.
"""
import asyncio, json, os
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from datetime import datetime

API_ID   = 38636931
API_HASH = "852280f65386a00114ff7453eac7849b"

# Session files — add more accounts as needed
SESSIONS = [
    'cineos_session',      # Primary
    'cineos_session_2',    # Secondary
    'cineos_session_3',    # Tertiary
]

class SessionManager:
    """
    Rotates between multiple Telegram sessions.
    When one hits rate limit, switches to next.
    3 sessions = approximately 3x throughput.
    """
    def __init__(self):
        self.clients    = []
        self.current    = 0
        self.rate_limits = {}

    async def start(self):
        """Start all available sessions."""
        started = 0
        for session in SESSIONS:
            try:
                client = TelegramClient(session, API_ID, API_HASH)
                await client.start()
                self.clients.append(client)
                started += 1
                print(f"  Session {session}: connected")
            except Exception as e:
                print(f"  Session {session}: {str(e)[:40]}")

        print(f"  {started}/{len(SESSIONS)} sessions active")
        return started

    async def get_client(self) -> TelegramClient:
        """Get next available client, skipping rate-limited ones."""
        now = datetime.now().timestamp()
        attempts = 0

        while attempts < len(self.clients):
            client = self.clients[self.current % len(self.clients)]
            session_name = SESSIONS[self.current % len(SESSIONS)]

            # Check if rate limited
            if session_name in self.rate_limits:
                wait_until = self.rate_limits[session_name]
                if now < wait_until:
                    self.current += 1
                    attempts += 1
                    continue
                else:
                    del self.rate_limits[session_name]

            return client, session_name

        # All limited — wait for first one to clear
        if self.rate_limits:
            soonest = min(self.rate_limits.values())
            wait_s  = max(0, soonest - now)
            print(f"  All sessions rate limited — waiting {wait_s:.0f}s")
            await asyncio.sleep(wait_s + 1)
            self.rate_limits.clear()
            return self.clients[0], SESSIONS[0]

        return self.clients[0], SESSIONS[0]

    def mark_rate_limited(self, session_name: str, wait_seconds: int):
        """Mark a session as rate limited."""
        until = datetime.now().timestamp() + wait_seconds
        self.rate_limits[session_name] = until
        self.current += 1
        print(f"  Session {session_name} rate limited for {wait_seconds}s "
              f"— switching to next")

    async def get_messages_safe(self, username: str,
                                limit: int = 200) -> list:
        """
        Get messages from a channel, rotating sessions on rate limit.
        """
        for attempt in range(len(self.clients) + 1):
            try:
                client, session_name = await self.get_client()
                entity   = await client.get_entity(username)
                messages = await client.get_messages(entity, limit=limit)
                return list(messages)

            except FloodWaitError as e:
                self.mark_rate_limited(session_name, e.seconds)
                await asyncio.sleep(2)
                continue
            except Exception as e:
                return []

        return []

    async def stop(self):
        for client in self.clients:
            try:
                await client.disconnect()
            except: pass

async def test_sessions():
    print("="*55)
    print("  CINEOS SESSION MANAGER TEST")
    print("="*55)
    print()

    mgr = SessionManager()
    started = await mgr.start()

    if started == 0:
        print("  No sessions available")
        print("  To add sessions:")
        print("  1. Create new Telegram account")
        print("  2. Run: python3 -c \"")
        print("     from telethon import TelegramClient")
        print("     import asyncio")
        print("     async def main():")
        print("         c = TelegramClient('cineos_session_2', API_ID, API_HASH)")
        print("         await c.start()")
        print("         await c.disconnect()")
        print("     asyncio.run(main())\"")
    else:
        print(f"\n  Testing channel fetch with {started} sessions...")
        msgs = await mgr.get_messages_safe('telegram', limit=5)
        print(f"  Test fetch: {len(msgs)} messages retrieved")
        print(f"\n  With {started} sessions:")
        print(f"  Throughput: ~{started * 30} channels/hour")
        print(f"  (vs 30 channels/hour with 1 session)")

    await mgr.stop()
    return started

asyncio.run(test_sessions())
