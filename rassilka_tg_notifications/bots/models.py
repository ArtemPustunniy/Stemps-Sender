from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta, timezone as dt_timezone


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
    sent = models.BooleanField(default=False, verbose_name="Отправлено")

    class Meta:
        verbose_name = "Второе касание"
        verbose_name_plural = "Вторые касания"

    def __str__(self):
        return f"Второе касание для {self.user} на {self.scheduled_time}"


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
        settings = Settings.objects.first()
        if not settings:
            settings = Settings.objects.create()

        if self.is_banned and not self.banned_until:
            self.banned_until = timezone.now() + timezone.timedelta(minutes=settings.ban_freeze_minutes)
            print(f"Bot banned until {self.banned_until}")

            # Обновляем время в расписаниях при бане
            for schedule in FirstTouchSchedule.objects.filter(sent=False):
                if schedule.scheduled_time < self.banned_until:
                    original_scheduled_time = schedule.scheduled_time
                    schedule.scheduled_time = self.banned_until
                    schedule.save()
                    print(f"First touch for {schedule.user} rescheduled from {original_scheduled_time} to {self.banned_until}")

            for schedule in SecondTouchSchedule.objects.filter(sent=False):
                if schedule.scheduled_time < self.banned_until:
                    original_scheduled_time = schedule.scheduled_time
                    schedule.scheduled_time = self.banned_until
                    schedule.save()
                    print(f"Second touch for {schedule.user} rescheduled from {original_scheduled_time} to {self.banned_until}")
                else:
                    first_touch = FirstTouchSchedule.objects.filter(
                        user=schedule.user,
                        sent=False
                    ).first()
                    if first_touch:
                        time_diff = schedule.scheduled_time - first_touch.scheduled_time
                        new_second_touch_time = first_touch.scheduled_time + time_diff
                        if new_second_touch_time < self.banned_until:
                            new_second_touch_time = self.banned_until
                        schedule.scheduled_time = new_second_touch_time
                        schedule.save()
                        print(f"Second touch for {schedule.user} rescheduled to {new_second_touch_time} to maintain time difference with first touch")

        elif not self.is_banned:
            self.banned_until = None

        super().save(*args, **kwargs)


@receiver(post_save, sender=User)
def create_user_schedules(sender, instance, created, **kwargs):
    if created:
        print(f"New user created: {instance.telegram_id}")

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
            if not first_touch_message:
                print("First touch message is missing.")
            if not second_touch_message:
                print("Second touch message is missing.")
            # Попробуем вывести все сообщения для отладки
            all_messages = Message.objects.all()
            print(f"All messages in DB: {[msg.text[:50] + '...' for msg in all_messages]}")
            return

        now = timezone.now().astimezone(dt_timezone.utc)
        print(f"Current time in UTC: {now}")

        last_first_touch = FirstTouchSchedule.objects.filter(
            sent=False
        ).order_by('-scheduled_time').first()

        if last_first_touch:
            last_first_touch_time_utc = last_first_touch.scheduled_time.astimezone(dt_timezone.utc)
            print(f"Last first touch time in UTC: {last_first_touch_time_utc}")
            if last_first_touch_time_utc > now:
                first_touch_time = last_first_touch_time_utc + timedelta(minutes=settings.message_interval_minutes)
            else:
                first_touch_time = now + timedelta(minutes=2)
        else:
            first_touch_time = now + timedelta(minutes=2)

        if (first_touch_time - now).total_seconds() < 120:
            first_touch_time = now + timedelta(minutes=4)

        if bot.is_banned and bot.banned_until and bot.banned_until > first_touch_time:
            first_touch_time = bot.banned_until

        print(f"First touch time before saving: {first_touch_time}")

        # Сохраняем в таблицу первого касания
        FirstTouchSchedule.objects.create(
            user=instance,
            message=first_touch_message,
            scheduled_time=first_touch_time
        )

        second_touch_time = first_touch_time + timedelta(minutes=settings.second_touch_delay_minutes)
        if bot.is_banned and bot.banned_until and bot.banned_until > second_touch_time:
            second_touch_time = bot.banned_until + timedelta(minutes=settings.second_touch_delay_minutes - 2)

        # Сохраняем в таблицу второго касания
        SecondTouchSchedule.objects.create(
            user=instance,
            message=second_touch_message,
            scheduled_time=second_touch_time
        )

        first_touch_time_utc_log = first_touch_time.astimezone(dt_timezone.utc)
        second_touch_time_utc_log = second_touch_time.astimezone(dt_timezone.utc)
        print(f"Scheduled messages for user {instance.telegram_id}: first at {first_touch_time_utc_log} (UTC), second at {second_touch_time_utc_log} (UTC)")