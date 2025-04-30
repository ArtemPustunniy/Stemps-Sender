import os
from celery import shared_task
from telethon import TelegramClient
from .models import Schedule, User, Bot
from django.utils import timezone
from concurrent.futures import ThreadPoolExecutor
from telethon.errors import PeerIdInvalidError, SessionPasswordNeededError, FloodWaitError
from celery.exceptions import Retry
from dotenv import load_dotenv
import asyncio

load_dotenv()
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')
TWO_FACTOR_PASSWORD = os.getenv('TWO_FACTOR_PASSWORD')

SESSION_FILE = 'sender'

@shared_task(bind=True)
def send_message(self, schedule_id):
    print(f"Starting task send_message for schedule_id {schedule_id} at {timezone.now()}")

    try:
        # Проверяем состояние бота
        bot = Bot.objects.first()  # Предполагаем, что у нас один бот
        if not bot:
            print("Bot not found. Please create a Bot instance in the admin panel.")
            raise ValueError("Bot not found. Please create a Bot instance in the admin panel.")

        # Если время фриза истекло, сбрасываем бан
        if bot.is_banned and bot.banned_until and bot.banned_until <= timezone.now():
            print(f"Ban period ended for bot at {timezone.now()}. Resetting is_banned to False.")
            bot.is_banned = False
            bot.banned_until = None
            bot.save()

        if bot.is_banned and bot.banned_until and bot.banned_until > timezone.now():
            # Если бот забанен, откладываем задачу до окончания фриза
            delay = (bot.banned_until - timezone.now()).total_seconds()
            print(f"Bot is banned until {bot.banned_until}. Retrying task after {delay} seconds.")
            raise self.retry(eta=bot.banned_until)

        # Получаем объект Schedule
        schedule = Schedule.objects.get(id=schedule_id)
        print(f"Schedule status: sent={schedule.sent}, scheduled_time={schedule.scheduled_time}")
        if schedule.sent:
            print(f"Message {schedule_id} already sent.")
            return

        # Извлекаем данные пользователя
        user = schedule.user
        print(f"User {user.telegram_id}: responded={user.responded}, is_second_touch={schedule.message.is_second_touch}, message_text='{schedule.message.text}'")

        # Извлекаем все данные, которые могут потребовать доступ к базе данных
        telegram_id = int(schedule.user.telegram_id)  # Преобразуем строку в int
        message_text = schedule.message.text
        print(f"Sending message to {telegram_id}: {message_text}")

        # Функция для выполнения работы с Telegram в отдельном потоке
        def run_telegram_task():
            # Создаем новый цикл событий для этого потока
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Создаем клиента Telegram, передавая цикл событий
                client = TelegramClient(SESSION_FILE, API_ID, API_HASH, loop=loop)

                # Определяем асинхронную функцию для отправки сообщения
                async def send_telegram_message():
                    print("Connecting to Telegram...")
                    try:
                        await client.start(phone=PHONE_NUMBER, password=lambda: TWO_FACTOR_PASSWORD)
                    except SessionPasswordNeededError:
                        print("Two-factor authentication password required but not provided.")
                        raise
                    print(f"Sending message to {telegram_id}...")

                    # Проверяем, существует ли пользователь
                    try:
                        entity = await client.get_input_entity(telegram_id)
                        print(f"Found entity: {entity}")
                    except PeerIdInvalidError:
                        print(f"Error: The Telegram ID {telegram_id} is invalid or inaccessible.")
                        raise ValueError(f"Cannot access user with ID {telegram_id}")

                    await client.send_message(telegram_id, message_text)
                    print("Message sent, disconnecting...")
                    await client.disconnect()

                # Выполняем асинхронный код в этом цикле
                loop.run_until_complete(send_telegram_message())
            finally:
                # Закрываем цикл событий
                loop.close()

        # Запускаем работу с Telegram в отдельном потоке
        with ThreadPoolExecutor() as executor:
            future = executor.submit(run_telegram_task)
            future.result()  # Ждем завершения

        # Обновляем статус отправки и время последнего сообщения
        schedule.sent = True
        schedule.save()
        user.last_message_time = timezone.now()
        user.save()
        print(f"Message {schedule_id} sent to {telegram_id} at {timezone.now()}")

    except FloodWaitError as e:
        print(f"Flood wait error: {e.seconds} seconds. Bot is likely banned.")
        bot = Bot.objects.first()
        if bot:
            bot.is_banned = True
            bot.save()  # Это вызовет метод save(), который установит banned_until
            print(f"Bot marked as banned until {bot.banned_until}.")
        raise self.retry(eta=timezone.now() + timezone.timedelta(seconds=e.seconds))
    except PeerIdInvalidError:
        print(f"Error: The Telegram ID {telegram_id} is invalid or inaccessible. Marking message as sent.")
        schedule.sent = True
        schedule.save()
    except Exception as e:
        print(f"Error sending message {schedule_id}: {str(e)} at {timezone.now()}")
        raise
