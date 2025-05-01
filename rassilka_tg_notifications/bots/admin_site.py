from django.contrib.admin import AdminSite
from django.utils.translation import gettext_lazy as _


class CustomAdminSite(AdminSite):
    site_header = "StempsSenderAdministration"
    site_title = "StempsSenderAdministration"
    index_title = "Добро пожаловать в StempsSenderAdministration"

    def get_app_list(self, request):
        app_list = super().get_app_list(request)
        for app in app_list:
            if app['app_label'] == 'bots':
                app['name'] = "Основные настройки"
                for model in app['models']:
                    if model['object_name'] == 'FirstTouchSchedule':
                        model['name'] = "Первые касания"
                    elif model['object_name'] == 'SecondTouchSchedule':
                        model['name'] = "Вторые касания"
                    elif model['object_name'] == 'User':
                        model['name'] = "Пользователи (Telegram)"
                    elif model['object_name'] == 'Message':
                        model['name'] = "Сообщения"
                    elif model['object_name'] == 'Settings':
                        model['name'] = "Настройки"
                    elif model['object_name'] == 'Bot':
                        model['name'] = "Боты"
            elif app['app_label'] == 'auth':
                app['name'] = "Аутентификация и авторизация"
                for model in app['models']:
                    if model['object_name'] == 'User':
                        model['name'] = "Пользователи (админ)"
                    elif model['object_name'] == 'Group':
                        model['name'] = "Группы"
        return app_list


custom_admin_site = CustomAdminSite(name='custom_admin')