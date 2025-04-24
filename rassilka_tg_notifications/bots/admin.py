from django.contrib import admin
from django.utils import timezone
from datetime import timezone as dt_timezone
from .models import User, Message, Schedule, Settings
from django import forms


class ScheduleAdminForm(forms.ModelForm):
    class Meta:
        model = Schedule
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Преобразуем scheduled_time в UTC для отображения
        if self.instance and self.instance.scheduled_time:
            self.initial['scheduled_time'] = self.instance.scheduled_time.astimezone(dt_timezone.utc)

        # Изменяем метку поля
        self.fields['scheduled_time'].label = 'Scheduled time (UTC)'

    def clean_scheduled_time(self):
        # Убедимся, что введенное время интерпретируется как UTC
        scheduled_time = self.cleaned_data['scheduled_time']
        if scheduled_time and scheduled_time.tzinfo:
            return scheduled_time.astimezone(dt_timezone.utc)
        return scheduled_time


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['telegram_id', 'name', 'responded', 'last_message_time']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['text', 'is_second_touch']


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    form = ScheduleAdminForm
    list_display = ['user', 'message', 'scheduled_time_utc', 'sent']

    def scheduled_time_utc(self, obj):
        return obj.scheduled_time.astimezone(dt_timezone.utc)

    scheduled_time_utc.short_description = 'Scheduled time (UTC)'


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    list_display = ['message_interval_minutes', 'ban_freeze_hours', 'second_touch_delay_hours']