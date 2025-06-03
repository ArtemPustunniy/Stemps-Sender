from django.db import models
from django.utils import timezone
from datetime import timedelta, timezone as dt_timezone


class PendingUser(models.Model):
    telegram_id = models.CharField(max_length=50, unique=True, verbose_name="Telegram ID")
    name = models.CharField(max_length=100, blank=True, verbose_name="Имя")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Время создания")
    is_processed = models.BooleanField(default=False, verbose_name="Обработан")

    class Meta:
        verbose_name = "Пользователь в очереди"
        verbose_name_plural = "Пользователи в очереди"
        ordering = ['created_at']

    def __str__(self):
        return f"{self.name} ({self.telegram_id})"


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


class FirstTouchSchedule(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    message = models.ForeignKey(Message, on_delete=models.CASCADE, verbose_name="Сообщение")
    scheduled_time = models.DateTimeField(verbose_name="Время добавления")
    original_scheduled_time = models.DateTimeField(null=True, blank=True, verbose_name="Изначальное время добавления")
    sent = models.BooleanField(default=False, verbose_name="Отправлено")

    class Meta:
        verbose_name = "Первое касание"
        verbose_name_plural = "Первые касания"

    def __str__(self):
        return f"Первое касание для {self.user} на {self.scheduled_time}"


class SecondTouchSchedule(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    message = models.ForeignKey(Message, on_delete=models.CASCADE, verbose_name="Сообщение")
    scheduled_time = models.DateTimeField(verbose_name="Время добавления")
    original_scheduled_time = models.DateTimeField(null=True, blank=True, verbose_name="Изначальное время добавления")
    sent = models.BooleanField(default=False, verbose_name="Отправлено")

    class Meta:
        verbose_name = "Второе касание"
        verbose_name_plural = "Вторые касания"

    def __str__(self):
        return f"Второе касание для {self.user} на {self.scheduled_time}"


class Settings(models.Model):
    message_interval_minutes = models.IntegerField(default=6, verbose_name="Интервал между сообщениями (минуты)")
    ban_freeze_minutes = models.IntegerField(default=60, verbose_name="Заморозка после бана (минуты)")
    second_touch_delay_minutes = models.IntegerField(default=1440, verbose_name="Задержка второго касания (минуты)")
    admin_telegram_id = models.CharField(max_length=50, blank=True, null=True, verbose_name="Telegram ID админа")

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
        settings = Settings.objects.first()
        if not settings:
            settings = Settings.objects.create()

        now = timezone.now()

        if self.is_banned and not self.banned_until:
            self.banned_until = now + timezone.timedelta(minutes=settings.ban_freeze_minutes)
            print(f"Bot banned until {self.banned_until}")

            for schedule in FirstTouchSchedule.objects.filter(sent=False):
                if not schedule.original_scheduled_time:
                    schedule.original_scheduled_time = schedule.scheduled_time
                new_time = schedule.scheduled_time + timezone.timedelta(minutes=settings.ban_freeze_minutes)
                adjusted_time = adjust_time_to_working_hours(new_time, settings)
                schedule.scheduled_time = adjusted_time
                schedule.save()
                print(f"First touch for {schedule.user} rescheduled from {schedule.original_scheduled_time} to {schedule.scheduled_time}")

            for schedule in SecondTouchSchedule.objects.filter(sent=False):
                if not schedule.original_scheduled_time:
                    schedule.original_scheduled_time = schedule.scheduled_time
                new_time = schedule.scheduled_time + timezone.timedelta(minutes=settings.ban_freeze_minutes)
                adjusted_time = adjust_time_to_working_hours(new_time, settings)
                schedule.scheduled_time = adjusted_time
                schedule.save()
                print(f"Second touch for {schedule.user} rescheduled from {schedule.original_scheduled_time} to {schedule.scheduled_time}")

        elif not self.is_banned and self.banned_until:
            print(f"Bot ban removed at {now}")
            self.banned_until = None

            for schedule in FirstTouchSchedule.objects.filter(sent=False):
                if schedule.original_scheduled_time:
                    schedule.scheduled_time = schedule.original_scheduled_time
                    schedule.original_scheduled_time = None
                    schedule.save()
                    print(f"First touch for {schedule.user} restored to {schedule.scheduled_time}")

            for schedule in SecondTouchSchedule.objects.filter(sent=False):
                if schedule.original_scheduled_time:
                    schedule.scheduled_time = schedule.original_scheduled_time
                    schedule.original_scheduled_time = None
                    schedule.save()
                    print(f"Second touch for {schedule.user} restored to {schedule.scheduled_time}")

        super().save(*args, **kwargs)


def adjust_time_to_working_hours(scheduled_time, settings):
    local_time = timezone.localtime(scheduled_time)
    while True:
        conflicting_first = FirstTouchSchedule.objects.filter(
            sent=False,
            scheduled_time__range=(
                local_time - timedelta(minutes=1),
                local_time + timedelta(minutes=1)
            )
        ).exists()
        conflicting_second = SecondTouchSchedule.objects.filter(
            sent=False,
            scheduled_time__range=(
                local_time - timedelta(minutes=1),
                local_time + timedelta(minutes=1)
            )
        ).exists()

        if not conflicting_first and not conflicting_second:
            break

        local_time += timedelta(minutes=settings.message_interval_minutes)

    current_hour = local_time.hour
    if current_hour < 11:
        local_time = local_time.replace(hour=11, minute=0, second=0, microsecond=0)
    elif current_hour >= 21:
        local_time = (local_time + timedelta(days=1)).replace(hour=11, minute=0, second=0, microsecond=0)

    return local_time.astimezone(dt_timezone.utc)
