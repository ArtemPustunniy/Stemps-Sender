import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rassilka_tg_notifications.settings')

app = Celery('rassilka_tg_notifications')
app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

app.conf.beat_schedule = {
    'check-tasks-every-10-seconds': {
        'task': 'django_celery_beat.schedulers:DatabaseScheduler',
        'schedule': 10.0,
    },
}