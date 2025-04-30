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
    periodic_task = models.ForeignKey(PeriodicTask, on_delete=models.CASCADE, null=True, blank=True)
    clocked_schedule = models.ForeignKey(ClockedSchedule, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        verbose_name = "Расписание"
        verbose_name_plural = "Расписания"

    def __str__(self):
        return f"Сообщение для {self.user} на {self.scheduled_time}"


class Settings(models.Model):
    message_interval_minutes = models.IntegerField(default=6, verbose_name="Интервал между сообщениями (минуты)")
    ban_freeze_minutes = models.IntegerField(default=60, verbose_name="Заморозка после бана (минуты)")
    second_touch_delay_minutes = models.IntegerField(default=1440, verbose_name="Задержка второго касания (минуты)")  # 1440 минут = 24 часа

    class Meta:
        verbose_name = "Настройка"
        verbose_name_plural = "Настройки"

    def __str__(self):
        return "Глобальные настройки"


class Bot(models.Model):
    name = models.CharField(max_length=100, default="Main Bot", verbose_name="Имя бота")
    is_banned = models.BooleanField(default=False, verbose_name="Забанен")
    banned_until = models.DateTimeField(null=True, blank=True, verbose_name="Забанен до")

    class Meta:
        verbose_name = "Бот"
        verbose_name_plural = "Боты"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Получаем настройки
        settings = Settings.objects.first()
        if not settings:
            settings = Settings.objects.create()

        # Если бот забанен, устанавливаем время фриза
        if self.is_banned and not self.banned_until:
            self.banned_until = timezone.now() + timezone.timedelta(minutes=settings.ban_freeze_minutes)
            print(f"Bot banned until {self.banned_until}")

            # Находим все запланированные, но не отправленные задачи
            schedules = Schedule.objects.filter(sent=False)
            for schedule in schedules:
                # Если scheduled_time меньше banned_until, сдвигаем задачу
                if schedule.scheduled_time < self.banned_until:
                    original_scheduled_time = schedule.scheduled_time
                    schedule.scheduled_time = self.banned_until
                    schedule.clocked_schedule.clocked_time = self.banned_until
                    schedule.clocked_schedule.save()
                    schedule.save()
                    print(f"Task {schedule.periodic_task.name} rescheduled from {original_scheduled_time} to {self.banned_until}")
                # Если scheduled_time больше banned_until, но есть второе касание, нужно сохранить разницу
                else:
                    # Проверяем, есть ли первое касание для этого пользователя
                    first_touch = Schedule.objects.filter(
                        user=schedule.user,
                        message__is_second_touch=False,
                        sent=False
                    ).first()
                    if first_touch and schedule.message.is_second_touch:
                        # Вычисляем разницу между первым и вторым касанием
                        time_diff = schedule.scheduled_time - first_touch.scheduled_time
                        # Сдвигаем второе касание относительно нового времени первого
                        new_second_touch_time = first_touch.scheduled_time + time_diff
                        if new_second_touch_time < self.banned_until:
                            new_second_touch_time = self.banned_until
                        schedule.scheduled_time = new_second_touch_time
                        schedule.clocked_schedule.clocked_time = new_second_touch_time
                        schedule.clocked_schedule.save()
                        schedule.save()
                        print(f"Second touch task {schedule.periodic_task.name} rescheduled to {new_second_touch_time} to maintain time difference with first touch")

        # Если бан снят, очищаем banned_until
        elif not self.is_banned:
            self.banned_until = None

        super().save(*args, **kwargs)


@receiver(post_save, sender=User)
def create_user_schedules(sender, instance, created, **kwargs):
    if created:
        print(f"New user created: {instance.telegram_id}")

        # Проверяем состояние бота
        bot = Bot.objects.first()
        if not bot:
            bot = Bot.objects.create(name="Main Bot")

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

        # Учитываем состояние бота
        if bot.is_banned and bot.banned_until and bot.banned_until > first_touch_time:
            first_touch_time = bot.banned_until

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
        first_task = PeriodicTask.objects.create(
            clocked=clocked_first,
            name=f"send-first-touch-{first_schedule.id}",
            task='bots.tasks.send_message',
            args=json.dumps([first_schedule.id]),
            one_off=True,
            enabled=True
        )
        print(f"First task created: {first_task.name}, enabled={first_task.enabled}, clocked_time={clocked_first.clocked_time}")
        first_schedule.periodic_task = first_task
        first_schedule.clocked_schedule = clocked_first
        first_schedule.save()

        second_touch_time = first_touch_time + timedelta(minutes=settings.second_touch_delay_minutes)
        # Учитываем состояние бота для второго касания
        if bot.is_banned and bot.banned_until and bot.banned_until > second_touch_time:
            second_touch_time = bot.banned_until + timedelta(minutes=settings.second_touch_delay_minutes - 2)

        second_schedule = Schedule.objects.create(
            user=instance,
            message=second_touch_message,
            scheduled_time=second_touch_time
        )

        second_touch_time_utc = second_touch_time.astimezone(dt_timezone.utc)
        clocked_second = ClockedSchedule.objects.create(
            clocked_time=second_touch_time_utc
        )
        second_task = PeriodicTask.objects.create(
            clocked=clocked_second,
            name=f"send-second-touch-{second_schedule.id}",
            task='bots.tasks.send_message',
            args=json.dumps([second_schedule.id]),
            one_off=True,
            enabled=True
        )
        print(f"Second task created: {second_task.name}, enabled={second_task.enabled}, clocked_time={clocked_second.clocked_time}")
        second_schedule.periodic_task = second_task
        second_schedule.clocked_schedule = clocked_second
        second_schedule.save()

        # Показываем время в UTC для ясности
        first_touch_time_utc_log = first_touch_time.astimezone(dt_timezone.utc)
        second_touch_time_utc_log = second_touch_time.astimezone(dt_timezone.utc)
        print(f"Scheduled messages for user {instance.telegram_id}: first at {first_touch_time_utc_log} (UTC), second at {second_touch_time_utc_log} (UTC)")