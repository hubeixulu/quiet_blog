from django.db import models
from django.urls import reverse
from django.utils import timezone


class NamedSlugModel(models.Model):
    name = models.CharField("名称", max_length=80, unique=True)
    slug = models.SlugField("网址标识", max_length=90, unique=True, allow_unicode=True)
    class Meta:
        abstract = True
    def __str__(self): return self.name


class Category(NamedSlugModel):
    class Meta: verbose_name = "分类"; verbose_name_plural = "分类"


class Tag(NamedSlugModel):
    class Meta: verbose_name = "标签"; verbose_name_plural = "标签"


class PostQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status=Post.Status.PUBLISHED, published_at__lte=timezone.now())


class Post(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        PUBLISHED = "published", "已发布"
    title = models.CharField("标题", max_length=180)
    slug = models.SlugField("网址标识", max_length=200, unique=True, allow_unicode=True)
    excerpt = models.TextField("摘要", max_length=300, blank=True)
    body = models.TextField("正文（Markdown）")
    comments_enabled = models.BooleanField("允许评论", default=True)
    cover = models.ImageField("封面", upload_to="covers/%Y/%m/", blank=True)
    category = models.ForeignKey(Category, verbose_name="分类", null=True, blank=True, on_delete=models.SET_NULL, related_name="posts")
    tags = models.ManyToManyField(Tag, verbose_name="标签", blank=True, related_name="posts")
    status = models.CharField("状态", max_length=12, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField("发布时间", default=timezone.now)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)
    objects = PostQuerySet.as_manager()
    class Meta:
        ordering = ["-published_at"]
        verbose_name = "文章"; verbose_name_plural = "文章"
    def __str__(self): return self.title
    def get_absolute_url(self): return reverse("post_detail", args=[self.slug])


class Comment(models.Model):
    post = models.ForeignKey(Post, verbose_name="文章", on_delete=models.CASCADE, related_name="comments")
    parent = models.ForeignKey(
        "self", verbose_name="回复对象", null=True, blank=True,
        on_delete=models.CASCADE, related_name="replies",
    )
    name = models.CharField("昵称", max_length=40)
    body = models.TextField("内容", max_length=1000)
    is_approved = models.BooleanField("公开显示", default=True)
    author_fingerprint = models.CharField(max_length=64, blank=True, db_index=True, editable=False)
    created_at = models.DateTimeField("发表时间", auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "评论"
        verbose_name_plural = "评论"

    def __str__(self):
        return f"{self.name}：{self.body[:30]}"


class CommentThrottle(models.Model):
    fingerprint = models.CharField(max_length=64, unique=True)
    window_started_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "评论限流记录"
        verbose_name_plural = "评论限流记录"


class SiteSetting(models.Model):
    title = models.CharField("站点名称", max_length=80, default="片刻")
    tagline = models.CharField("一句话介绍", max_length=160, default="记录日常所想")
    author = models.CharField("作者", max_length=80, blank=True)
    about = models.TextField("关于（Markdown）", blank=True)
    footer = models.CharField("页脚文字", max_length=160, blank=True)
    rss_enabled = models.BooleanField("启用 RSS", default=True)
    class Meta: verbose_name = "站点设置"; verbose_name_plural = "站点设置"
    def __str__(self): return self.title
    def save(self, *args, **kwargs):
        if not self.pk and SiteSetting.objects.exists():
            self.pk = SiteSetting.objects.first().pk
        super().save(*args, **kwargs)
