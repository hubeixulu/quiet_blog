from datetime import timedelta
from io import BytesIO
from tempfile import TemporaryDirectory
from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from .markdown import render_markdown
from .models import Category, Comment, Post, PostViewDaily, SiteSetting, Tag

class BlogTests(TestCase):
    def setUp(self):
        self.published = Post.objects.create(title="第一篇", slug="first", excerpt="摘要", body="# 正文", status="published")
        self.draft = Post.objects.create(title="秘密", slug="secret", body="草稿", status="draft")
        self.future = Post.objects.create(title="明天", slug="tomorrow", body="稍后", status="published", published_at=timezone.now()+timedelta(days=1))

    def comment_data(self, **overrides):
        self.client.get(reverse("comment_captcha"))
        data = {"name": "读者", "body": "评论内容", "captcha": self.client.session["comment_captcha"]["answer"]}
        data.update(overrides)
        return data

    def test_home_only_shows_currently_published_posts(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "第一篇"); self.assertNotContains(response, "秘密"); self.assertNotContains(response, "明天")

    def test_frontend_loads_image_lightbox(self):
        response = self.client.get(self.published.get_absolute_url())
        self.assertContains(response, "js/lightbox.js")

    def test_post_views_are_deduplicated_and_aggregated(self):
        response = self.client.get(self.published.get_absolute_url())
        self.published.refresh_from_db()
        self.assertEqual(self.published.view_count, 1)
        self.assertContains(response, "1 次阅读")
        self.client.get(self.published.get_absolute_url())
        self.published.refresh_from_db()
        self.assertEqual(self.published.view_count, 1)
        self.assertEqual(PostViewDaily.objects.get(post=self.published).views, 1)

        session = self.client.session
        session["recent_post_views"] = {str(self.published.pk): 0}
        session.save()
        self.client.get(self.published.get_absolute_url())
        self.published.refresh_from_db()
        self.assertEqual(self.published.view_count, 2)
        self.assertEqual(PostViewDaily.objects.get(post=self.published).views, 2)

        Client(HTTP_USER_AGENT="Googlebot/2.1").get(self.published.get_absolute_url())
        self.published.refresh_from_db()
        self.assertEqual(self.published.view_count, 2)

    def test_comments_can_be_nested_and_are_escaped(self):
        url = reverse("add_comment", args=[self.published.slug])
        self.client.post(url, self.comment_data(body="第一层"))
        root = Comment.objects.get()
        Comment.objects.filter(pk=root.pk).update(created_at=timezone.now() - timedelta(seconds=31))
        root.refresh_from_db()
        self.client.post(url, self.comment_data(name="回复者", body="<script>alert(1)</script>", parent_id=root.pk))
        reply = Comment.objects.get(parent=root)
        response = self.client.get(self.published.get_absolute_url())
        self.assertContains(response, "第一层")
        self.assertContains(response, "回复者")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertEqual(reply.parent, root)

    def test_comments_can_be_disabled_per_post(self):
        existing = Comment.objects.create(post=self.published, name="已有", body="保留显示")
        self.published.comments_enabled = False
        self.published.save(update_fields=["comments_enabled"])
        response = self.client.post(reverse("add_comment", args=[self.published.slug]), {"name": "新评论", "body": "不能发布"})
        self.assertEqual(Comment.objects.count(), 1)
        page = self.client.get(response.url)
        self.assertContains(page, existing.body)
        self.assertContains(page, "这篇文章已关闭评论")

    def test_reply_must_belong_to_same_post_and_honeypot_rejects_bots(self):
        other = Post.objects.create(title="另一篇", slug="other", body="正文", status=Post.Status.PUBLISHED)
        foreign_comment = Comment.objects.create(post=other, name="别人", body="别处评论")
        url = reverse("add_comment", args=[self.published.slug])
        self.client.post(url, self.comment_data(name="跨文章", body="错误回复", parent_id=foreign_comment.pk))
        self.client.post(url, self.comment_data(name="机器人", body="广告", website="https://spam.example"))
        self.assertEqual(Comment.objects.count(), 1)

    def test_hidden_comments_are_not_rendered(self):
        Comment.objects.create(post=self.published, name="隐藏", body="不可见", is_approved=False)
        response = self.client.get(self.published.get_absolute_url())
        self.assertNotContains(response, "不可见")

    def test_comment_captcha_is_required_and_one_time(self):
        url = reverse("add_comment", args=[self.published.slug])
        data = self.comment_data()
        data["captcha"] = "WRONG"
        self.client.post(url, data)
        self.assertEqual(Comment.objects.count(), 0)
        data["captcha"] = self.client.session.get("comment_captcha", {}).get("answer", "")
        self.client.post(url, data)
        self.assertEqual(Comment.objects.count(), 0)

    def test_comment_attempts_are_rate_limited(self):
        url = reverse("add_comment", args=[self.published.slug])
        for _ in range(11):
            self.client.post(url, {"name": "机器人", "body": "刷屏", "captcha": "WRONG"})
        response = self.client.post(url, {"name": "机器人", "body": "刷屏", "captcha": "WRONG"}, follow=True)
        self.assertContains(response, "尝试次数过多")
        self.assertEqual(Comment.objects.count(), 0)

    def test_draft_is_404_but_staff_can_preview(self):
        self.assertEqual(self.client.get(self.draft.get_absolute_url()).status_code, 404)
        user = get_user_model().objects.create_user("writer", password="pass", is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.draft.get_absolute_url()+"?preview=1").status_code, 200)

    def test_search_taxonomy_rss_and_sitemap(self):
        category = Category.objects.create(name="生活", slug="life"); tag = Tag.objects.create(name="随想", slug="thought")
        self.published.category = category; self.published.save(); self.published.tags.add(tag)
        self.assertContains(self.client.get(reverse("search")+"?q=第一"), "第一篇")
        self.assertContains(self.client.get(reverse("taxonomy", args=["categories", "life"])), "第一篇")
        self.assertContains(self.client.get(reverse("rss")), "第一篇")
        self.assertContains(self.client.get(reverse("sitemap")), self.published.get_absolute_url())

    def test_unicode_slugs_are_supported(self):
        category = Category.objects.create(name="新闻", slug="新闻")
        post = Post.objects.create(
            title="中文网址",
            slug="中文网址",
            body="正文",
            category=category,
            status=Post.Status.PUBLISHED,
        )

        self.assertEqual(self.client.get(reverse("home")).status_code, 200)
        self.assertEqual(self.client.get(post.get_absolute_url()).status_code, 200)
        self.assertContains(
            self.client.get(reverse("taxonomy", args=["categories", category.slug])),
            post.title,
        )

    def test_markdown_is_sanitized(self):
        rendered = str(render_markdown("hello<script>alert(1)</script>"))
        self.assertNotIn("<script>", rendered)

    def test_site_setting_is_singleton(self):
        first = SiteSetting.objects.create(title="A"); second = SiteSetting(title="B"); second.save()
        self.assertEqual(SiteSetting.objects.count(), 1); self.assertEqual(SiteSetting.objects.get().title, "B")

    def test_rss_can_be_disabled_in_site_settings(self):
        setting = SiteSetting.objects.create(title="测试站点", rss_enabled=False)
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, 'type="application/rss+xml"')
        self.assertNotContains(response, ">RSS</a>", html=False)
        self.assertEqual(self.client.get(reverse("rss")).status_code, 404)
        setting.rss_enabled = True
        setting.save()
        self.assertEqual(self.client.get(reverse("rss")).status_code, 200)

    def test_site_favicon_and_icp_number_are_rendered(self):
        SiteSetting.objects.create(
            title="测试站点",
            favicon="site/favicon.png",
            icp_number="京ICP备12345678号",
        )
        response = self.client.get(reverse("home"))
        self.assertContains(response, '<link rel="icon" href="/media/site/favicon.png">', html=True)
        self.assertContains(response, "京ICP备12345678号")
        self.assertContains(response, 'href="https://beian.miit.gov.cn/"')

    def test_empty_favicon_and_icp_number_are_not_rendered(self):
        SiteSetting.objects.create(title="测试站点")
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, '<link rel="icon"')
        self.assertNotContains(response, "beian.miit.gov.cn")

    def test_admin_image_upload_requires_staff_and_stores_valid_image(self):
        upload_url = reverse("admin:blog_post_upload_image")
        self.assertEqual(self.client.post(upload_url).status_code, 302)
        user = get_user_model().objects.create_superuser("editor", "editor@example.com", "pass")
        self.client.force_login(user)
        image_data = BytesIO()
        Image.new("RGB", (2, 2), "red").save(image_data, format="PNG")
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(upload_url, {
                "image": SimpleUploadedFile("paste.png", image_data.getvalue(), content_type="image/png")
            })
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["url"].startswith("/media/posts/"))

    def test_admin_image_upload_rejects_invalid_files_and_private_urls(self):
        user = get_user_model().objects.create_superuser("admin", "admin@example.com", "pass")
        self.client.force_login(user)
        upload_url = reverse("admin:blog_post_upload_image")
        response = self.client.post(upload_url, {
            "image": SimpleUploadedFile("fake.png", b"not an image", content_type="image/png")
        })
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            upload_url,
            data='{"url":"http://127.0.0.1/secret.png"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
