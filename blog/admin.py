import ipaddress
import http.client
import json
import socket
import ssl
from io import BytesIO
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

from PIL import Image, UnidentifiedImageError
from django import forms
from django.contrib import admin
from django.db.models import Count
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.urls import path
from django.utils import timezone
from .markdown import HTML_BLOCK, _prepare_legacy_text
from .models import Category, Comment, Post, PostViewDaily, SiteSetting, Tag

MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "GIF": ".gif", "WEBP": ".webp"}


def _validate_public_url(value):
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("只支持公开的 HTTP/HTTPS 图片地址")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise ValueError("无法解析图片地址") from exc
    public_addresses = []
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError("不允许访问内网或保留地址")
        public_addresses.append(str(ip))
    return parsed, public_addresses[0]


def _download_remote_image(value):
    current = value
    for _ in range(5):
        parsed, resolved_ip = _validate_public_url(current)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        host_header = parsed.hostname if port in {80, 443} else f"{parsed.hostname}:{port}"
        path = parsed.path or "/"
        if parsed.query:
            path += f"?{parsed.query}"
        connection = http.client.HTTPConnection(parsed.hostname, port, timeout=8)
        try:
            sock = socket.create_connection((resolved_ip, port), timeout=8)
            if parsed.scheme == "https":
                sock = ssl.create_default_context().wrap_socket(sock, server_hostname=parsed.hostname)
            connection.sock = sock
            connection.request("GET", path, headers={"Host": host_header, "User-Agent": "QuietBlog/1.0", "Accept": "image/*"})
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308} and response.getheader("Location"):
                current = urljoin(current, response.getheader("Location"))
                response.close(); connection.close()
                continue
            if response.status < 200 or response.status >= 300:
                response.close(); connection.close()
                raise ValueError("远程图片下载失败")
        except (TimeoutError, OSError, http.client.HTTPException, ssl.SSLError) as exc:
            connection.close()
            raise ValueError("远程图片下载失败或超时") from exc
        content_type = response.getheader("Content-Type", "").split(";", 1)[0].strip().lower()
        if not content_type.startswith("image/"):
            response.close(); connection.close()
            raise ValueError("远程地址返回的不是图片")
        declared_size = response.getheader("Content-Length")
        if declared_size and int(declared_size) > MAX_IMAGE_BYTES:
            response.close(); connection.close()
            raise ValueError("图片不能超过 10 MB")
        data = response.read(MAX_IMAGE_BYTES + 1)
        response.close(); connection.close()
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError("图片不能超过 10 MB")
        return data
    raise ValueError("远程图片重定向次数过多")


def _validated_image(data):
    if not data:
        raise ValueError("图片内容为空")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("图片不能超过 10 MB")
    try:
        with Image.open(BytesIO(data)) as image:
            if image.width * image.height > 40_000_000:
                raise ValueError("图片像素尺寸过大")
            image.verify()
            image_format = image.format
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as exc:
        raise ValueError("文件不是有效图片") from exc
    if image_format not in ALLOWED_IMAGE_FORMATS:
        raise ValueError("仅支持 JPEG、PNG、GIF 和 WebP 图片")
    return ALLOWED_IMAGE_FORMATS[image_format]


def _store_image(data):
    extension = _validated_image(data)
    folder = timezone.localdate().strftime("posts/%Y/%m")
    name = f"{folder}/{uuid4().hex}{extension}"
    saved_name = default_storage.save(name, ContentFile(data))
    return default_storage.url(saved_name)


class PostAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            body = self.initial.get("body") or getattr(self.instance, "body", "")
            if body and not HTML_BLOCK.match(body):
                # Old posts used Markdown single line breaks, which Toast UI
                # reopens as soft wraps in one paragraph. Give the editor real
                # paragraph separators before any browser-side code runs.
                self.initial["body"] = _prepare_legacy_text(body)

    class Meta:
        model = Post
        fields = "__all__"
        widgets = {"body": forms.Textarea(attrs={"class": "quiet-editor-source"})}

admin.site.site_header = "片刻 · 写作后台"
admin.site.site_title = "片刻"

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    form = PostAdminForm
    list_display = ("title", "status", "view_count", "comment_count", "comments_enabled", "category", "published_at", "updated_at")
    list_filter = ("status", "category", "tags")
    search_fields = ("title", "excerpt", "body")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("tags",)
    date_hierarchy = "published_at"
    actions = ("publish", "make_draft")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_comment_count=Count("comments", distinct=True))

    @admin.display(description="评论数", ordering="_comment_count")
    def comment_count(self, obj):
        return obj._comment_count
    class Media:
        css = {"all": ("vendor/toastui-editor.css", "/static/admin/post-editor.css?v=20260714-4")}
        js = ("vendor/purify.min.js", "vendor/toastui-editor.js", "/static/admin/post-editor.js?v=20260714-4")

    def get_urls(self):
        custom_urls = [
            path(
                "upload-image/",
                self.admin_site.admin_view(self.upload_image),
                name="blog_post_upload_image",
            )
        ]
        return custom_urls + super().get_urls()

    def upload_image(self, request):
        if request.method != "POST":
            return JsonResponse({"error": "仅支持 POST 请求"}, status=405)
        try:
            if request.FILES.get("image"):
                upload = request.FILES["image"]
                if upload.size > MAX_IMAGE_BYTES:
                    raise ValueError("图片不能超过 10 MB")
                data = upload.read(MAX_IMAGE_BYTES + 1)
            else:
                payload = json.loads(request.body or b"{}") if request.content_type == "application/json" else request.POST
                remote_url = payload.get("url")
                if not remote_url:
                    raise ValueError("请提供图片文件或远程图片地址")
                data = _download_remote_image(remote_url)
            return JsonResponse({"url": _store_image(data)})
        except (ValueError, json.JSONDecodeError) as exc:
            return JsonResponse({"error": str(exc)}, status=400)

    @admin.action(description="发布所选文章")
    def publish(self, request, queryset): queryset.update(status=Post.Status.PUBLISHED)
    @admin.action(description="转为草稿")
    def make_draft(self, request, queryset): queryset.update(status=Post.Status.DRAFT)

@admin.register(Category, Tag)
class TaxonomyAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("name", "post", "parent", "is_approved", "created_at")
    list_filter = ("is_approved", "created_at")
    search_fields = ("name", "body", "post__title")
    list_editable = ("is_approved",)
    readonly_fields = ("post", "parent", "created_at")

    def has_add_permission(self, request):
        return False


@admin.register(PostViewDaily)
class PostViewDailyAdmin(admin.ModelAdmin):
    list_display = ("date", "post", "views")
    list_filter = ("date",)
    search_fields = ("post__title",)
    date_hierarchy = "date"

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    fieldsets = (
        ("基本信息", {"fields": ("title", "tagline", "author", "favicon")}),
        ("内容", {"fields": ("about",)}),
        ("页脚与备案", {"fields": ("footer", "icp_number", "rss_enabled")}),
    )

    def has_add_permission(self, request):
        return not SiteSetting.objects.exists()
    def has_delete_permission(self, request, obj=None): return False
