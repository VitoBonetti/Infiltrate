from django.db.models import Count
from django.db import IntegrityError, connection
from django.views.generic import TemplateView
from django.core.paginator import Paginator
from django.core.files.storage import FileSystemStorage
from django.core.exceptions import ValidationError
from django.views import View
from django.views.generic import UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import (
    render,
    get_object_or_404,
    redirect
)
from management.mixins import ManagementAccessMixin
from management.validators import validate_file_size, validate_excel_magic_bytes
from rbac.management_policy import admin_can_write, admin_can_delete
from regions.models import Regions
from markets.models import Market
from organizations.models import Organization
from rbac.models import RoleAssignment
from accounts.models import User
from assets.models import Asset
from configurations.models import PlatformConfiguration
from .forms import (
    RegionsForm,
    MarketForm,
    OrganizationForm,
    UserForm,
    RoleAssignmentForm,
    AssetForm,
    ConfigurationForm,
)
import json
import jsonschema
import os
import threading
import pandas as pd


# Define the expected structure of the JSON
ORG_JSON_SCHEMA = {
    "type": "object",
    "patternProperties": {
        "^[a-zA-Z0-9_.-]+$": {
            "type": "array",
            "items": {"type": "string", "minLength": 1, "maxLength": 200}
        }
    },
    "additionalProperties": False
}


def process_assets_excel_background(file_path):
    """
    This function runs entirely in a background thread.
    """
    try:
        # Read Excel from the temporary file path
        df = pd.read_excel(file_path)

        # Filter out Archived statuses
        if 'Status' in df.columns:
            df = df[~df['Status'].astype(str).str.lower().isin(['archived'])]

        # Fetch organizations once to map them
        from organizations.models import Organization
        from assets.models import Asset
        org_map = {org.name.lower(): org for org in Organization.objects.all()}

        for index, row in df.iterrows():
            org_name = str(row.get('Managing Organization', '')).strip()
            asset_name = str(row.get('Name', '')).strip()
            inventory_id = str(row.get('Inventory Id', '')).strip()

            if not org_name or not asset_name or pd.isna(asset_name):
                continue

            org_instance = org_map.get(org_name.lower())
            if not org_instance:
                continue

            def clean_val(val, default=None):
                return str(val).strip() if not pd.isna(val) and str(val).lower() != 'nan' else default

            def clean_int(val):
                try:
                    return int(val) if not pd.isna(val) else None
                except (ValueError, TypeError):
                    return None

            def clean_bool(val):
                if pd.isna(val) or str(val).strip().lower() in ['nan', 'none', '']:
                    return None
                return str(val).lower() in ['yes', 'true', '1', 'y']

            defaults_dict = {
                'hosting_location': clean_val(row.get('Hosting Location')),
                'asset_type': clean_val(row.get('Type')),
                'asset_status': clean_val(row.get('Status')),
                'asset_stage': clean_val(row.get('Stage')),
                'cia_score': clean_int(row.get('Business Critical')),
                'confidentiality_score': clean_int(row.get('Confidentiality Rating')),
                'integrity_score': clean_int(row.get('Integrity Rating')),
                'availability_score': clean_int(row.get('Availability Rating')),
                'internet_facing': clean_bool(row.get('Internet Facing')),
                'as_a_service': clean_val(row.get('IaaS, PaaS, SaaS')),
                'master_record': clean_val(row.get('Master Record')),
            }

            asset_id_val = clean_int(row.get('ID'))

            if inventory_id and inventory_id.lower() != 'nan':
                defaults_dict['organization'] = org_instance
                defaults_dict['name'] = asset_name
                defaults_dict['ID'] = asset_id_val

                Asset.objects.update_or_create(
                    uuid=inventory_id,
                    defaults=defaults_dict
                )
            else:
                Asset.objects.update_or_create(
                    organization=org_instance,
                    name=asset_name,
                    ID=asset_id_val,
                    defaults=defaults_dict
                )

    except Exception as e:
        # In a background thread, we can't show a toast to the user, so we log it to the console
        print(f"CRITICAL ERROR in Background Asset Upload: {str(e)}")

    finally:
        # 1. ALWAYS clean up the temporary Excel file from the server
        if os.path.exists(file_path):
            os.remove(file_path)

        # 2. ALWAYS close the database connection.
        # Django automatically manages connections for web requests, but we must manually close them for threads!
        connection.close()


