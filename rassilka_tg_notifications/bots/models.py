from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta, timezone as dt_timezone
from django_celery_beat.models import PeriodicTask, ClockedSchedule
import json


class User(models.Model):
    telegram_id = models.CharField(max_length=50, unique=True, verbose_name="Telegram ID")
    name = models.CharField(max_length=100, blank=True, verbose_name="Имя")
    responded = models.BooleanField(default=False, verbose_name="Ответил")
    last_message_time = models.DateTimeField(null=True, blank=True, verbose_name="Время последнего сообщения")

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return f"{self.name} ({self.telegram_id})"


class Message(models.Model):
    text = models.TextField(verbose_name="Текст сообщения")
    is_second_touch = models.BooleanField(default=False, verbose_name="Второе касание")

    class Meta:
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"

    def __str__(self):
        return self.text[:50]


class Schedule(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    message = models.ForeignKey(Message, on_delete=models.CASCADE, verbose_name="Сообщение")
    scheduled_time = models.DateTimeField(verbose_name="Время отправки")
    sent = models.BooleanField(default=False, verbose_name="Отправлено")

    class Meta:
        verbose_name = "Расписание"
        verbose_name_plural = "Расписания"

    def __str__(self):
        return f"Сообщение для {self.user} на {self.scheduled_time}"


class Settings(models.Model):
    message_interval_minutes = models.IntegerField(default=6, verbose_name="Интервал между сообщениями (минуты)")
    ban_freeze_hours = models.IntegerField(default=3, verbose_name="Заморозка после бана (часы)")
    second_touch_delay_minutes = models.IntegerField(default=1440, verbose_name="Задержка второго касания (минуты)")  # 1440 минут = 24 часа

    class Meta:
        verbose_name = "Настройка"
        verbose_name_plural = "Настройки"

    def __str__(self):
        return "Глобальные настройки"


@receiver(post_save, sender=User)
def create_user_schedules(sender, instance, created, **kwargs):
    if created:
        print(f"New user created: {instance.telegram_id}")

        settings = Settings.objects.first()
        if not settings:
            print("Settings not found, cannot schedule messages.")
            return

        first_touch_message = Message.objects.filter(is_second_touch=False).first()
        second_touch_message = Message.objects.filter(is_second_touch=True).first()
        if not first_touch_message or not second_touch_message:
            print("Messages not found, cannot schedule messages.")
            return

        # Получаем текущее время в UTC
        now = timezone.now().astimezone(dt_timezone.utc)
        print(f"Current time in UTC: {now}")

        last_first_touch = Schedule.objects.filter(
            message__is_second_touch=False, sent=False
        ).order_by('-scheduled_time').first()

        # Убедимся, что время в будущем (в UTC)
        if last_first_touch:
            last_first_touch_time_utc = last_first_touch.scheduled_time.astimezone(dt_timezone.utc)
            print(f"Last first touch time in UTC: {last_first_touch_time_utc}")
            if last_first_touch_time_utc > now:
                first_touch_time = last_first_touch_time_utc + timedelta(minutes=settings.message_interval_minutes)
            else:
                first_touch_time = now + timedelta(minutes=2)
        else:
            first_touch_time = now + timedelta(minutes=2)

        # Если разница меньше 2 минут, добавим еще 2 минуты
        if (first_touch_time - now).total_seconds() < 120:
            first_touch_time = now + timedelta(minutes=4)

        print(f"First touch time before saving: {first_touch_time}")

        first_schedule = Schedule.objects.create(
            user=instance,
            message=first_touch_message,
            scheduled_time=first_touch_time
        )

        first_touch_time_utc = first_touch_time.astimezone(dt_timezone.utc)
        clocked_first = ClockedSchedule.objects.create(
            clocked_time=first_touch_time_utc
        )
        PeriodicTask.objects.create(
            clocked=clocked_first,
            name=f"send-first-touch-{first_schedule.id}",
            task='bots.tasks.send_message',
            args=json.dumps([first_schedule.id]),
            one_off=True
        )

        second_touch_time = first_touch_time + timedelta(minutes=settings.second_touch_delay_minutes)
        second_schedule = Schedule.objects.create(
            user=instance,
            message=second_touch_message,
            scheduled_time=second_touch_time
        )

        second_touch_time_utc = second_touch_time.astimezone(dt_timezone.utc)
        clocked_second = ClockedSchedule.objects.create(
            clocked_time=second_touch_time_utc
        )
        PeriodicTask.objects.create(
            clocked=clocked_second,
            name=f"send-second-touch-{second_schedule.id}",
            task='bots.tasks.send_message',
            args=json.dumps([second_schedule.id]),
            one_off=True
        )

        # Показываем время в UTC для ясности
        first_touch_time_utc_log = first_touch_time.astimezone(dt_timezone.utc)
        second_touch_time_utc_log = second_touch_time.astimezone(dt_timezone.utc)
        print(f"Scheduled messages for user {instance.telegram_id}: first at {first_touch_time_utc_log} (UTC), second at {second_touch_time_utc_log} (UTC)")