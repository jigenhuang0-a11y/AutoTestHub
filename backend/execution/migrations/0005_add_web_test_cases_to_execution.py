# Generated manually 2026-07-07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('execution', '0004_add_locked_to_execution'),
    ]

    operations = [
        migrations.AddField(
            model_name='testexecution',
            name='web_test_cases',
            field=models.JSONField(blank=True, default=list, verbose_name='Web测试用例ID列表'),
        ),
    ]
