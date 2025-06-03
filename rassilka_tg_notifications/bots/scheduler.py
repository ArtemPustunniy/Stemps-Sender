import os
import time
from threading import Thread, Lock
from datetime import timezone
from django.utils import timezone as django_timezone
from django.db import transaction

scheduler_lock = Lock()


def process_schedules():
    from bots.models import FirstTouchSchedule, SecondTouchSchedule, Settings
    from bots.tasks import send_message

    now = django_timezone.localtime(django_timezone.now())
    current_hour = now.hour
    settings = Settings.objects.first() or Settings.objects.create()
    print(f"Checking schedules at {now} (local time) with message_interval_minutes={settings.message_interval_minutes}")

    if 11 <= current_hour < 21:
        first_touch = FirstTouchSchedule.objects.filter(
            sent=False,
            scheduled_time__lte=now
        ).order_by('scheduled_time').first()

        if first_touch:
            print(f"Processing first touch for user {first_touch.user.telegram_id}")
            success = send_message(first_touch)
            if success:
                first_touch.sent = True
                first_touch.save()
                print(f"First touch for user {first_touch.user.telegram_id} processed successfully")
            else:
                print(f"Failed to process first touch for user {first_touch.user.telegram_id}")

        second_touch = SecondTouchSchedule.objects.filter(
            sent=False,
            scheduled_time__lte=now
        ).order_by('scheduled_time').first()

        if second_touch:
            print(f"Processing second touch for user {second_touch.user.telegram_id}")
            success = send_message(second_touch)
            if success:
                second_touch.sent = True
                second_touch.save()
                print(f"Second touch for user {second_touch.user.telegram_id} processed successfully")
            else:
                print(f"Failed to process second touch for user {second_touch.user.telegram_id}")

        if not first_touch and not second_touch:
            print("No schedules to process at this time")
    else:
        print("Outside working hours (11:00–19:00), skipping schedule processing")


