# Generated by Django 5.2 on 2025-04-21 16:13

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bots", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Account",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("api_id", models.CharField(max_length=50)),
                ("api_hash", models.CharField(max_length=255)),
                ("phone_number", models.CharField(max_length=20)),
                ("session_string", models.TextField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("last_ban_time", models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.RemoveField(
            model_name="schedule",
            name="bot",
        ),
        migrations.AddField(
            model_name="schedule",
            name="account",
            field=models.ForeignKey(
                default=None,
                on_delete=django.db.models.deletion.CASCADE,
                to="bots.account",
            ),
            preserve_default=False,
        ),
        migrations.DeleteModel(
            name="Bot",
        ),
    ]
