import os
import django

# Инициализируем Django перед любыми импортами, связанными с Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rassilka_tg_notifications.settings')
django.setup()

from telethon import TelegramClient, events
from django.utils import timezone
from bots.models import User
from dotenv import load_dotenv
from asgiref.sync import sync_to_async

load_dotenv()

API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
SESSION_FILE = 'listener'

# Оборачиваем операции с базой данных в sync_to_async
get_user = sync_to_async(User.objects.get)
save_user = sync_to_async(lambda user: user.save())

async def handle_new_message(event):
    sender = await event.get_sender()
    telegram_id = str(sender.id)
    message_text = event.message.text

    print(f"Received message from {telegram_id}: {message_text}")

    try:
        # Используем sync_to_async для получения пользователя
        user = await get_user(telegram_id=telegram_id)
        print(f"Found user: {user.telegram_id}, current responded: {user.responded}")
        # Обновляем поле responded, если пользователь ответил
        if not user.responded:
            user.responded = True
            user.last_message_time = timezone.now()
            # Используем sync_to_async для сохранения пользователя
            await save_user(user)
            print(f"User {telegram_id} responded. Updated responded=True.")
        else:
            print(f"User {telegram_id} already marked as responded.")
    except User.DoesNotExist:
        print(f"User with telegram_id {telegram_id} not found.")
    except Exception as e:
        print(f"Error updating user {telegram_id}: {str(e)}")

async def main():
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    client.on(events.NewMessage(incoming=True))(handle_new_message)
    await client.start()
    print("Listening for new messages...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())