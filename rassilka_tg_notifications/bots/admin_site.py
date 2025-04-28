from django.contrib.admin import AdminSite
from django.utils.translation import gettext_lazy as _


class CustomAdminSite(AdminSite):
    site_header = "StempsSenderAdministration"
    site_title = "StempsSenderAdministration"
    index_title = "Добро пожаловать в StempsSenderAdministration"

    def get_app_list(self, request):
        app_list = super().get_app_list(request)
        for app in app_list:
            if app['app_label'] == 'django_celery_beat':
                # Переводим название группы
                app['name'] = "Настройки времени"
                # Переводим названия моделей
                for model in app['models']:
                    if model['object_name'] == 'PeriodicTask':
                        model['name'] = "Периодические задачи"
                    elif model['object_name'] == 'ClockedSchedule':
                        model['name'] = "Одноразовые расписания"
                    elif model['object_name'] == 'CrontabSchedule':
                        model['name'] = "Расписания Crontab"
                    elif model['object_name'] == 'IntervalSchedule':
                        model['name'] = "Интервалы"
                    elif model['object_name'] == 'SolarSchedule':
                        model['name'] = "Солнечные события"
            elif app['app_label'] == 'bots':
                # Переводим название группы BOTS
                app['name'] = "Основные настройки"
            elif app['app_label'] == 'auth':
                app['name'] = "Аутентификация и авторизация"
                # Переводим названия моделей
                for model in app['models']:
                    if model['object_name'] == 'User':
                        model['name'] = "Пользователи (админ)"
                    elif model['object_name'] == 'Group':
                        model['name'] = "Группы"
        return app_list

# Создаём экземпляр кастомного AdminSite
custom_admin_site = CustomAdminSite(name='custom_admin')

