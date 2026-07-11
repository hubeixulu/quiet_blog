from django.contrib.syndication.views import Feed
from django.http import Http404
from django.urls import path
from .models import Post, SiteSetting
from .views import AboutView, ArchiveView, FilteredPostsView, PostDetailView, PostListView, SearchView, add_comment, comment_captcha

class LatestPostsFeed(Feed):
    title = "片刻"; link = "/"; description = "最新文章"
    def items(self): return Post.objects.published()[:20]
    def item_title(self, item): return item.title
    def item_description(self, item): return item.excerpt
    def __call__(self, request, *args, **kwargs):
        setting = SiteSetting.objects.first()
        if setting and not setting.rss_enabled:
            raise Http404
        return super().__call__(request, *args, **kwargs)

urlpatterns = [
    path("", PostListView.as_view(), name="home"), path("posts/<str:slug>/", PostDetailView.as_view(), name="post_detail"),
    path("posts/<str:slug>/comments/", add_comment, name="add_comment"),
    path("comments/captcha/", comment_captcha, name="comment_captcha"),
    path("archive/", ArchiveView.as_view(), name="archive"), path("search/", SearchView.as_view(), name="search"),
    path("about/", AboutView.as_view(), name="about"), path("rss.xml", LatestPostsFeed(), name="rss"),
    path("<str:kind>/<str:slug>/", FilteredPostsView.as_view(), name="taxonomy"),
]