def recalculate_all_assets_kpi_background():
    """
    Runs in a background thread to update the KPI status of all assets
    without freezing the web request.
    """
    try:
        from assets.models import Asset
        # Loop through all assets and trigger their save method to recalculate is_kpi
        for asset in Asset.objects.all():
            asset.save(update_fields=['is_kpi'])
    except Exception as e:
        print(f"Error recalculating KPIs in background: {str(e)}")
    finally:
        # close the database connection for background threads!
        connection.close()

class ConfigurationUpdateView(ManagementAccessMixin, UpdateView):
    model = PlatformConfiguration
    form_class = ConfigurationForm
    template_name = "management/configuration.html"
    success_url = reverse_lazy("configuration_settings")

    def get_object(self, queryset=None):
        # Always fetch the single configuration instance
        return PlatformConfiguration.load()

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Platform configuration updated successfully. Asset KPIs are being recalculated in the background.")

        thread = threading.Thread(target=recalculate_all_assets_kpi_background)
        thread.start()

        return response


class ManagementHomeView(ManagementAccessMixin, TemplateView):
    template_name = "management/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            # Regions Stats
            ctx["active_regions_count"] = Regions.objects.filter(active=True).count()
            ctx["total_regions_count"] = Regions.objects.count()

            # Markets Stats
            ctx["total_markets_count"] = Market.objects.count()
            ctx["active_markets_count"] = Market.objects.filter(active=True).count()
            ctx["key_markets_count"] = Market.objects.filter(key_market=True).count()

            # Organizations Stats
            ctx["total_orgs_count"] = Organization.objects.count()

            # Users Stats
            ctx["total_users_count"] = User.objects.count()
            ctx["admin_users_count"] = User.objects.filter(is_platform_admin=True).count()
            ctx["god_user_count"] = User.objects.filter(is_superuser=True).count()
            ctx["scoped_role"] = ctx["total_users_count"] - (ctx["admin_users_count"] + ctx["god_user_count"])

            # Asset Stats
            ctx['total_assets'] = Asset.objects.count()
            ctx['active_assets'] = Asset.objects.filter(asset_status='Active').count()
            ctx['kpi_assets'] = Asset.objects.filter(is_kpi=True).count()

        except Exception:
            # Fallback if tables don't exist yet
            ctx["active_regions_count"] = 0
            ctx["total_regions_count"] = 0
            ctx["total_markets_count"] = 0
            ctx["active_markets_count"] = 0
            ctx["key_markets_count"] = 0
            ctx["total_orgs_count"] = 0
            ctx["total_users_count"] = 0
            ctx["admin_users_count"] = 0
            ctx["god_user_count"] = 0
            ctx["scoped_role"] = 0
            ctx['total_assets'] = 0
            ctx['active_assets'] = 0
            ctx['kpi_assets'] = 0

        return ctx


