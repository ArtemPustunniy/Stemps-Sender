import os
import time
from threading import Thread

def process_schedules():
    from django.utils import timezone
    from bots.models import FirstTouchSchedule, SecondTouchSchedule
    from bots.tasks import send_message

    print(f"Checking schedules at {timezone.now()}")

    # Обрабатываем первое касание
    first_touch = FirstTouchSchedule.objects.filter(
        sent=False,
        scheduled_time__lte=timezone.now()
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

    # Обрабатываем второе касание
    second_touch = SecondTouchSchedule.objects.filter(
        sent=False,
        scheduled_time__lte=timezone.now()
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
        print("No schedules to process")

def run_scheduler():
    while True:
        process_schedules()
        print("Sleeping for 3 minutes...")
        time.sleep(180)  # 6 минут = 360 секунд

def start_scheduler():
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rassilka_tg_notifications.settings')
    django.setup()

    print("Starting scheduler in a background thread...")
    scheduler_thread = Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()