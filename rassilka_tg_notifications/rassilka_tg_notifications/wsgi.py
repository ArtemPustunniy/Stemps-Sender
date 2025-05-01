"""
WSGI config for rassilka_tg_notifications project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
from django.core.wsgi import get_wsgi_application

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rassilka_tg_notifications.settings')

# Запускаем планировщик при старте сервера
from bots.scheduler import start_scheduler
start_scheduler()

application = get_wsgi_application()