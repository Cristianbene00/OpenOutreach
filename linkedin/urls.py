# linkedin/urls.py
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponse
from django.template import TemplateDoesNotExist, loader
from django.urls import include, path, re_path
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie

_SPA_NOT_BUILT = """<!doctype html><html><head><meta charset="utf-8">
<title>OpenOutreach</title></head><body style="font-family:system-ui;max-width:40rem;margin:4rem auto;padding:0 1rem">
<h1>Control center not built yet</h1>
<p>The React SPA bundle is missing. Build it first:</p>
<pre>make frontend-install &amp;&amp; make frontend-build</pre>
<p>Or run the dev server: <code>make frontend-dev</code> (proxies the API).</p>
<p>The API is live at <a href="/api/auth/me">/api/</a> and Django Admin at
<a href="/admin/">/admin/</a>.</p>
</body></html>"""


@ensure_csrf_cookie
@never_cache
def spa(request):
    """Serve the SPA shell; client-side router handles the path.

    Falls back to a helpful message when the frontend hasn't been built.
    """
    try:
        template = loader.get_template("index.html")
    except TemplateDoesNotExist:
        return HttpResponse(_SPA_NOT_BUILT)
    return HttpResponse(template.render({}, request))


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("controlcenter.urls")),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# SPA catch-all — must come last so it doesn't shadow /api or /admin.
urlpatterns += [re_path(r"^(?!api/|admin/|static/|media/).*$", spa)]
