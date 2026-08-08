# Generated migration for mixed_scenarios field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('performance', '0002_perfexecution_exec_summary_perfexecution_test_type_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='perftestcase',
            name='mixed_scenarios',
            field=models.JSONField(blank=True, default=list, help_text='混合场景下多接口按权重配比，格式: [{"url":"...","method":"GET","headers":{},"body":null,"weight":70}]', verbose_name='混合场景配置'),
        ),
    ]