class RegionView(ManagementAccessMixin, View):
    template_name = "management/regions.html"

    def get(self, request, *args, **kwargs):
        region_id = request.GET.get("region_id")
        if region_id:
            region = get_object_or_404(Regions, uuid=region_id)
            form_region = RegionsForm(instance=region)
        else:
            form_region = RegionsForm()

        return self._render_page(request, form_region, region_id)

    def post(self, request, *args, **kwargs):
        # 1. Handle Single Delete Action
        if "delete_id" in request.POST:
            if not admin_can_delete(request.user):
                messages.error(request, "You do not have permission to delete regions.")
                return redirect("regions")

            try:
                region = get_object_or_404(Regions, uuid=request.POST["delete_id"])
                region.delete()
                messages.success(request, "Region deleted successfully.")
            except Exception as e:
                messages.error(request, f"Could not delete region. Error: {str(e)}")
            return redirect("regions")

        # 2. Handle Bulk Actions
        action = request.POST.get('action')
        selected_ids = request.POST.getlist('selected_items')

        if action and selected_ids:
            if not admin_can_write(request.user):
                messages.error(request, "Permission denied.")
                return redirect("regions")

            if action == 'bulk_delete':
                if not admin_can_delete(request.user):
                    messages.error(request, "You do not have permission to delete.")
                else:
                    try:
                        count, _ = Regions.objects.filter(uuid__in=selected_ids).delete()
                        messages.success(request, f"Successfully deleted {count} regions.")
                    except Exception as e:
                        messages.error(request, f"Bulk delete failed. Error: {str(e)}")
            elif action == 'bulk_activate':
                count = Regions.objects.filter(uuid__in=selected_ids).update(active=True)
                messages.success(request, f"Successfully activated {count} regions.")
            elif action == 'bulk_deactivate':
                count = Regions.objects.filter(uuid__in=selected_ids).update(active=False)
                messages.success(request, f"Successfully deactivated {count} regions.")

            return redirect("regions")

        # 3. Handle Create / Update Action
        if not admin_can_write(request.user):
            messages.error(request, "You do not have permission to modify regions.")
            return redirect("regions")

        region_id = request.GET.get("region_id")
        if region_id:
            region = get_object_or_404(Regions, uuid=region_id)
            form_region = RegionsForm(request.POST, instance=region)
        else:
            form_region = RegionsForm(request.POST)

        if form_region.is_valid():
            form_region.save()
            msg = "Region updated successfully." if region_id else "Region created successfully."
            messages.success(request, msg)
            return redirect("regions")

        for field, errors in form_region.errors.items():
            for error in errors:
                messages.error(request,
                               f"Validation Error: {error}" if field == '__all__' else f"{field.title()}: {error}")

        # If form is invalid, re-render the page with errors
        return self._render_page(request, form_region, region_id)

    def _render_page(self, request, form_region, region_id=None):
        # Base Queryset
        queryset = Regions.objects.annotate(market_count=Count('markets'))

        # Search Filter
        search_query = request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(region__icontains=search_query)

        # Active Status Filter
        active_filter = request.GET.get('active', '')
        if active_filter == 'true':
            queryset = queryset.filter(active=True)
        elif active_filter == 'false':
            queryset = queryset.filter(active=False)

        # Sorting
        sort_by = request.GET.get('sort', 'region')
        valid_sorts = ['region', '-region', '-created_at', 'created_at', 'market_count', '-market_count']
        if sort_by in valid_sorts:
            queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by('region')

        # 3. Stats
        active_count = queryset.filter(active=True).count()
        total_count = queryset.count()

        # 4. Pagination
        paginator = Paginator(queryset, 10)  # 10 items per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            "page_obj": page_obj,
            "search_query": search_query,  # Pass search back to template
            "active_filter": active_filter,
            "sort_by": sort_by,  # Pass sort back to template
            "form_region": form_region,
            "active_regions_count": active_count,
            "total_regions_count": total_count,
            "editing": bool(region_id),
            "can_write": admin_can_write(request.user),
            "can_delete": admin_can_delete(request.user),
        }
        return render(request, self.template_name, context)


class MarketListView(ManagementAccessMixin, View):
    template_name = "management/markets.html"

    def get(self, request, *args, **kwargs):
        # Base queryset, using select_related for efficiency since we display Region
        queryset = Market.objects.select_related('region').all()

        # 1. Filtering by market name
        search_query = request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(market__icontains=search_query)

        # 2. Filtering
        active_filter = request.GET.get('active', '')
        if active_filter == 'true':
            queryset = queryset.filter(active=True)
        elif active_filter == 'false':
            queryset = queryset.filter(active=False)

        key_filter = request.GET.get('key_market', '')
        if key_filter == 'true':
            queryset = queryset.filter(key_market=True)
        elif key_filter == 'false':
            queryset = queryset.filter(key_market=False)

        # 3. Sorting
        sort_by = request.GET.get('sort', 'market')
        valid_sorts = ['market', '-market', 'region__region', '-region__region', 'created_at', '-created_at']
        if sort_by in valid_sorts:
            queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by('market')

        # 4. Stats (calculate before pagination so it reflects overall data)
        total_count = Market.objects.count()
        active_count = Market.objects.filter(active=True).count()
        key_count = Market.objects.filter(key_market=True).count()

        # 5. Pagination
        paginator = Paginator(queryset, 10)  # 10 items per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            'page_obj': page_obj,
            'search_query': search_query,
            'active_filter': active_filter,
            'key_filter': key_filter,
            'sort_by': sort_by,
            'total_count': total_count,
            'active_count': active_count,
            'key_count': key_count,
            'can_write': admin_can_write(request.user),
            'can_delete': admin_can_delete(request.user),
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        # Handle Single Deletion
        if "delete_id" in request.POST:
            if not admin_can_delete(request.user):
                messages.error(request, "You do not have permission to delete markets.")
                return redirect("markets")
            try:
                market = get_object_or_404(Market, uuid=request.POST["delete_id"])
                market_name = market.market
                market.delete()
                messages.success(request, f"Market '{market_name}' deleted successfully.")
            except Exception as e:
                messages.error(request, f"Could not delete market. Error: {str(e)}")

            return redirect("markets")

        action = request.POST.get('action')
        selected_ids = request.POST.getlist('selected_items')

        if action and selected_ids:
            if not admin_can_write(request.user):
                messages.error(request, "Permission denied.")
                return redirect("markets")

            if action == 'bulk_delete':
                if not admin_can_delete(request.user):
                    messages.error(request, "You do not have permission to delete.")
                else:
                    try:
                        count, _ = Market.objects.filter(uuid__in=selected_ids).delete()
                        messages.success(request, f"Successfully deleted {count} markets.")
                    except Exception as e:
                        messages.error(request, f"Bulk delete failed. Error: {str(e)}")
            elif action == 'bulk_activate':
                count = Market.objects.filter(uuid__in=selected_ids).update(active=True)
                messages.success(request, f"Successfully activated {count} markets.")
            elif action == 'bulk_deactivate':
                count = Market.objects.filter(uuid__in=selected_ids).update(active=False)
                messages.success(request, f"Successfully deactivated {count} markets.")
            elif action == 'bulk_set_key':
                count = Market.objects.filter(uuid__in=selected_ids).update(key_market=True)
                messages.success(request, f"Successfully marked {count} markets as Key Markets.")
            elif action == 'bulk_remove_key':
                count = Market.objects.filter(uuid__in=selected_ids).update(key_market=False)
                messages.success(request, f"Successfully removed Key Market status from {count} markets.")

        return redirect("markets")


