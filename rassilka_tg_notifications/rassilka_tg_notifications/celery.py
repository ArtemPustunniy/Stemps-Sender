import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rassilka_tg_notifications.settings')

app = Celery('rassilka_tg_notifications')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()