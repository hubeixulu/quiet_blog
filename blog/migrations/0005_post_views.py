from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("blog", "0004_sitesetting_rss_enabled")]
    operations = [
        migrations.AddField(
            model_name="post",
            name="view_count",
            field=models.PositiveBigIntegerField(default=0, editable=False, verbose_name="阅读量"),
        ),
        migrations.CreateModel(
            name="PostViewDaily",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(verbose_name="日期")),
                ("views", models.PositiveIntegerField(default=0, verbose_name="阅读量")),
                ("post", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="daily_views", to="blog.post", verbose_name="文章")),
            ],
            options={
                "verbose_name": "每日阅读数据",
                "verbose_name_plural": "每日阅读数据",
                "ordering": ["-date", "-views"],
                "constraints": [models.UniqueConstraint(fields=("post", "date"), name="unique_post_view_date")],
            },
        ),
    ]
