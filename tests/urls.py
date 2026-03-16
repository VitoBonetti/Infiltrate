from django.urls import path
from tests.views import TestRequestView, TestsListView

urlpatterns = [
    path('tests_user_form/', TestRequestView.as_view(), name='tests_user_form'),
    path('tests_user_list/', TestsListView.as_view(), name='tests_user_list'),
]