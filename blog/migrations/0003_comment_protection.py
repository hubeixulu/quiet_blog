from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("blog", "0002_post_comments_enabled_comment")]
    operations = [
        migrations.AddField(
            model_name="comment",
            name="author_fingerprint",
            field=models.CharField(blank=True, db_index=True, editable=False, max_length=64),
        ),
        migrations.CreateModel(
            name="CommentThrottle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fingerprint", models.CharField(max_length=64, unique=True)),
                ("window_started_at", models.DateTimeField()),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
            ],
            options={"verbose_name": "评论限流记录", "verbose_name_plural": "评论限流记录"},
        ),
    ]
