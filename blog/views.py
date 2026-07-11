import hmac
import ipaddress
import secrets
import time
from io import BytesIO
from datetime import timedelta

from PIL import Image, ImageDraw
from django.db.models import Q
from django.db.models import F
from django.db import transaction
from django.http import Http404, HttpResponse
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.generic import DetailView, ListView, TemplateView
from .forms import CommentForm
from .models import Category, Comment, CommentThrottle, Post, PostViewDaily, SiteSetting, Tag

CAPTCHA_SESSION_KEY = "comment_captcha"
CAPTCHA_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
BOT_MARKERS = ("bot", "spider", "crawler", "slurp", "preview", "facebookexternalhit", "curl", "wget")


def _record_post_view(request, post):
    user_agent = request.headers.get("User-Agent", "").lower()
    if any(marker in user_agent for marker in BOT_MARKERS):
        return False
    now = int(time.time())
    viewed = request.session.get("recent_post_views", {})
    key = str(post.pk)
    if now - int(viewed.get(key, 0)) < 1800:
        return False
    with transaction.atomic():
        Post.objects.filter(pk=post.pk).update(view_count=F("view_count") + 1)
        daily, _ = PostViewDaily.objects.get_or_create(post=post, date=timezone.localdate())
        PostViewDaily.objects.filter(pk=daily.pk).update(views=F("views") + 1)
    viewed[key] = now
    request.session["recent_post_views"] = dict(sorted(viewed.items(), key=lambda item: item[1], reverse=True)[:100])
    post.view_count += 1
    return True


def _visitor_fingerprint(request):
    raw_ip = request.headers.get("X-Real-IP") or request.META.get("REMOTE_ADDR", "unknown")
    try:
        raw_ip = str(ipaddress.ip_address(raw_ip))
    except ValueError:
        raw_ip = "unknown"
    return salted_hmac("quiet-blog-comment", raw_ip).hexdigest()


def _record_attempt(fingerprint):
    now = timezone.now()
    window = now - timedelta(minutes=10)
    with transaction.atomic():
        throttle, _ = CommentThrottle.objects.select_for_update().get_or_create(
            fingerprint=fingerprint,
            defaults={"window_started_at": now, "attempts": 0},
        )
        if throttle.window_started_at < window:
            throttle.window_started_at = now
            throttle.attempts = 0
        if throttle.attempts >= 10:
            return False
        throttle.attempts += 1
        throttle.save(update_fields=["window_started_at", "attempts"])
    return True


def _comment_frequency_allowed(fingerprint):
    recent = Comment.objects.filter(
        author_fingerprint=fingerprint,
        created_at__gte=timezone.now() - timedelta(minutes=10),
    ).order_by("-created_at")
    latest = recent.first()
    if latest and latest.created_at > timezone.now() - timedelta(seconds=30):
        return False, "评论太快了，请等待 30 秒后再试。"
    if recent.count() >= 3:
        return False, "评论过于频繁，请 10 分钟后再试。"
    return True, ""


def comment_captcha(request):
    answer = "".join(secrets.choice(CAPTCHA_ALPHABET) for _ in range(5))
    request.session[CAPTCHA_SESSION_KEY] = {"answer": answer, "created": int(time.time())}
    image = Image.new("RGB", (150, 48), "#f4f1e9")
    draw = ImageDraw.Draw(image)
    for _ in range(10):
        x1, y1, x2, y2 = (secrets.randbelow(150), secrets.randbelow(48), secrets.randbelow(150), secrets.randbelow(48))
        draw.line((x1, y1, x2, y2), fill="#c8c1b4", width=1)
    draw.text((27, 15), " ".join(answer), fill="#292724")
    output = BytesIO()
    image.save(output, "PNG")
    response = HttpResponse(output.getvalue(), content_type="image/png")
    response["Cache-Control"] = "no-store, private"
    return response

class PostListView(ListView):
    template_name = "blog/index.html"; context_object_name = "posts"; paginate_by = 8
    def get_queryset(self): return Post.objects.published().select_related("category").prefetch_related("tags")

