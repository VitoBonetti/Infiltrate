from django.views.generic import TemplateView, CreateView, UpdateView
from tests.forms import TestForm
from tests.models import Test
from django.urls import reverse_lazy


class TestFormView(CreateView):
    model = Test
    form_class = TestForm
    template_name = "tests/tests_user_form.html"
    success_url = reverse_lazy('tests_user_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        # Attach the user who requested the test before saving to the DB
        form.instance.requested_by = self.request.user
        return super().form_valid(form)


class TestListView(TemplateView):
    template_name = "tests/tests_user_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['tests_count'] = Test.objects.count()
        context['tests'] = Test.objects.all()

        return context