class MarketFormView(ManagementAccessMixin, View):
    template_name = "management/market_form.html"

    def get(self, request, *args, **kwargs):
        if not admin_can_write(request.user):
            messages.error(request, "You do not have permission to modify markets.")
            return redirect("markets")

        market_id = request.GET.get("market_id")
        if market_id:
            market = get_object_or_404(Market, uuid=market_id)
            form = MarketForm(instance=market)
            editing = True
        else:
            form = MarketForm()
            editing = False

        return render(request, self.template_name, {'form': form, 'editing': editing, 'market_id': market_id})

    def post(self, request, *args, **kwargs):
        if not admin_can_write(request.user):
            messages.error(request, "You do not have permission to modify markets.")
            return redirect("markets")

        market_id = request.GET.get("market_id")
        if market_id:
            market = get_object_or_404(Market, uuid=market_id)
            # request.FILES is required because of the flag_icons ImageField!
            form = MarketForm(request.POST, request.FILES, instance=market)
        else:
            form = MarketForm(request.POST, request.FILES)

        if form.is_valid():
            market_instance = form.save(commit=False)
            market_instance.save()

            msg = "Market updated successfully." if market_id else "Market created successfully."
            messages.success(request, msg)

            if 'save_and_add' in request.POST:
                return redirect("market_form")
            else:
                return redirect("markets")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        messages.error(request, f"Validation Error: {error}")
                    else:
                        # custom error here
                        pass

        return render(request, self.template_name, {'form': form, 'editing': bool(market_id), 'market_id': market_id})


