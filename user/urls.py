from django.urls import path
from user.views import UserRegisterView, UserLoginView, UserView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('register/', UserRegisterView.as_view()),
    path('login/', UserLoginView.as_view()),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path("users/", UserView.as_view()), 
]