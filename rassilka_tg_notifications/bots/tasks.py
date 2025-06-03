import os
from telethon import TelegramClient
from .models import Bot
from django.utils import timezone
from concurrent.futures import ThreadPoolExecutor
from telethon.errors import PeerIdInvalidError, FloodWaitError
from dotenv import load_dotenv
import asyncio

load_dotenv()
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')

SESSION_FILE = 'sender'


def send_message(schedule):
    print(f"Starting send_message for user {schedule.user.telegram_id} at {timezone.now()}")

    try:
        bot = Bot.objects.first()
        if not bot:
            print("Bot not found. Please create a Bot instance in the admin panel.")
            raise ValueError("Bot not found. Please create a Bot instance in the admin panel.")

        if bot.is_banned and bot.banned_until and bot.banned_until <= timezone.now():
            print(f"Ban period ended for bot at {timezone.now()}. Resetting is_banned to False.")
            bot.is_banned = False
            bot.banned_until = None
            bot.save()

        if bot.is_banned and bot.banned_until and bot.banned_until > timezone.now():
            print(f"Bot is banned until {bot.banned_until}. Skipping message.")
            return False

        user = schedule.user
        print(f"User {user.telegram_id}: responded={user.responded}, is_second_touch={schedule.message.is_second_touch}, message_text='{schedule.message.text}'")

        if schedule.message.is_second_touch and user.responded:
            print(f"User {user.telegram_id} has responded. Skipping second touch message.")
            return True

        username = user.name
        message_text = schedule.message.text
        print(f"Sending message to {username}: {message_text}")

        def run_telegram_task():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                client = TelegramClient(SESSION_FILE, API_ID, API_HASH, loop=loop)

                async def send_telegram_message():
                    print(f"Connecting to Telegram for {username}...")
                    await client.connect()
                    if not await client.is_user_authorized():
                        await client.start(phone=PHONE_NUMBER)
                        print("Authorized successfully.")

                    if not username.startswith('@'):
                        username_with_at = '@' + username
                    else:
                        username_with_at = username

                    print(f"Fetching entity for {username_with_at}...")
                    try:
                        entity = await client.get_entity(username_with_at)
                        print(f"Entity found: {entity}")
                    except PeerIdInvalidError:
                        print(f"Error: The username {username_with_at} is invalid or inaccessible.")
                        raise ValueError(f"Cannot access user with username {username_with_at}")

                    print(f"Sending message to {username_with_at}...")
                    await client.send_message(entity, message_text)
                    print("Message sent, disconnecting...")
                    await client.disconnect()

                loop.run_until_complete(send_telegram_message())
            finally:
                loop.close()

        with ThreadPoolExecutor() as executor:
            future = executor.submit(run_telegram_task)
            future.result()

        user.last_message_time = timezone.now()
        user.save()
        print(f"Message sent to {username} at {timezone.now()}")
        return True

    except FloodWaitError as e:
        print(f"Flood wait error: {e.seconds} seconds. Bot is likely banned.")
        bot = Bot.objects.first()
        if bot:
            bot.is_banned = True
            bot.banned_until = timezone.now() + timezone.timedelta(seconds=e.seconds)
            bot.save()
            print(f"Bot marked as banned until {bot.banned_until}.")
        return False
    except ValueError as e:
        print(f"Error: {str(e)} at {timezone.now()}")
        return True
    except Exception as e:
        print(f"Error sending message: {str(e)} at {timezone.now()}")
        return False