class OrganizationListView(ManagementAccessMixin, View):
    template_name = "management/organizations.html"

    def get(self, request, *args, **kwargs):
        queryset = Organization.objects.select_related('market__region').all()

        # 1. Search Filter
        search_query = request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(name__icontains=search_query)

        # 2. Market Filter (NEW)
        market_filter = request.GET.get('market', '')
        if market_filter:
            queryset = queryset.filter(market__uuid=market_filter)

        # 3. Sorting
        sort_by = request.GET.get('sort', 'name')
        valid_sorts = ['name', '-name', 'market__market', '-market__market', 'market__region__region', '-market__region__region']
        if sort_by in valid_sorts:
            queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by('name')

        total_count = queryset.count()

        # 4. Pagination
        paginator = Paginator(queryset, 15)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # 5. Get all markets for the dropdown filter
        markets = Market.objects.all().order_by('market')

        context = {
            'page_obj': page_obj,
            'search_query': search_query,
            'market_filter': market_filter,
            'markets': markets,
            'sort_by': sort_by,
            'total_count': total_count,
            'can_write': admin_can_write(request.user),
            'can_delete': admin_can_delete(request.user),
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        if "delete_id" in request.POST:
            if not admin_can_delete(request.user):
                messages.error(request, "Permission denied.")
                return redirect("organizations")

            try:
                org = get_object_or_404(Organization, uuid=request.POST["delete_id"])
                org.delete()
                messages.success(request, f"Organization '{org.name}' deleted.")
            except Exception as e:
                messages.error(request, f"Could not delete organization. Error: {str(e)}")

            return redirect("organizations")

        # Handle Bulk Deletion
        action = request.POST.get('action')
        selected_ids = request.POST.getlist('selected_items')

        if action == 'bulk_delete' and selected_ids:
            if not admin_can_delete(request.user):
                messages.error(request, "Permission denied.")
                return redirect("organizations")

            try:
                count, _ = Organization.objects.filter(uuid__in=selected_ids).delete()
                messages.success(request, f"Successfully deleted {count} organizations.")
            except Exception as e:
                messages.error(request, f"Bulk delete failed. Error: {str(e)}")

        return redirect("organizations")


class OrganizationFormView(ManagementAccessMixin, View):
    template_name = "management/organization_form.html"

    def get(self, request, *args, **kwargs):
        if not admin_can_write(request.user):
            messages.error(request, "Permission denied.")
            return redirect("organizations")

        org_id = request.GET.get("org_id")
        if org_id:
            org = get_object_or_404(Organization, uuid=org_id)
            form = OrganizationForm(instance=org)
            editing = True
        else:
            form = OrganizationForm()
            editing = False

        return render(request, self.template_name, {'form': form, 'editing': editing, 'org_id': org_id})

    def post(self, request, *args, **kwargs):
        if not admin_can_write(request.user):
            messages.error(request, "Permission denied.")
            return redirect("organizations")

        submission_type = request.POST.get('submission_type', 'single')
        org_id = request.GET.get("org_id")

        # 1. Handle Single Form Submission
        if submission_type == 'single':
            if org_id:
                org = get_object_or_404(Organization, uuid=org_id)
                form = OrganizationForm(request.POST, instance=org)
            else:
                form = OrganizationForm(request.POST)

            if form.is_valid():
                form.save()
                messages.success(request, "Organization saved successfully.")
                if 'save_and_add' in request.POST:
                    return redirect("organization_form")
                return redirect("organizations")
            return render(request, self.template_name, {'form': form, 'editing': bool(org_id), 'org_id': org_id})

        # 2. Handle JSON Bulk Submissions
        json_data = None
        try:
            if submission_type == 'json_text':
                json_data = json.loads(request.POST.get('json_text', '{}'))
            elif submission_type == 'json_file':
                file = request.FILES.get('json_file')
                if file:
                    # SECURE: Check file size before reading into memory (e.g., limit to 2MB)
                    if file.size > 2 * 1024 * 1024:
                        messages.error(request, "JSON file is too large. Maximum size is 2MB.")
                        return redirect("organization_form")

                    json_data = json.loads(file.read().decode('utf-8'))
                else:
                    raise ValueError("No file uploaded.")

            # SECURE: Validate the JSON structure to prevent deeply nested or malformed injections
            if json_data:
                jsonschema.validate(instance=json_data, schema=ORG_JSON_SCHEMA)

        except json.JSONDecodeError:
            messages.error(request, "Invalid JSON formatting.")
            return redirect("organization_form")
        except jsonschema.exceptions.ValidationError as e:
            messages.error(request, f"JSON Schema validation failed: {e.message}")
            return redirect("organization_form")
        except Exception as e:
            messages.error(request, f"Error processing file: {str(e)}")
            return redirect("organization_form")

        # 3. Process the parsed JSON
        if json_data:
            created_count = 0
            skipped_count = 0
            missing_markets = set()

            for market_code, org_list in json_data.items():
                # Find market by code
                market = Market.objects.filter(code=market_code).first()
                if not market:
                    missing_markets.add(market_code)
                    continue

                # Create organizations
                for org_name in org_list:
                    obj, created = Organization.objects.get_or_create(market=market, name=org_name)
                    if created:
                        created_count += 1
                    else:
                        skipped_count += 1

            # Provide feedback
            if created_count > 0:
                messages.success(request, f"Successfully created {created_count} organizations.")
            if skipped_count > 0:
                messages.info(request, f"Skipped {skipped_count} organizations (already existed in that market).")
            if missing_markets:
                messages.warning(request,
                                 f"Skipped organizations for unknown market codes: {', '.join(missing_markets)}")

        return redirect("organizations")


class UserListView(ManagementAccessMixin, View):
    template_name = "management/users.html"

    def get(self, request, *args, **kwargs):
        queryset = User.objects.all()

        search_query = request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(email__icontains=search_query)

        active_filter = request.GET.get('active', '')
        if active_filter == 'true':
            queryset = queryset.filter(is_active=True)
        elif active_filter == 'false':
            queryset = queryset.filter(is_active=False)

        admin_filter = request.GET.get('is_admin', '')
        if admin_filter == 'true':
            queryset = queryset.filter(is_platform_admin=True)

        sort_by = request.GET.get('sort', 'email')
        valid_sorts = ['email', '-email', 'first_name', '-first_name', 'date_joined', '-date_joined']
        if sort_by in valid_sorts:
            queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by('email')

        paginator = Paginator(queryset, 15)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            'page_obj': page_obj,
            'search_query': search_query,
            'active_filter': active_filter,
            'admin_filter': admin_filter,
            'sort_by': sort_by,
            'total_count': User.objects.count(),
            'admin_count': User.objects.filter(is_platform_admin=True).count(),
            'can_write': admin_can_write(request.user),
            'can_delete': admin_can_delete(request.user),
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        # 1. Handle Single Deletion
        if "delete_id" in request.POST:
            if not admin_can_delete(request.user):
                messages.error(request, "Permission denied.")
                return redirect("users")
            try:
                user_obj = get_object_or_404(User, id=request.POST["delete_id"])

                # SECURITY: Cannot delete yourself
                if user_obj == request.user:
                    messages.error(request, "You cannot delete your own account.")
                    return redirect("users")

                # SECURITY: Admin cannot delete GOD or Admin
                if (user_obj.is_superuser or user_obj.is_platform_admin) and not request.user.is_superuser:
                    messages.error(request, "Permission denied. Only GODs can delete global administrators.")
                    return redirect("users")

                user_obj.delete()
                messages.success(request, f"User '{user_obj.email}' deleted.")
            except Exception as e:
                messages.error(request, f"Could not delete user. Error: {str(e)}")
            return redirect("users")

        # 2. Handle Bulk Actions
        action = request.POST.get('action')
        selected_ids = request.POST.getlist('selected_items')

        if action and selected_ids:
            if not admin_can_write(request.user):
                messages.error(request, "Permission denied.")
                return redirect("users")

            # Get base queryset
            users_to_modify = User.objects.filter(id__in=selected_ids)

            # SECURITY: Exclude yourself from bulk actions (so you don't accidentally lock yourself out)
            users_to_modify = users_to_modify.exclude(id=request.user.id)

            # SECURITY: If not a GOD, strictly exclude all GODs and Admins from being modified in bulk
            if not request.user.is_superuser:
                original_count = users_to_modify.count()
                users_to_modify = users_to_modify.exclude(is_superuser=True).exclude(is_platform_admin=True)
                if users_to_modify.count() < original_count:
                    messages.warning(request,
                                     "Some selected users were skipped because you lack permission to modify global administrators.")

            if action == 'bulk_delete' and admin_can_delete(request.user):
                count, _ = users_to_modify.delete()
                messages.success(request, f"Successfully deleted {count} users.")
            elif action == 'bulk_activate':
                count = users_to_modify.update(is_active=True)
                messages.success(request, f"Activated {count} users.")
            elif action == 'bulk_deactivate':
                count = users_to_modify.update(is_active=False)
                messages.success(request, f"Deactivated {count} users.")

        return redirect("users")


class UserFormView(ManagementAccessMixin, View):
    template_name = "management/user_form.html"

    def get(self, request, *args, **kwargs):
        if not admin_can_write(request.user):
            messages.error(request, "Permission denied.")
            return redirect("users")

        user_id = request.GET.get("user_id")
        if user_id:
            user_obj = get_object_or_404(User, id=user_id)

            # SECURITY: Admin cannot load the edit page for a GOD or Admin
            if (user_obj.is_superuser or user_obj.is_platform_admin) and not request.user.is_superuser:
                messages.error(request, "Permission denied. Only GODs can edit global administrators.")
                return redirect("users")

            form = UserForm(instance=user_obj)
            editing = True
        else:
            form = UserForm()
            editing = False

        return render(request, self.template_name, {'form': form, 'editing': editing, 'user_id': user_id})

    def post(self, request, *args, **kwargs):
        if not admin_can_write(request.user):
            messages.error(request, "Permission denied.")
            return redirect("users")

        user_id = request.GET.get("user_id")
        if user_id:
            user_obj = get_object_or_404(User, id=user_id)

            # SECURITY: Admin cannot submit edits for a GOD or Admin (prevents malicious POST requests)
            if (user_obj.is_superuser or user_obj.is_platform_admin) and not request.user.is_superuser:
                messages.error(request, "Permission denied. Only GODs can edit global administrators.")
                return redirect("users")

            form = UserForm(request.POST, instance=user_obj)
        else:
            form = UserForm(request.POST)

        if form.is_valid():
            new_user = form.save(commit=False)
            if not user_id:
                # Generate the base username (e.g., john.doe)
                base_username = f"{new_user.first_name.strip().lower()}.{new_user.last_name.strip().lower()}"

                # Ensure it is unique
                username = base_username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1

                new_user.username = username
                new_user.set_password('GostPillar2024!')
            new_user.save()

            messages.success(request, "User saved successfully.")
            return redirect("users")

        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field.title()}: {error}")

        return render(request, self.template_name, {'form': form, 'editing': bool(user_id), 'user_id': user_id})


