from django.utils import timezone
from datetime import timedelta
from .models import Account, User, Message, Schedule, Settings
import logging

logger = logging.getLogger('bots')


def create_schedules():
    settings = Settings.objects.first()
    if not settings:
        logger.error("Settings not found, cannot create schedules")
        return

    accounts = Account.objects.filter(is_active=True)
    users = User.objects.all()
    first_touch_message = Message.objects.filter(is_second_touch=False).first()

    if not first_touch_message:
        logger.error("No first touch message found")
        return

    if not accounts:
        logger.error("No active accounts found")
        return

    current_time = timezone.now()
    for i, user in enumerate(users):
        account = accounts[i % len(accounts)]
        scheduled_time = current_time + timedelta(minutes=settings.message_interval_minutes * i)
        Schedule.objects.create(
            user=user,
            account=account,
            message=first_touch_message,
            scheduled_time=scheduled_time
        )
        logger.info(f"Scheduled message for {user.telegram_id} at {scheduled_time}")