class PostDetailView(DetailView):
    model = Post; template_name = "blog/detail.html"; context_object_name = "post"; slug_url_kwarg = "slug"
    def get_queryset(self):
        qs = Post.objects.select_related("category").prefetch_related("tags")
        if self.request.user.is_staff and self.request.GET.get("preview") == "1": return qs
        return qs.published()
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not (self.request.user.is_staff and self.request.GET.get("preview") == "1"):
            _record_post_view(self.request, self.object)
        comments = list(self.object.comments.filter(is_approved=True).select_related("parent"))
        by_id = {comment.pk: comment for comment in comments}
        roots = []
        for comment in comments:
            comment.visible_replies = []
        for comment in comments:
            if comment.parent_id:
                parent = by_id.get(comment.parent_id)
                if parent:
                    parent.visible_replies.append(comment)
            else:
                roots.append(comment)
        context.update(comment_roots=roots, comment_count=len(comments), comment_form=CommentForm())
        return context


def add_comment(request, slug):
    if request.method != "POST":
        raise Http404
    post = get_object_or_404(Post.objects.published(), slug=slug)
    if not post.comments_enabled:
        messages.error(request, "这篇文章已关闭评论。")
        return redirect(f"{post.get_absolute_url()}#comments")
    fingerprint = _visitor_fingerprint(request)
    if not _record_attempt(fingerprint):
        messages.error(request, "尝试次数过多，请 10 分钟后再试。")
        return redirect(f"{post.get_absolute_url()}#comment-form")
    form = CommentForm(request.POST)
    if form.is_valid():
        captcha = request.session.pop(CAPTCHA_SESSION_KEY, None)
        answer = form.cleaned_data["captcha"].strip().upper()
        if not captcha or int(time.time()) - captcha.get("created", 0) > 300 or not hmac.compare_digest(answer, captcha.get("answer", "")):
            messages.error(request, "验证码错误或已过期，请刷新后重试。")
            return redirect(f"{post.get_absolute_url()}#comment-form")
        allowed, reason = _comment_frequency_allowed(fingerprint)
        if not allowed:
            messages.error(request, reason)
            return redirect(f"{post.get_absolute_url()}#comment-form")
        parent = None
        parent_id = form.cleaned_data.get("parent_id")
        if parent_id:
            parent = Comment.objects.filter(pk=parent_id, post=post, is_approved=True).first()
            if not parent:
                messages.error(request, "要回复的评论不存在或已被隐藏。")
                return redirect(f"{post.get_absolute_url()}#comments")
            depth, ancestor = 1, parent
            while ancestor.parent_id and depth < 10:
                ancestor = ancestor.parent
                depth += 1
            if depth >= 10:
                messages.error(request, "该评论楼层已达到最大回复深度。")
                return redirect(f"{post.get_absolute_url()}#comments")
        comment = form.save(commit=False)
        comment.post = post
        comment.parent = parent
        comment.author_fingerprint = fingerprint
        comment.save()
        messages.success(request, "评论已发布。")
        return redirect(f"{post.get_absolute_url()}#comment-{comment.pk}")
    messages.error(request, "请填写昵称和 1000 字以内的评论内容。")
    return redirect(f"{post.get_absolute_url()}#comment-form")

class ArchiveView(PostListView): template_name = "blog/archive.html"; paginate_by = 30

class FilteredPostsView(PostListView):
    template_name = "blog/taxonomy.html"
    def get_queryset(self):
        qs = super().get_queryset(); kind = self.kwargs["kind"]; slug = self.kwargs["slug"]
        model = Category if kind == "categories" else Tag
        self.term = get_object_or_404(model, slug=slug)
        return qs.filter(category=self.term) if kind == "categories" else qs.filter(tags=self.term)
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs); ctx["term"] = self.term; return ctx

class SearchView(PostListView):
    template_name = "blog/search.html"
    def get_queryset(self):
        self.query = self.request.GET.get("q", "").strip()[:100]
        if not self.query: return Post.objects.none()
        return super().get_queryset().filter(Q(title__icontains=self.query) | Q(excerpt__icontains=self.query) | Q(body__icontains=self.query))
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs); ctx["query"] = self.query; return ctx

class AboutView(TemplateView): template_name = "blog/about.html"