class UserRoleView(ManagementAccessMixin, View):
    template_name = "management/user_roles.html"

    def get(self, request, user_id, *args, **kwargs):
        target_user = get_object_or_404(User, id=user_id)
        assignments = RoleAssignment.objects.filter(user=target_user)
        form = RoleAssignmentForm()

        context = {
            'target_user': target_user,
            'assignments': assignments,
            'form': form,
            'can_write': admin_can_write(request.user),
            'can_delete': admin_can_delete(request.user),
        }
        return render(request, self.template_name, context)

    def post(self, request, user_id, *args, **kwargs):
        target_user = get_object_or_404(User, id=user_id)

        if "global_role" in request.POST:
            if not request.user.is_superuser:
                messages.error(request, "Only GOD (Superusers) can manage global platform roles.")
                return redirect("user_roles", user_id=user_id)
            # 1. Handle Global Role Management (Promote/Demote GODs and Admins)
            if target_user == request.user:
                messages.error(request, "You cannot modify your own global role. Ask another GOD to do it.")
                return redirect("user_roles", user_id=user_id)

            new_role = request.POST.get("global_role")
            if new_role == "god":
                target_user.is_superuser = True
                target_user.is_platform_admin = False
                target_user.is_pentester = False
                messages.success(request, f"{target_user.username} has been promoted to GOD (Superuser).")
            elif new_role == "admin":
                target_user.is_superuser = False
                target_user.is_platform_admin = True
                target_user.is_pentester = False
                messages.success(request, f"{target_user.username} has been promoted to Platform Admin.")
            elif new_role == "pentester":
                target_user.is_superuser = False
                target_user.is_platform_admin = False
                target_user.is_pentester = True
                messages.success(request, f"{target_user.username} has been assigned Global Pentester.")
            elif new_role == "standard":
                target_user.is_superuser = False
                target_user.is_platform_admin = False
                target_user.is_pentester = False
                messages.success(request, f"{target_user.username} is now a Standard User.")

            target_user.save()
            return redirect("user_roles", user_id=user_id)

        # 2. SECURITY CHECK: Admins cannot modify scopes of GODs or other Admins
        if (target_user.is_superuser or target_user.is_platform_admin) and not request.user.is_superuser:
            messages.error(request, "Permission Denied. Only GODs can modify the roles of global administrators.")
            return redirect("user_roles", user_id=user_id)

        # 3. Handle Delete Assignment
        if "delete_assignment_id" in request.POST:
            if not admin_can_delete(request.user):
                messages.error(request, "Permission denied.")
                return redirect("user_roles", user_id=user_id)

            assignment = get_object_or_404(RoleAssignment, id=request.POST["delete_assignment_id"], user=target_user)
            assignment.delete()
            messages.success(request, "Role assignment removed.")
            return redirect("user_roles", user_id=user_id)

        # 4. Handle Add Assignment
        if not admin_can_write(request.user):
            messages.error(request, "Permission denied.")
            return redirect("user_roles", user_id=user_id)

        form = RoleAssignmentForm(request.POST, user=target_user)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, f"Role assigned successfully.")
            except Exception as e:
                # Catch database-level constraint errors
                messages.error(request, f"Error assigning role: {str(e)}")
        else:
            # Catch model-level ValidationErrors (where your RBAC rules live)
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        messages.error(request, f"Rule Violation: {error}")
                    else:
                        messages.error(request, f"{field.title()}: {error}")

        return redirect("user_roles", user_id=user_id)


