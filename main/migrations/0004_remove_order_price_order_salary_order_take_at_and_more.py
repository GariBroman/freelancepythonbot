# Generated by Django 4.1.7 on 2023-02-24 07:16

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0003_order_price'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='order',
            name='price',
        ),
        migrations.AddField(
            model_name='order',
            name='salary',
            field=models.DecimalField(decimal_places=2, default=300, max_digits=8, validators=[django.core.validators.MinValueValidator(0)], verbose_name='стоимость работ'),
        ),
        migrations.AddField(
            model_name='order',
            name='take_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name='Взят в работу'),
        ),
        migrations.AddField(
            model_name='tariff',
            name='subscription_price',
            field=models.DecimalField(decimal_places=2, default=300, max_digits=8, validators=[django.core.validators.MinValueValidator(0)], verbose_name='стоимость подписки'),
            preserve_default=False,
        ),
    ]
