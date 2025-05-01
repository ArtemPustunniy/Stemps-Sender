from django.utils import timezone
from datetime import timezone as dt_timezone
from .models import User, Message, FirstTouchSchedule, SecondTouchSchedule, Settings, Bot
from django import forms
from .admin_site import custom_admin_site
from django.contrib import admin
from django.contrib.auth.models import User as AuthUser, Group
from django.contrib.auth.admin import UserAdmin as AuthUserAdmin, GroupAdmin


class ScheduleAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.scheduled_time:
            self.initial['scheduled_time'] = self.instance.scheduled_time.astimezone(dt_timezone.utc)

        self.fields['scheduled_time'].label = 'Время добавления (UTC)'

    def clean_scheduled_time(self):
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


class FirstTouchScheduleAdmin(admin.ModelAdmin):
    form = ScheduleAdminForm
    list_display = ('user', 'message', 'scheduled_time_utc', 'sent')
    list_filter = ('sent', 'scheduled_time')
    search_fields = ('user__telegram_id', 'message__text')
    ordering = ('scheduled_time',)
    actions = ['delete_schedules']

    def scheduled_time_utc(self, obj):
        return obj.scheduled_time.astimezone(dt_timezone.utc)

    scheduled_time_utc.short_description = 'Время добавления (UTC)'

    @admin.action(description="Удалить выбранные расписания первого касания")
    def delete_schedules(self, request, queryset):
        queryset.delete()


class SecondTouchScheduleAdmin(admin.ModelAdmin):
    form = ScheduleAdminForm
    list_display = ('user', 'message', 'scheduled_time_utc', 'sent')
    list_filter = ('sent', 'scheduled_time')
    search_fields = ('user__telegram_id', 'message__text')
    ordering = ('scheduled_time',)
    actions = ['delete_schedules']

    def scheduled_time_utc(self, obj):
        return obj.scheduled_time.astimezone(dt_timezone.utc)

    scheduled_time_utc.short_description = 'Время добавления (UTC)'

    @admin.action(description="Удалить выбранные расписания второго касания")
    def delete_schedules(self, request, queryset):
        queryset.delete()


class SettingsAdmin(admin.ModelAdmin):
    list_display = ('message_interval_minutes', 'ban_freeze_minutes', 'second_touch_delay_minutes')


class BotAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_banned', 'banned_until')
    list_filter = ('is_banned',)
    search_fields = ('name',)


custom_admin_site.register(User, UserAdmin)
custom_admin_site.register(Message, MessageAdmin)
custom_admin_site.register(FirstTouchSchedule, FirstTouchScheduleAdmin)
custom_admin_site.register(SecondTouchSchedule, SecondTouchScheduleAdmin)
custom_admin_site.register(Settings, SettingsAdmin)
custom_admin_site.register(Bot, BotAdmin)
custom_admin_site.register(AuthUser, AuthUserAdmin)
custom_admin_site.register(Group, GroupAdmin)