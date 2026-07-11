from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Post

class PostSitemap(Sitemap):
    changefreq = "weekly"; priority = 0.8
    def items(self): return Post.objects.published()
    def lastmod(self, obj): return obj.updated_at

class StaticSitemap(Sitemap):
    def items(self): return ["home", "archive", "about"]
    def location(self, item): return reverse(item)

