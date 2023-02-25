# Generated by Django 4.1.7 on 2023-02-25 09:48

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0003_alter_client_person_alter_contractor_person_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='client',
            options={'verbose_name': 'клиент', 'verbose_name_plural': 'клиенты'},
        ),
        migrations.AddField(
            model_name='order',
            name='estimated_time',
            field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name='Срок выполнения заказа'),
        ),
        migrations.AlterField(
            model_name='client',
            name='person',
            field=models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='clients', to='main.person', verbose_name='Клиент'),
        ),
    ]
