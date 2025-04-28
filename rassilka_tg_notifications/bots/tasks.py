import os

from celery import shared_task
from telethon import TelegramClient
from .models import Schedule, User
import asyncio
from concurrent.futures import ThreadPoolExecutor
from telethon.errors import PeerIdInvalidError
from django.utils import timezone
from dotenv import load_dotenv

load_dotenv()
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')

SESSION_FILE = 'sender'

@shared_task
def send_message(schedule_id):
    print(f"Starting task send_message for schedule_id {schedule_id}")

    try:
        # Получаем объект Schedule
        schedule = Schedule.objects.get(id=schedule_id)
        if schedule.sent:
            print(f"Message {schedule_id} already sent.")
            return

        # Проверяем, ответил ли пользователь
        user = schedule.user
        if user.responded and schedule.message.is_second_touch:
            # Если пользователь ответил и это второе касание, помечаем расписание как завершённое и не отправляем
            schedule.sent = True
            schedule.save()
            print(f"User {user.telegram_id} has already responded. Skipping second touch message.")
            return

        # Извлекаем все данные, которые могут потребовать доступ к базе данных
        telegram_id = int(schedule.user.telegram_id)  # Преобразуем строку в int
        message_text = schedule.message.text

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
                    await client.start()
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
        print(f"Message {schedule_id} sent to {telegram_id}")

    except Exception as e:
        print(f"Error sending message {schedule_id}: {str(e)}")
        raise