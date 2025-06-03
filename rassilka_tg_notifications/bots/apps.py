import os

from django.apps import AppConfig
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')

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

SESSION_FILE = 'sender'


class BotsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bots'

    def ready(self):
        pass