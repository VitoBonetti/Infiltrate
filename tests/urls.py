from django.urls import path
from tests.views import TestFormView, TestListView

urlpatterns = [
    path('tests_user_form/', TestFormView.as_view(), name='tests_user_form'),
    path('tesst_user_list/', TestListView.as_view(), name='tests_user_list'),
]