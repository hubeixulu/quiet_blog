from .models import SiteSetting

def site_settings(request):
    return {"site": SiteSetting.objects.first() or SiteSetting()}