class AssetListView(ManagementAccessMixin, View):
    template_name = "management/assets.html"


    def get(self, request, *args, **kwargs):
        queryset = Asset.objects.select_related('organization__market').all()

        search_query = request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(name__icontains=search_query)

        org_filter = request.GET.get('org', '')
        if org_filter:
            queryset = queryset.filter(organization__uuid=org_filter)

        is_kpi_filter = request.GET.get('is_kpi_filter', '')
        if is_kpi_filter == 'true':
            queryset = queryset.filter(is_kpi=True)
        elif is_kpi_filter == 'false':
            queryset = queryset.filter(is_kpi=False)

        is_pentest_queue = request.GET.get('is_pentest_queue', '')
        if is_pentest_queue == 'true':
            queryset = queryset.filter(is_pentest_queue=True)
        elif is_pentest_queue == 'false':
            queryset = queryset.filter(is_pentest_queue=False)

        is_critical_app = request.GET.get('is_critical_app', '')
        if is_critical_app == 'true':
            queryset = queryset.filter(is_critical_app=True)
        elif is_critical_app == 'false':
            queryset = queryset.filter(is_critical_app=False)


        sort_by = request.GET.get('sort', 'name')
        valid_sorts = ['name', '-name', 'organization__name', '-organization__name', 'asset_type', '-asset_type', 'asset_status', '-asset_status']
        if sort_by in valid_sorts:
            queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by('name')

        paginator = Paginator(queryset, 500)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        organizations = Organization.objects.all().order_by('name')

        total_assets = queryset.count()
        total_kpi_assets = queryset.filter(is_kpi=True).count()
        total_queue_assets = queryset.filter(is_pentest_queue=True).count()

        context = {
            'page_obj': page_obj,
            'search_query': search_query,
            'org_filter': org_filter,
            'organizations': organizations,
            'sort_by': sort_by,
            'is_kpi_filter': is_kpi_filter,
            'is_pentest_queue': is_pentest_queue,
            'is_critical_app': is_critical_app,
            'total_assets': total_assets,
            'total_kpi_assets': total_kpi_assets,
            'total_queue_assets': total_queue_assets,
            'total_count': queryset.count(),
            'can_write': admin_can_write(request.user),
            'can_delete': admin_can_delete(request.user),
        }
        return render(request, self.template_name, context)


    def post(self, request, *args, **kwargs):
        if "delete_id" in request.POST:
            if not admin_can_delete(request.user):
                messages.error(request, "Permission denied.")
                return redirect("assets")

            asset = get_object_or_404(Asset, uuid=request.POST["delete_id"])
            asset.delete()
            messages.success(request, f"Asset '{asset.name}' deleted.")

        # Bulk Delete Logic
        action = request.POST.get('action')
        selected_ids = request.POST.getlist('selected_items')
        if action == 'bulk_delete' and selected_ids and admin_can_delete(request.user):
            count, _ = Asset.objects.filter(uuid__in=selected_ids).delete()
            messages.success(request, f"Successfully deleted {count} assets.")

        return redirect("assets")


