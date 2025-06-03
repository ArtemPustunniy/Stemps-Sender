import os
import asyncio
from django.core.management.base import BaseCommand
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')
SESSION_FILE = 'sender'


class Command(BaseCommand):
    help = 'Initialize or verify Telegram session'

    def handle(self, *args, **kwargs):
        client = TelegramClient(SESSION_FILE, API_ID, API_HASH)

        async def check_session():
            self.stdout.write("Checking Telegram session...")
            await client.connect()
            if not await client.is_user_authorized():
                self.stdout.write(f"Session not found or invalid. Requesting code for {PHONE_NUMBER}")
                await client.sign_in(phone=PHONE_NUMBER)
                code = input(f"Enter the code sent to {PHONE_NUMBER}: ")
                try:
                    await client.sign_in(code=code)
                    self.stdout.write(self.style.SUCCESS("Telegram session created successfully!"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Failed to create Telegram session: {str(e)}"))
                    await client.disconnect()
                    return
            else:
                self.stdout.write(self.style.SUCCESS("Telegram session already exists and is valid."))
            await client.disconnect()

        asyncio.run(check_session())