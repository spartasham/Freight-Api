# Generated by Django 5.2.1 on 2025-05-31 08:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shipments', '0004_alter_shipment_customer_alter_shipment_table'),
    ]

    operations = [
        migrations.AlterField(
            model_name='shipment',
            name='carrier',
            field=models.CharField(blank=True, max_length=120, null=True, unique=True),
        ),
        migrations.DeleteModel(
            name='Carrier',
        ),
    ]
