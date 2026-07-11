from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("blog", "0001_initial")]
    operations = [
        migrations.AddField(
            model_name="post",
            name="comments_enabled",
            field=models.BooleanField(default=True, verbose_name="允许评论"),
        ),
        migrations.CreateModel(
            name="Comment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=40, verbose_name="昵称")),
                ("body", models.TextField(max_length=1000, verbose_name="内容")),
                ("is_approved", models.BooleanField(default=True, verbose_name="公开显示")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="发表时间")),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="replies", to="blog.comment", verbose_name="回复对象")),
                ("post", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comments", to="blog.post", verbose_name="文章")),
            ],
            options={"verbose_name": "评论", "verbose_name_plural": "评论", "ordering": ["created_at"]},
        ),
    ]