def process_pending_users():
    from bots.models import PendingUser, User, Settings, FirstTouchSchedule, SecondTouchSchedule, Message, Bot
    from django.utils import timezone as django_timezone
    from datetime import timedelta

    now = django_timezone.localtime(django_timezone.now())
    current_hour = now.hour
    settings = Settings.objects.first() or Settings.objects.create()
    print(f"Checking pending users at {now} (local time) with message_interval_minutes={settings.message_interval_minutes}")

    if current_hour < 11:
        pending_users = PendingUser.objects.filter(is_processed=False).order_by('created_at')
        if pending_users.exists():
            print(f"Found {pending_users.count()} pending users, but it's before 11:00. Waiting...")
        else:
            print("No pending users to process")
        return

    with scheduler_lock:
        with transaction.atomic():
            pending_users = PendingUser.objects.select_for_update().filter(is_processed=False).order_by('created_at')
            if pending_users.exists():
                first_touch_message = Message.objects.filter(is_second_touch=False).first()
                second_touch_message = Message.objects.filter(is_second_touch=True).first()
                if not first_touch_message or not second_touch_message:
                    print("Messages not found, cannot schedule messages.")
                    return

                bot = Bot.objects.first() or Bot.objects.create(name="Main Bot")

                last_first_touch = FirstTouchSchedule.objects.filter(sent=False).order_by('-scheduled_time').first()
                last_second_touch = SecondTouchSchedule.objects.filter(sent=False).order_by('-scheduled_time').first()

                base_time = django_timezone.now()
                print(f"Base time (UTC): {base_time}")

                for pending_user in pending_users:
                    print(f"Processing pending user: {pending_user.telegram_id} ({pending_user.name}) at {now}")
                    user = User.objects.filter(telegram_id=pending_user.telegram_id).first()

                    existing_first_touch = FirstTouchSchedule.objects.filter(user__telegram_id=pending_user.telegram_id, sent=False).exists()
                    existing_second_touch = SecondTouchSchedule.objects.filter(user__telegram_id=pending_user.telegram_id, sent=False).exists()

                    if user and (existing_first_touch or existing_second_touch):
                        print(f"User {pending_user.telegram_id} already has scheduled (unsent) touches, skipping.")
                        pending_user.is_processed = True
                        pending_user.save()
                        continue

                    user, created = User.objects.get_or_create(
                        telegram_id=pending_user.telegram_id,
                        defaults={'name': pending_user.name}
                    )
                    if created:
                        print(f"User {user.telegram_id} created successfully")
                    else:
                        print(f"User {user.telegram_id} already exists")

                    pending_user.is_processed = True
                    pending_user.save()

                    if not last_first_touch:
                        first_touch_time = base_time + timedelta(minutes=2)
                    else:
                        last_first_touch_time = last_first_touch.scheduled_time
                        first_touch_time = last_first_touch_time + timedelta(minutes=settings.message_interval_minutes)

                    if bot.is_banned and bot.banned_until and bot.banned_until > first_touch_time:
                        first_touch_time = bot.banned_until
                        print(f"First touch time adjusted Cane to ban: {first_touch_time}")

                    local_first_touch_time = django_timezone.localtime(first_touch_time)
                    if local_first_touch_time.hour < 11:
                        local_first_touch_time = local_first_touch_time.replace(hour=11, minute=0, second=0, microsecond=0)
                        first_touch_time = local_first_touch_time.astimezone(timezone.utc)
                    elif local_first_touch_time.hour >= 21:
                        local_first_touch_time = (local_first_touch_time + timedelta(days=1)).replace(hour=11, minute=0, second=0, microsecond=0)
                        first_touch_time = local_first_touch_time.astimezone(timezone.utc)

                    while FirstTouchSchedule.objects.filter(
                        sent=False,
                        scheduled_time__range=(
                            first_touch_time - timedelta(minutes=1),
                            first_touch_time + timedelta(minutes=1)
                        )
                    ).exclude(user=user).exists():
                        first_touch_time += timedelta(minutes=settings.message_interval_minutes)
                        local_first_touch_time = django_timezone.localtime(first_touch_time)
                        if local_first_touch_time.hour >= 21:
                            local_first_touch_time = (local_first_touch_time + timedelta(days=1)).replace(hour=11, minute=0, second=0, microsecond=0)
                            first_touch_time = local_first_touch_time.astimezone(timezone.utc)

                    first_touch = FirstTouchSchedule.objects.create(
                        user=user,
                        message=first_touch_message,
                        scheduled_time=first_touch_time
                    )
                    print(f"Scheduled first touch for {user.telegram_id} at {django_timezone.localtime(first_touch_time)} (local time) (ID: {first_touch.id})")

                    if not last_second_touch:
                        second_touch_time = first_touch_time + timedelta(minutes=settings.second_touch_delay_minutes)
                    else:
                        last_second_touch_time = last_second_touch.scheduled_time
                        second_touch_time = last_second_touch_time + timedelta(minutes=settings.message_interval_minutes)

                    if bot.is_banned and bot.banned_until and bot.banned_until > second_touch_time:
                        second_touch_time = bot.banned_until
                        print(f"Second touch time adjusted due to ban: {second_touch_time}")

                    local_second_touch_time = django_timezone.localtime(second_touch_time)
                    if local_second_touch_time.hour < 11:
                        local_second_touch_time = local_second_touch_time.replace(hour=11, minute=0, second=0, microsecond=0)
                        second_touch_time = local_second_touch_time.astimezone(timezone.utc)
                    elif local_second_touch_time.hour >= 21:
                        local_second_touch_time = (local_second_touch_time + timedelta(days=1)).replace(hour=11, minute=0, second=0, microsecond=0)
                        second_touch_time = local_second_touch_time.astimezone(timezone.utc)

                    while SecondTouchSchedule.objects.filter(
                        sent=False,
                        scheduled_time__range=(
                            second_touch_time - timedelta(minutes=1),
                            second_touch_time + timedelta(minutes=1)
                        )
                    ).exclude(user=user).exists():
                        second_touch_time += timedelta(minutes=settings.message_interval_minutes)
                        local_second_touch_time = django_timezone.localtime(second_touch_time)
                        if local_second_touch_time.hour >= 21:
                            local_second_touch_time = (local_second_touch_time + timedelta(days=1)).replace(hour=11, minute=0, second=0, microsecond=0)
                            second_touch_time = local_second_touch_time.astimezone(timezone.utc)

                    second_touch = SecondTouchSchedule.objects.create(
                        user=user,
                        message=second_touch_message,
                        scheduled_time=second_touch_time
                    )
                    print(f"Scheduled second touch for {user.telegram_id} at {django_timezone.localtime(second_touch_time)} (local time) (ID: {second_touch.id})")

                    print(f"Pending user {pending_user.telegram_id} processed")
            else:
                print("No pending users to process")


def get_next_schedule_time():
    from django.utils import timezone as django_timezone
    from bots.models import FirstTouchSchedule, SecondTouchSchedule

    now = django_timezone.localtime(django_timezone.now())
    next_first_touch = FirstTouchSchedule.objects.filter(
        sent=False,
        scheduled_time__gt=now
    ).order_by('scheduled_time').first()

    next_second_touch = SecondTouchSchedule.objects.filter(
        sent=False,
        scheduled_time__gt=now
    ).order_by('scheduled_time').first()

    if not next_first_touch and not next_second_touch:
        return None

    next_time = None
    if next_first_touch:
        next_time = next_first_touch.scheduled_time
    if next_second_touch and (next_time is None or next_second_touch.scheduled_time < next_time):
        next_time = next_second_touch.scheduled_time

    return next_time


def run_scheduler():
    while True:
        now = django_timezone.localtime(django_timezone.now())
        process_schedules()
        process_pending_users()

        next_time = get_next_schedule_time()
        now = django_timezone.localtime(django_timezone.now())

        if next_time:
            sleep_seconds = (next_time - now).total_seconds()
            if sleep_seconds <= 0:
                sleep_seconds = 1
            else:
                print(f"Next schedule at {next_time}, sleeping for {sleep_seconds:.2f} seconds...")
                time.sleep(sleep_seconds)
        else:
            print("No upcoming schedules, sleeping for 3 minutes...")
            time.sleep(180)


def start_scheduler():
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rassilka_tg_notifications.settings')
    django.setup()

    global scheduler_lock
    if scheduler_lock.locked():
        print("Scheduler is already running, skipping new instance.")
        return

    print("Starting scheduler in a background thread...")
    scheduler_thread = Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()