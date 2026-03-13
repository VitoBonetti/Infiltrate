from django.urls import path
from django.contrib.auth import views as auth_views
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator

app_name = "accounts"

# Rate limiting to the post request of the LoginView
@method_decorator(ratelimit(key='ip', rate='5/5m', method='POST', block=True), name='post')
class RateLimitedLoginView(auth_views.LoginView):
    template_name = "registration/login.html"

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]