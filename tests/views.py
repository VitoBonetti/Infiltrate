from django.views.generic import TemplateView, CreateView, UpdateView
from django.views import View
from tests.forms import TestForm
from tests.models import Test
from rbac.models import RoleAssignment, ROLE_MANAGER
from rbac.policy import is_god, is_admin, is_pentester
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib import messages


class TestRequestView(View):
    template_name = "tests/tests_user_form.html"

    def _can_request_test(self, user):
        """Helper to check if a user is allowed to request/create a test."""
        if not user.is_authenticated:
            return False

        # 1. Check global roles
        if is_god(user) or is_admin(user) or is_pentester(user):
            return True

        # 2. Check if user is a Manager for ANY market
        # We don't check a specific market here because the form hasn't been rendered/submitted yet.
        # The TestForm's __init__ method will handle restricting the actual asset choices.
        is_manager = RoleAssignment.objects.filter(user=user, role=ROLE_MANAGER).exists()

        return is_manager

    def get(self, request, *args, **kwargs):
        if not self._can_request_test(request.user):
            messages.error(request, "You do not have permission to request a test.")
            return redirect("dashboard")

        test_id = request.GET.get("test_id")
        if test_id:
            test = get_object_or_404(Test, uuid=test_id)
            form = TestForm(instance=test)
            editing = True
        else:
            form = TestForm()
            editing = False

        return render(request, self.template_name, {'form': form, 'editing': editing, 'test_id': test_id})

    def post(self, request, *args, **kwargs):
        if not self._can_request_test(request.user):
            messages.error(request, "You do not have permission to request a test.")
            return redirect("dashboard")

        test_id = request.GET.get("test_id")
        if test_id:
            test = get_object_or_404(Test, uuid=test_id)
            form = TestForm(request.POST, instance=test)
        else:
            form = TestForm(request.POST)

        if form.is_valid():
            test_instance = form.save(commit=False)
            test_instance.requested_by = request.user
            test_instance.save()

            form.save_m2m()

            msg = "Test updated successfully." if test_id else "Test requested successfully."
            messages.success(request, msg)

            return redirect('tests_user_list')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        messages.error(request, f"Validation Error: {error}")
                    else:
                        # custom error here
                        pass

        return render(request, self.template_name, {'form': form, 'editing': bool(test_id), 'test_id': test_id})



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