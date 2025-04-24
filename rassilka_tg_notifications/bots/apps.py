import asyncio
from django.apps import AppConfig
from telethon import TelegramClient

from rassilka_tg_notifications.rassilka_tg_notifications.settings import API_ID, API_HASH, PHONE_NUMBER

# Сообщения
FIRST_TOUCH_MESSAGE = """
Добрый день!

Меня зовут Екатерина, менеджер по развитию образовательной платформы для архитекторов и девелоперов stemps.ru

Возможно уже что-то слышали о нас?)
"""

SECOND_TOUCH_MESSAGE = """
В прошлый раз не дописалась) 

Чтобы лишний раз не дёргала, не подскажете кто в вашей команде отвечает за обучение сотрудников?
"""

# Данные отправителя (должны совпадать с tasks.py)

SESSION_FILE = 'sender'


class BotsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bots'

    def ready(self):
        # Создание сообщений
        from .models import Message
        if not Message.objects.filter(text=FIRST_TOUCH_MESSAGE).exists():
            Message.objects.create(text=FIRST_TOUCH_MESSAGE, is_second_touch=False)
            print("First touch message created.")
        if not Message.objects.filter(text=SECOND_TOUCH_MESSAGE).exists():
            Message.objects.create(text=SECOND_TOUCH_MESSAGE, is_second_touch=True)
            print("Second touch message created.")

        # Проверка Telegram сессии
        client = TelegramClient(SESSION_FILE, API_ID, API_HASH)

        async def check_session():
            print("Checking Telegram session...")
            await client.connect()
            if not await client.is_user_authorized():
                print(f"Session not found or invalid. Requesting code for {PHONE_NUMBER}")
                await client.sign_in(phone=PHONE_NUMBER)
                code = input(f"Enter the code sent to {PHONE_NUMBER}: ")
                try:
                    await client.sign_in(code=code)
                    print("Telegram session created successfully!")
                except Exception as e:
                    print(f"Failed to create Telegram session: {str(e)}")
                    await client.disconnect()
                    return
            else:
                print("Telegram session already exists and is valid.")
            await client.disconnect()

        asyncio.run(check_session())
