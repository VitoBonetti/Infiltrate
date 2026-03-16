from django.views.generic import TemplateView, CreateView, UpdateView
from django.views import View
from django.core.paginator import Paginator
from tests.forms import TestForm
from tests.models import Test
from rbac.models import RoleAssignment, ROLE_MANAGER
from rbac.policy import is_god, is_admin, is_pentester, can_view
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
            form = TestForm(instance=test, user=request.user)
            editing = True
        else:
            form = TestForm(user=request.user)
            editing = False

        return render(request, self.template_name, {'form': form, 'editing': editing, 'test_id': test_id})

    def post(self, request, *args, **kwargs):
        if not self._can_request_test(request.user):
            messages.error(request, "You do not have permission to request a test.")
            return redirect("dashboard")

        test_id = request.GET.get("test_id")
        if test_id:
            test = get_object_or_404(Test, uuid=test_id)
            form = TestForm(request.POST, instance=test, user=request.user)
        else:
            form = TestForm(request.POST, user=request.user)

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


class TestsListView(View):
    template_name = "tests/tests_user_list.html"

    def get(self, request, *args, **kwargs):
        all_tests = Test.objects.all()
        allowed_test_ids = [test.uuid for test in all_tests if can_view(request.user, test)]

        queryset = Test.objects.filter(uuid__in=allowed_test_ids)

        tests_count = queryset.count()

        search_query = request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(name__icontains=search_query)

        sort_by = request.GET.get('sort', 'name')
        valid_sorts = ['name', '-name', 'service', '-service', 'status', '-status',]
        if sort_by in valid_sorts:
            queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by('name')

        paginator = Paginator(queryset, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            "page_obj": page_obj,
            "tests_count": tests_count,
            "search_query": search_query,  # Pass search back to template
            "sort_by": sort_by,  # Pass sort back to template
        }
        return render(request, self.template_name, context)

class TestListView(TemplateView):
    template_name = "tests/tests_user_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Retrieve all tests and filter using the RBAC policy
        all_tests = Test.objects.all()
        user_tests = [test for test in all_tests if can_view(self.request.user, test)]

        context['tests_count'] = len(user_tests)
        context['tests'] = user_tests

        return context