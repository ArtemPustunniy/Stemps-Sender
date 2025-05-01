from django.db import migrations

FIRST_TOUCH_MESSAGE = """
Добрый день!

Меня зовут Екатерина, менеджер по развитию образовательной платформы для архитекторов и девелоперов stemps.ru

Возможно уже что-то слышали о нас?)
"""

SECOND_TOUCH_MESSAGE = """
В прошлый раз не дописалась) 

Чтобы лишний раз не дёргала, не подскажете кто в вашей команде отвечает за обучение сотрудников?
"""

def create_initial_data(apps, schema_editor):
    Message = apps.get_model('bots', 'Message')
    Settings = apps.get_model('bots', 'Settings')
    Bot = apps.get_model('bots', 'Bot')

    # Создаём сообщения
    if not Message.objects.filter(text=FIRST_TOUCH_MESSAGE).exists():
        Message.objects.create(text=FIRST_TOUCH_MESSAGE, is_second_touch=False)
    if not Message.objects.filter(text=SECOND_TOUCH_MESSAGE).exists():
        Message.objects.create(text=SECOND_TOUCH_MESSAGE, is_second_touch=True)

    # Создаём настройки
    if not Settings.objects.exists():
        Settings.objects.create()

    # Создаём бота
    if not Bot.objects.exists():
        Bot.objects.create(name="Main Bot")

class Migration(migrations.Migration):
    dependencies = [
        ('bots', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_initial_data),
    ]