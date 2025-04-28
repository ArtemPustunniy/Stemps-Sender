default_app_config = 'rassilka_tg_notifications.apps.RassilkaTgNotificationsConfig'

from .celery import app as celery_app

__all__ = ('celery_app',)
