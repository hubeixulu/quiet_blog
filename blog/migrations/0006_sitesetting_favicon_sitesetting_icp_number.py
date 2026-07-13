from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("blog", "0005_post_views")]
    operations = [
        migrations.AddField(
            model_name="sitesetting",
            name="favicon",
            field=models.ImageField(
                blank=True,
                help_text="显示在浏览器标签页中，建议上传正方形的 PNG、ICO 或 WebP 图片。",
                upload_to="site/",
                verbose_name="网站图标（Favicon）",
            ),
        ),
        migrations.AddField(
            model_name="sitesetting",
            name="icp_number",
            field=models.CharField(
                blank=True,
                help_text="例如：京ICP备12345678号。填写后会显示在全站页脚。",
                max_length=80,
                verbose_name="ICP备案号",
            ),
        ),
    ]
