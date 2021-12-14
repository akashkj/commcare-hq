# Generated by Django 2.2.24 on 2021-11-30 09:05

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('export', '0012_defaultexportsettings_remove_duplicates_option'),
    ]

    operations = [
        migrations.CreateModel(
            name='GoogleApiToken',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(max_length=128)),
                ('date_created', models.DateField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='google_api_tokens', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
