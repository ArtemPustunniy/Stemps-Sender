from django.utils import timezone
from datetime import timezone as dt_timezone
from .models import User, Message, Schedule, Settings
from django import forms
from .admin_site import custom_admin_site
from django.contrib import admin
from django.contrib.auth.models import User as AuthUser, Group
from django_celery_beat.models import PeriodicTask, ClockedSchedule, CrontabSchedule, IntervalSchedule, SolarSchedule
from django.contrib.auth.admin import UserAdmin as AuthUserAdmin, GroupAdmin

class ScheduleAdminForm(forms.ModelForm):
    class Meta:
        model = Schedule
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Преобразуем scheduled_time в UTC для отображения
        if self.instance and self.instance.scheduled_time:
            self.initial['scheduled_time'] = self.instance.scheduled_time.astimezone(dt_timezone.utc)

        # Изменяем метку поля на русском
        self.fields['scheduled_time'].label = 'Время отправки (UTC)'

    def clean_scheduled_time(self):
        # Убедимся, что введенное время интерпретируется как UTC
        scheduled_time = self.cleaned_data['scheduled_time']
        if scheduled_time and scheduled_time.tzinfo:
            return scheduled_time.astimezone(dt_timezone.utc)
        return scheduled_time

class UserAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'name', 'responded', 'last_message_time')
    list_filter = ('responded',)
    search_fields = ('telegram_id', 'name')
    ordering = ('telegram_id',)

class MessageAdmin(admin.ModelAdmin):
    list_display = ('text', 'is_second_touch')
    list_filter = ('is_second_touch',)
    search_fields = ('text',)

class ScheduleAdmin(admin.ModelAdmin):
    form = ScheduleAdminForm
    list_display = ('user', 'message', 'scheduled_time_utc', 'sent')
    list_filter = ('sent', 'scheduled_time')
    search_fields = ('user__telegram_id', 'message__text')
    ordering = ('scheduled_time',)
    actions = ['delete_schedules']

    def scheduled_time_utc(self, obj):
        return obj.scheduled_time.astimezone(dt_timezone.utc)

    scheduled_time_utc.short_description = 'Время отправки (UTC)'

    @admin.action(description="Удалить выбранные расписания")
    def delete_schedules(self, request, queryset):
        queryset.delete()

class SettingsAdmin(admin.ModelAdmin):
    list_display = ('message_interval_minutes', 'ban_freeze_hours', 'second_touch_delay_minutes')

# Классы админки для django-celery-beat
class PeriodicTaskAdmin(admin.ModelAdmin):
    list_display = ('name', 'task', 'enabled')
    list_filter = ('enabled',)
    search_fields = ('name', 'task')

class ClockedScheduleAdmin(admin.ModelAdmin):
    list_display = ('clocked_time',)
    list_filter = ('clocked_time',)
    search_fields = ('clocked_time',)

class CrontabScheduleAdmin(admin.ModelAdmin):
    list_display = ('minute', 'hour', 'day_of_week', 'day_of_month', 'month_of_year')
    search_fields = ('minute', 'hour')

class IntervalScheduleAdmin(admin.ModelAdmin):
    list_display = ('every', 'period')
    search_fields = ('every', 'period')

class SolarScheduleAdmin(admin.ModelAdmin):
    list_display = ('event', 'latitude', 'longitude')
    search_fields = ('event',)

# Регистрируем модели напрямую через custom_admin_site
custom_admin_site.register(User, UserAdmin)
custom_admin_site.register(Message, MessageAdmin)
custom_admin_site.register(Schedule, ScheduleAdmin)
custom_admin_site.register(Settings, SettingsAdmin)
custom_admin_site.register(PeriodicTask, PeriodicTaskAdmin)
custom_admin_site.register(ClockedSchedule, ClockedScheduleAdmin)
custom_admin_site.register(CrontabSchedule, CrontabScheduleAdmin)
custom_admin_site.register(IntervalSchedule, IntervalScheduleAdmin)
custom_admin_site.register(SolarSchedule, SolarScheduleAdmin)
custom_admin_site.register(AuthUser, AuthUserAdmin)
custom_admin_site.register(Group, GroupAdmin)