from django.views import View
from django.core.paginator import Paginator
from tests.forms import TestForm
from tests.models import Test
from rbac.models import RoleAssignment, ROLE_MANAGER
from rbac.policy import is_god, is_admin, is_pentester, can_view
from django.shortcuts import render, redirect, get_object_or_404
from rbac.management_policy import admin_can_write
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

        service_filter = request.GET.get('service', '')
        if service_filter:
            queryset = queryset.filter(service=service_filter)

        status_filter = request.GET.get('status', '')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        quarter_filter = request.GET.get('quarter', '')
        if quarter_filter:
            queryset = queryset.filter(quarter=quarter_filter)

        sort_by = request.GET.get('sort', 'name')
        valid_sorts = ['name', '-name', 'service', '-service', 'status', '-status',]
        if sort_by in valid_sorts:
            queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by('name')

        paginator = Paginator(queryset, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # --- GETTING OPTIONS FOR TEMPLATE DROPDOWNS ---
        # distinct quarters dynamically from allowed tests ignoring none/blanks
        available_quarters = Test.objects.filter(uuid__in=allowed_test_ids) \
            .exclude(quarter__isnull=True) \
            .exclude(quarter__exact='') \
            .values_list('quarter', flat=True) \
            .distinct() \
            .order_by('quarter')

        # get choices directly from the model fields
        service_choices = Test._meta.get_field('service').choices
        status_choices = Test._meta.get_field('status').choices


        context = {
            "page_obj": page_obj,
            "tests_count": tests_count,
            "search_query": search_query,  # Pass search back to template
            "sort_by": sort_by,
            "service_filter": service_filter,
            "status_filter": status_filter,
            "quarter_filter": quarter_filter,
            "available_quarters": available_quarters,
            "service_choices": service_choices,
            "status_choices": status_choices,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        selected_test_ids = request.POST.getlist('selected_items')

        if action and selected_test_ids:
            # 1. Enforce global role permission
            if not admin_can_write(request.user):
                messages.error(request, "Permission denied. Only global administrators can perform bulk actions.")
                return redirect("tests_list")  # Note: replace "tests_list" with your actual URL name!

            tests_to_update = Test.objects.filter(uuid__in=selected_test_ids)

            # 2. Handle Status Change
            if action.startswith('status_'):
                new_status = action.replace('status_', '')

                # Fetch valid choices directly from the model to prevent injection/errors
                valid_statuses = dict(Test._meta.get_field('status').choices).keys()

                if new_status in valid_statuses:
                    try:
                        count = 0
                        # We need to loop and call .save() instead of .update() so that
                        # so the start_date and end_date logic in models.py is triggered
                        for test in tests_to_update:
                            test.status = new_status
                            test.save()
                            count += 1

                        messages.success(request, f"Successfully updated status to '{new_status}' for {count} tests.")
                    except Exception as e:
                        messages.error(request, f"Bulk update failed. Error: {str(e)}")
                else:
                    messages.error(request, "Invalid status selected.")

            # 3. Handle Service Change
            elif action.startswith('service_'):
                new_service = action.replace('service_', '')

                # Fetch valid choices directly from the model
                valid_services = dict(Test._meta.get_field('service').choices).keys()

                if new_service in valid_services:
                    try:
                        count = 0
                        for test in tests_to_update:
                            test.service = new_service
                            test.save()  # Trigger custom model logic
                            count += 1

                        messages.success(request, f"Successfully updated service to '{new_service}' for {count} tests.")
                    except Exception as e:
                        messages.error(request, f"Bulk update failed. Error: {str(e)}")
                else:
                    messages.error(request, "Invalid service selected.")

        return redirect("tests_user_list")


