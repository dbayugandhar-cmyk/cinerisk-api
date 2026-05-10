import asyncio
from telethon import TelegramClient

API_ID = 38636931
API_HASH = "852280f65386a00114ff7453eac7849b"

async def main():
    client = TelegramClient('cineos_session', API_ID, API_HASH)
    await client.start()
    me = await client.get_me()
    print(f"Connected as: {me.first_name}")
    print(f"Phone: +{me.phone}")
    await client.disconnect()
    print("Session saved — ready for scanning")

asyncio.run(main())