class AssetFormView(ManagementAccessMixin, View):
    template_name = "management/asset_form.html"

    def get(self, request, *args, **kwargs):
        if not admin_can_write(request.user):
            messages.error(request, "Permission denied.")
            return redirect("assets")

        asset_id = request.GET.get("asset_id")
        if asset_id:
            asset = get_object_or_404(Asset, uuid=asset_id)
            form = AssetForm(instance=asset)
            editing = True
        else:
            form = AssetForm()
            editing = False

        return render(request, self.template_name, {'form': form, 'editing': editing, 'asset_id': asset_id})

    def post(self, request, *args, **kwargs):
        if not admin_can_write(request.user):
            messages.error(request, "Permission denied.")
            return redirect("assets")

        submission_type = request.POST.get('submission_type', 'single')
        asset_id = request.GET.get("asset_id")

        # 1. Single Form Logic
        if submission_type == 'single':
            if asset_id:
                asset = get_object_or_404(Asset, uuid=asset_id)
                form = AssetForm(request.POST, instance=asset)
            else:
                form = AssetForm(request.POST)

            if form.is_valid():
                form.save()
                messages.success(request, "Asset saved successfully.")
                if 'save_and_add' in request.POST:
                    return redirect("asset_form")
                return redirect("assets")
            return render(request, self.template_name, {'form': form, 'editing': bool(asset_id), 'asset_id': asset_id})

        # 2. Excel Upload Logic
        if submission_type == 'excel_file':
            excel_file = request.FILES.get('excel_file')
            if not excel_file:
                messages.error(request, "No file uploaded.")
                return redirect("asset_form")

            try:
                validate_file_size(excel_file)
                validate_excel_magic_bytes(excel_file)
            except ValidationError as e:
                # e.messages is a list of error strings from the ValidationError
                messages.error(request, e.messages[0])
                return redirect("asset_form")

            try:
                # save the file to the server disk temporarily because  Django destroys request.FILES as soon as we return the page to the user!
                fs = FileSystemStorage()
                filename = fs.save(f"temp_asset_upload_{excel_file.name}", excel_file)
                file_path = fs.path(filename)

                # Spin up a background thread and point it to our saved file
                thread = threading.Thread(target=process_assets_excel_background, args=(file_path,))
                thread.start()
                messages.success(request,
                                 "Your Excel file has been queued and is processing in the background! You can safely navigate away.")
            except Exception as e:
                messages.error(request, f"Error starting background process: {str(e)}")

            return redirect("assets")