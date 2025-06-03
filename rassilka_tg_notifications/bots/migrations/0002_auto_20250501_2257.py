from django.db import migrations


def add_initial_messages(apps, schema_editor):
    Message = apps.get_model('bots', 'Message')

    # Создаём сообщение для первого касания
    Message.objects.get_or_create(
        text='Добрый день! Меня зовут Екатерина, я представляю компанию XYZ. У нас есть интересное предложение для вас. Вы готовы обсудить детали?',
        is_second_touch=False,
        defaults={
            'text': 'Добрый день! Меня зовут Екатерина, я представляю компанию XYZ. У нас есть интересное предложение для вас. Вы готовы обсудить детали?'}
    )

    # Создаём сообщение для второго касания
    Message.objects.get_or_create(
        text='Здравствуйте! Я писала вам ранее, но не получила ответа. Напоминаю, что у нас есть отличное предложение от компании XYZ. Давайте созвонимся и обсудим? :)',
        is_second_touch=True,
        defaults={
            'text': 'Здравствуйте! Я писала вам ранее, но не получила ответа. Напоминаю, что у нас есть отличное предложение от компании XYZ. Давайте созвонимся и обсудим? :)'}
    )


def remove_initial_messages(apps, schema_editor):
    Message = apps.get_model('bots', 'Message')
    Message.objects.filter(
        text__in=[
            'Добрый день! Меня зовут Екатерина, я представляю компанию XYZ. У нас есть интересное предложение для вас. Вы готовы обсудить детали?',
            'Здравствуйте! Я писала вам ранее, но не получила ответа. Напоминаю, что у нас есть отличное предложение от компании XYZ. Давайте созвонимся и обсудим? :)'
        ]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('bots', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(add_initial_messages, remove_initial_messages),
    ]