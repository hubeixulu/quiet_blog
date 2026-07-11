from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("blog", "0003_comment_protection")]
    operations = [
        migrations.AddField(
            model_name="sitesetting",
            name="rss_enabled",
            field=models.BooleanField(default=True, verbose_name="启用 RSS"),
        ),
    ]
