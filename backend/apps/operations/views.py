from collections import defaultdict
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.core.exceptions import PermissionDenied
from apps.accounts.models import UserAccount
from apps.audit.services import log_activity
from apps.core.decorators import manager_required, role_required
from apps.projects.models import Project
from apps.projects.selectors import can_access_project
from apps.questionnaires.models import ProjectQuestionnaire
from apps.questionnaires.services import WEBSITE_TEMPLATE_CODE
from .forms import CredentialPurchaseForm, GeneralManagementRecordForm, ProductionRecordForm, WebProductionStructureForm
from .models import (
    CompleteStatus,
    CredentialPurchase,
    GeneralManagementRecord,
    ProductionRecord,
    ProductionWorkStatus,
    WebProductionCounty,
    WebProductionCountyService,
    WebProductionCity,
    WebProductionInternalSection,
    WebProductionPage,
    WebProductionSheet,
)
from .services import apply_seo_automation, ensure_web_production_structure, save_credential_purchase, save_production_record


@role_required("administration")
def general_list(request):
    q = request.GET.get("q", "").strip()
    records = GeneralManagementRecord.objects.select_related("client", "responsible")
    credentials = CredentialPurchase.objects.select_related("client", "project").all()
    if q:
        records = records.filter(Q(client__business_name__icontains=q) | Q(detail_name__icontains=q) | Q(code__icontains=q))
        credentials = credentials.filter(Q(client__business_name__icontains=q) | Q(credential_name__icontains=q) | Q(provider__icontains=q))
    return render(request, "operations/general_list.html", {"records": records[:300], "credential_records": credentials[:300], "q": q})


@role_required("administration")
def general_create(request):
    form = GeneralManagementRecordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False); obj.created_by = request.user; obj.save()
        log_activity(request.user, "operations", "general_create", obj)
        messages.success(request, f"Registro {obj.code} guardado.")
        return redirect("operations:general_list")
    return render(request, "shared/form.html", {"form": form, "title": "Nueva compra · Dominio / Host", "subtitle": "Registra únicamente dominio, host o dominio + host."})


@role_required("administration")
def general_edit(request, pk):
    obj = get_object_or_404(GeneralManagementRecord, pk=pk)
    form = GeneralManagementRecordForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save(); log_activity(request.user, "operations", "general_update", obj); messages.success(request, "Registro actualizado."); return redirect("operations:general_list")
    return render(request, "shared/form.html", {"form": form, "title": f"Editar {obj.code}", "subtitle": obj.client_label})


@role_required("administration")
def general_detail(request, pk):
    obj = get_object_or_404(GeneralManagementRecord.objects.select_related("client", "responsible", "created_by"), pk=pk)
    return render(request, "operations/general_detail.html", {"record": obj})


@manager_required
@require_POST
def general_delete(request, pk):
    obj = get_object_or_404(GeneralManagementRecord, pk=pk)
    label = obj.code
    log_activity(request.user, "operations", "general_delete", obj, description=f"Eliminado {label}")
    obj.delete()
    messages.success(request, f"{label} eliminado.")
    return redirect("operations:general_list")


@role_required("administration")
def credential_list(request):
    # Kept for backwards-compatible links; the UI is now unified.
    return redirect("operations:general_list")


@role_required("administration", "marketing")
def credential_create(request):
    form = CredentialPurchaseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        save_credential_purchase(form=form, user=request.user)
        messages.success(request, "Compra registrada y recordatorio anual de renovación creado.")
        return redirect("operations:general_list" if request.user.role == "administration" or request.user.is_manager else "marketing:list")
    return render(request, "shared/form.html", {"form": form, "title": "Registrar compra de credencial", "subtitle": "La fecha de renovación se calcula a un año si se deja vacía. No guardar contraseñas aquí."})


@role_required("administration", "marketing")
def credential_edit(request, pk):
    obj = get_object_or_404(CredentialPurchase, pk=pk)
    form = CredentialPurchaseForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        save_credential_purchase(form=form, user=request.user)
        messages.success(request, "Credencial y recordatorio de renovación actualizados.")
        return redirect("operations:general_list" if request.user.role == "administration" or request.user.is_manager else "marketing:list")
    return render(request, "shared/form.html", {"form": form, "title": "Editar credencial", "subtitle": obj.client.business_name})


@role_required("administration", "marketing")
def credential_detail(request, pk):
    obj = get_object_or_404(CredentialPurchase.objects.select_related("client", "project", "created_by"), pk=pk)
    return render(request, "operations/credential_detail.html", {"record": obj})


@manager_required
@require_POST
def credential_delete(request, pk):
    obj = get_object_or_404(CredentialPurchase, pk=pk)
    label = obj.credential_name
    log_activity(request.user, "operations", "credential_delete", obj, description=f"Eliminada {label}")
    obj.delete()
    messages.success(request, "Credencial eliminada.")
    return redirect("operations:general_list")


@role_required("administration")
def production_list(request):
    records = ProductionRecord.objects.select_related("client", "project", "collaborator")
    return render(request, "operations/production_list.html", {"records": records})


@role_required("administration")
def production_create(request):
    form = ProductionRecordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        save_production_record(form=form, user=request.user); messages.success(request, "Registro de producción guardado."); return redirect("operations:production_list")
    return render(request, "shared/form.html", {"form": form, "title": "Nuevo registro · Producción", "subtitle": "Plan, diseño, estado técnico, colaborador y valores."})


@role_required("administration")
def production_edit(request, pk):
    obj = get_object_or_404(ProductionRecord, pk=pk)
    form = ProductionRecordForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        save_production_record(form=form, user=request.user); messages.success(request, "Producción actualizada."); return redirect("operations:production_list")
    return render(request, "shared/form.html", {"form": form, "title": "Editar producción", "subtitle": obj.client.business_name})


# ---------------------------------------------------------------------------
# DESARROLLO · FICHA DE PRODUCCIÓN WEB · V5
# ---------------------------------------------------------------------------

def _developer_users():
    return UserAccount.objects.filter(
        role__in=[UserAccount.Role.DEVELOPER, UserAccount.Role.MANAGER],
        is_active=True,
    ).order_by("first_name", "last_name", "email")


def _technical_production_inputs(project):
    questionnaire = ProjectQuestionnaire.objects.filter(
        project=project,
        template__code=WEBSITE_TEMPLATE_CODE,
    ).prefetch_related("answers__question").first()
    services = []
    strategy = ""
    if questionnaire:
        for answer in questionnaire.answers.all():
            if answer.question.key == "main_services":
                services = [
                    item for item in (answer.value_json or {}).get("items", [])
                    if item.get("name") and not item.get("excluded")
                ]
            elif answer.question.key == "seo_page_strategy":
                strategy = (answer.value_json or {}).get("strategy", "")
    # Primary service first, then alphabetical, without duplicates.
    seen = set()
    normalized = []
    for item in sorted(services, key=lambda x: (not bool(x.get("primary")), str(x.get("name", "")).lower())):
        name = str(item.get("name", "")).strip()
        key = name.lower()
        if name and key not in seen:
            seen.add(key)
            normalized.append({"name": name, "primary": bool(item.get("primary"))})
    return questionnaire, normalized, strategy


def _binary(value):
    return CompleteStatus.COMPLETE if value == CompleteStatus.COMPLETE else CompleteStatus.INCOMPLETE


def _update_seo_row(
    obj,
    request,
    prefix,
    allowed_responsibles,
):
    obj.name = request.POST.get(
        f"{prefix}_name",
        "",
    ).strip()

    obj.keyword = request.POST.get(
        f"{prefix}_keyword",
        "",
    ).strip()

    obj.secondary_keywords = (
        request.POST.get(
            f"{prefix}_secondary_keywords",
            "",
        ).strip()
    )

    obj.meta_title = request.POST.get(
        f"{prefix}_meta_title",
        "",
    ).strip()

    obj.meta_description = (
        request.POST.get(
            f"{prefix}_meta_description",
            "",
        ).strip()
    )

    obj.notes = request.POST.get(
        f"{prefix}_notes",
        "",
    ).strip()

    workflow_status = request.POST.get(
        f"{prefix}_workflow_status",
        ProductionWorkStatus.NOT_STARTED,
    )

    if (
        workflow_status
        not in ProductionWorkStatus.values
    ):
        workflow_status = (
            ProductionWorkStatus.NOT_STARTED
        )

    obj.workflow_status = workflow_status

    obj.review_status = _binary(
        request.POST.get(
            f"{prefix}_review_status"
        )
    )


    responsible_id = request.POST.get(
        f"{prefix}_responsible",
        "",
    ).strip()

    obj.responsible = (
        allowed_responsibles.get(
            int(responsible_id)
        )
        if responsible_id.isdigit()
        else None
    )


    reviewer_id = request.POST.get(
        f"{prefix}_reviewer",
        "",
    ).strip()

    obj.reviewer = (
        allowed_responsibles.get(
            int(reviewer_id)
        )
        if reviewer_id.isdigit()
        else None
    )


    if isinstance(
        obj,
        WebProductionCountyService,
    ):

        obj.service_name = (
            request.POST.get(
                f"{prefix}_service_name",
                "",
            ).strip()
        )

        obj.is_global = (
            request.POST.get(
                f"{prefix}_is_global"
            )
            == "1"
        )

        if (
            not obj.name
            and obj.service_name
        ):
            obj.name = (
                f"{obj.service_name} "
                f"{obj.county.name}"
            ).strip()


    elif isinstance(
        obj,
        WebProductionCity,
    ):

        county_id = request.POST.get(
            f"{prefix}_county",
            "",
        ).strip()

        obj.county = (
            WebProductionCounty.objects
            .filter(
                pk=county_id,
                sheet=obj.sheet,
            )
            .first()
            if county_id.isdigit()
            else None
        )


    obj.updated_by = request.user

    apply_seo_automation(
        obj
    )

    obj.save()

def _ensure_internal_sections(
    sheet,
    user,
):
    defaults = [
        (
            "FAQ",
            "S",
            1,
        ),
        (
            "SITE KITS",
            "S",
            2,
        ),
        (
            "PHP",
            "S",
            1,
        ),
        (
            "CTA",
            "S",
            1,
        ),
        (
            "Form + Reviews",
            "C",
            3,
        ),
        (
            "Header",
            "C",
            3,
        ),
        (
            "Footer",
            "C",
            3,
        ),
        (
            "Hero",
            "M",
            1,
        ),
        (
            "Carrusel o Galería",
            "M",
            1,
        ),
        (
            "Rank Math e indexación",
            "S",
            2,
        ),
    ]

    for order, (
        name,
        complexity,
        points,
    ) in enumerate(
        defaults,
        start=1,
    ):

        WebProductionInternalSection.objects.get_or_create(
            sheet=sheet,
            name=name,
            defaults={
                "complexity": complexity,
                "points": points,
                "order": order,
                "updated_by": user,
            },
        )
def _update_internal_section(
    obj,
    request,
    prefix,
    allowed_responsibles,
):

    obj.name = request.POST.get(
        f"{prefix}_name",
        obj.name,
    ).strip()

    complexity = request.POST.get(
        f"{prefix}_complexity",
        obj.complexity,
    )

    if complexity in {
        "S",
        "M",
        "C",
    }:
        obj.complexity = complexity


    points = request.POST.get(
        f"{prefix}_points",
        "",
    ).strip()

    if points.isdigit():
        obj.points = int(points)


    workflow_status = request.POST.get(
        f"{prefix}_workflow_status",
        ProductionWorkStatus.NOT_STARTED,
    )

    if (
        workflow_status
        not in ProductionWorkStatus.values
    ):
        workflow_status = (
            ProductionWorkStatus.NOT_STARTED
        )

    obj.workflow_status = workflow_status


    responsible_id = request.POST.get(
        f"{prefix}_responsible",
        "",
    ).strip()

    obj.responsible = (
        allowed_responsibles.get(
            int(responsible_id)
        )
        if responsible_id.isdigit()
        else None
    )


    reviewer_id = request.POST.get(
        f"{prefix}_reviewer",
        "",
    ).strip()

    obj.reviewer = (
        allowed_responsibles.get(
            int(reviewer_id)
        )
        if reviewer_id.isdigit()
        else None
    )


    obj.created = (
        request.POST.get(
            f"{prefix}_created"
        )
        == "1"
    )


    obj.notes = request.POST.get(
        f"{prefix}_notes",
        "",
    ).strip()


    obj.updated_by = request.user

    obj.save()

@role_required("developer")
def web_production_sheet(request, project_pk):
    project = get_object_or_404(Project.objects.select_related("client", "purchased_plan__plan"), pk=project_pk)
    if not can_access_project(request.user, project):
        raise PermissionDenied("Este proyecto no está asignado a Desarrollo.")

    sheet, created = WebProductionSheet.objects.get_or_create(
        project=project,
        defaults={"updated_by": request.user, "main_page_target": 8},
    )
    if created:
        ensure_web_production_structure(
            sheet=sheet,
            main_page_target=8,
            county_target=0,
            services_per_county_target=0,
            cities_per_county_target=0,
            user=request.user,
        )
    _ensure_internal_sections(
        sheet,
        request.user,
    )
    questionnaire, service_catalog, seo_strategy = _technical_production_inputs(project)
    structure_form = WebProductionStructureForm(initial={
        "main_page_target": sheet.main_page_target,
        "county_target": sheet.county_target,
        "services_per_county_target": sheet.services_per_county_target,
        "cities_per_county_target": sheet.cities_per_county_target,
    })

    if request.method == "POST":
        action = request.POST.get(
            "action",
            "",
        ).strip()

        users = {
            u.pk: u
            for u in _developer_users()
        }

        if action == "save_page":
            row_id = request.POST.get(
                "row_id",
                "",
            ).strip()

            page = get_object_or_404(
                WebProductionPage,
                pk=row_id,
                sheet=sheet,
            )

            _update_seo_row(
                page,
                request,
                f"p_{page.pk}",
                users,
            )

            sheet.updated_by = request.user
            sheet.save(
                update_fields=[
                    "updated_by",
                    "updated_at",
                ]
            )

            log_activity(
                request.user,
                "development",
                "production_page_save",
                page,
                description=page.name,
            )

            messages.success(
                request,
                f"{page.name} guardada correctamente.",
            )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        elif action == "save_county":
            row_id = request.POST.get(
                "row_id",
                "",
            ).strip()

            county = get_object_or_404(
                WebProductionCounty,
                pk=row_id,
                sheet=sheet,
            )

            _update_seo_row(
                county,
                request,
                f"c_{county.pk}",
                users,
            )

            sheet.updated_by = request.user
            sheet.save(
                update_fields=[
                    "updated_by",
                    "updated_at",
                ]
            )

            log_activity(
                request.user,
                "development",
                "production_county_save",
                county,
                description=county.name,
            )

            messages.success(
                request,
                f"{county.name} guardado correctamente.",
            )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        elif action == "save_service":
            row_id = request.POST.get(
                "row_id",
                "",
            ).strip()

            service = get_object_or_404(
                WebProductionCountyService,
                pk=row_id,
                county__sheet=sheet,
            )

            _update_seo_row(
                service,
                request,
                f"s_{service.pk}",
                users,
            )

            sheet.updated_by = request.user
            sheet.save(
                update_fields=[
                    "updated_by",
                    "updated_at",
                ]
            )

            log_activity(
                request.user,
                "development",
                "production_service_save",
                service,
                description=service.name,
            )

            messages.success(
                request,
                f"{service.name} guardado correctamente.",
            )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        elif action == "save_city":
            row_id = request.POST.get(
                "row_id",
                "",
            ).strip()

            city = get_object_or_404(
                WebProductionCity,
                pk=row_id,
                sheet=sheet,
            )

            _update_seo_row(
                city,
                request,
                f"city_{city.pk}",
                users,
            )

            sheet.updated_by = request.user
            sheet.save(
                update_fields=[
                    "updated_by",
                    "updated_at",
                ]
            )

            log_activity(
                request.user,
                "development",
                "production_city_save",
                city,
                description=city.name,
            )

            messages.success(
                request,
                f"{city.name} guardada correctamente.",
            )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        elif action == "save_internal_section":
            row_id = request.POST.get(
                "row_id",
                "",
            ).strip()

            section = get_object_or_404(
                WebProductionInternalSection,
                pk=row_id,
                sheet=sheet,
            )

            _update_internal_section(
                section,
                request,
                f"internal_{section.pk}",
                users,
            )

            sheet.updated_by = request.user
            sheet.save(
                update_fields=[
                    "updated_by",
                    "updated_at",
                ]
            )

            log_activity(
                request.user,
                "development",
                "production_internal_section_save",
                section,
                description=section.name,
            )

            messages.success(
                request,
                f"{section.name} guardada correctamente.",
            )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        elif action == "generate_structure":
            structure_form = WebProductionStructureForm(
                request.POST
            )

            if structure_form.is_valid():
                ensure_web_production_structure(
                    sheet=sheet,
                    user=request.user,
                    **structure_form.cleaned_data,
                )

                messages.success(
                    request,
                    "Estructura completada sin borrar información existente.",
                )

                return redirect(
                    "operations:web_production_sheet",
                    project_pk=project.pk,
                )

        elif action == "add_page":
            order = (
                sheet.pages
                .order_by("-order")
                .values_list(
                    "order",
                    flat=True,
                )
                .first()
                or 0
            ) + 1

            obj = WebProductionPage(
                sheet=sheet,
                page_type=WebProductionPage.PageType.EXTRA,
                name=f"Página extra {order}",
                order=order,
                updated_by=request.user,
            )

            apply_seo_automation(obj)
            obj.save()

            log_activity(
                request.user,
                "development",
                "production_page_add",
                sheet,
            )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        elif action == "add_county":
            order = (
                sheet.counties
                .order_by("-order")
                .values_list(
                    "order",
                    flat=True,
                )
                .first()
                or 0
            ) + 1

            county = WebProductionCounty(
                sheet=sheet,
                name=f"Condado {order}",
                order=order,
                updated_by=request.user,
            )

            apply_seo_automation(county)
            county.save()

            for index in range(
                sheet.services_per_county_target
            ):
                service = WebProductionCountyService(
                    county=county,
                    name=(
                        f"Servicio {index + 1} · "
                        f"{county.name}"
                    ),
                    order=index + 1,
                    updated_by=request.user,
                )

                apply_seo_automation(service)
                service.save()

            for index in range(
                sheet.cities_per_county_target
            ):
                city = WebProductionCity(
                    sheet=sheet,
                    county=county,
                    name=f"Ciudad {index + 1}",
                    order=index + 1,
                    updated_by=request.user,
                )

                apply_seo_automation(city)
                city.save()

            log_activity(
                request.user,
                "development",
                "production_county_add",
                sheet,
            )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        elif action == "add_service":
            county = get_object_or_404(
                WebProductionCounty,
                pk=request.POST.get("county_id"),
                sheet=sheet,
            )

            order = (
                county.services
                .order_by("-order")
                .values_list(
                    "order",
                    flat=True,
                )
                .first()
                or 0
            ) + 1

            service = WebProductionCountyService(
                county=county,
                name=(
                    f"Servicio {order} · "
                    f"{county.name}"
                ),
                order=order,
                updated_by=request.user,
            )

            apply_seo_automation(service)
            service.save()

            log_activity(
                request.user,
                "development",
                "production_service_add",
                sheet,
                description=county.name,
            )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        elif action == "add_city":
            order = (
                sheet.cities
                .order_by("-order")
                .values_list(
                    "order",
                    flat=True,
                )
                .first()
                or 0
            ) + 1

            county_id = request.POST.get(
                "county_id",
                "",
            ).strip()

            county = (
                WebProductionCounty.objects
                .filter(
                    pk=county_id,
                    sheet=sheet,
                )
                .first()
                if county_id.isdigit()
                else None
            )

            if county:
                order = (
                    county.cities
                    .order_by("-order")
                    .values_list(
                        "order",
                        flat=True,
                    )
                    .first()
                    or 0
                ) + 1

            city = WebProductionCity(
                sheet=sheet,
                county=county,
                name=f"Ciudad {order}",
                order=order,
                updated_by=request.user,
            )

            apply_seo_automation(city)
            city.save()

            log_activity(
                request.user,
                "development",
                "production_city_add",
                sheet,
            )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        elif action == "apply_global_service":
            selected = request.POST.get(
                "global_service_name",
                "",
            ).strip()

            if not selected:
                messages.warning(
                    request,
                    "Selecciona un servicio para aplicarlo globalmente.",
                )

            else:
                created_count = 0

                for county in sheet.counties.all():
                    exists = county.services.filter(
                        service_name__iexact=selected
                    ).exists()

                    if exists:
                        continue

                    order = (
                        county.services
                        .order_by("-order")
                        .values_list(
                            "order",
                            flat=True,
                        )
                        .first()
                        or 0
                    ) + 1

                    obj = WebProductionCountyService(
                        county=county,
                        service_name=selected,
                        name=(
                            f"{selected} "
                            f"{county.name}"
                        ).strip(),
                        is_global=True,
                        order=order,
                        updated_by=request.user,
                    )

                    apply_seo_automation(obj)
                    obj.save()

                    created_count += 1

                log_activity(
                    request.user,
                    "development",
                    "production_global_service",
                    sheet,
                    description=selected,
                )

                messages.success(
                    request,
                    (
                        f"{selected}: creado en "
                        f"{created_count} condados "
                        "que no lo tenían."
                    ),
                )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        elif action in {
            "delete_page",
            "delete_county",
            "delete_service",
            "delete_city",
        }:
            row_id = request.POST.get(
                "row_id"
            )

            if action == "delete_page":
                obj = get_object_or_404(
                    WebProductionPage,
                    pk=row_id,
                    sheet=sheet,
                )
                label = obj.name

            elif action == "delete_county":
                obj = get_object_or_404(
                    WebProductionCounty,
                    pk=row_id,
                    sheet=sheet,
                )
                label = obj.name

            elif action == "delete_service":
                obj = get_object_or_404(
                    WebProductionCountyService,
                    pk=row_id,
                    county__sheet=sheet,
                )
                label = obj.name

            else:
                obj = get_object_or_404(
                    WebProductionCity,
                    pk=row_id,
                    sheet=sheet,
                )
                label = obj.name

            obj.delete()

            log_activity(
                request.user,
                "development",
                action,
                sheet,
                description=label,
            )

            messages.success(
                request,
                "Elemento eliminado.",
            )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        elif action == "save_general":
            sheet.header_structure = (
                request.POST.get(
                    "header_structure",
                    "",
                ).strip()
            )

            sheet.notes = (
                request.POST.get(
                    "sheet_notes",
                    "",
                ).strip()
            )

            sheet.updated_by = request.user

            sheet.save(
                update_fields=[
                    "header_structure",
                    "notes",
                    "updated_by",
                    "updated_at",
                ]
            )

            log_activity(
                request.user,
                "development",
                "production_general_save",
                sheet,
            )

            messages.success(
                request,
                "Configuración general guardada.",
            )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

    pages = list(
        sheet.pages.select_related(
            "responsible",
            "reviewer",
            "updated_by",
        )
    )
    counties = list(
    sheet.counties
    .select_related(
        "responsible",
        "reviewer",
        "updated_by",
    )
    .prefetch_related(
        "services__responsible",
        "services__reviewer",
        "services__updated_by",
        "cities__responsible",
        "cities__reviewer",
        "cities__updated_by",
    )
)
    cities = list(
        sheet.cities.select_related(
            "county",
            "responsible",
            "reviewer",
            "updated_by",
        )
    )

    internal_sections = list(
        sheet.internal_sections.select_related(
            "responsible",
            "reviewer",
            "updated_by",
        )
    )

    unassigned_cities = [
        city for city in cities
        if not city.county_id
    ]


    developers = list(_developer_users())

    all_rows = (
    pages
    + counties
    + [
        service
        for county in counties
        for service in county.services.all()
    ]
    + cities
)

    production_rows = (
        all_rows
        + internal_sections
    )

    total_rows = len(all_rows)

    completed_rows = sum(
        1
        for row in all_rows
        if row.state == CompleteStatus.COMPLETE
    )

    reviewed_rows = sum(
        1
        for row in all_rows
        if row.review_status == CompleteStatus.COMPLETE
    )

    completed_percent = (
        round((completed_rows / total_rows) * 100)
        if total_rows
        else 0
    )

    reviewed_percent = (
        round((reviewed_rows / total_rows) * 100)
        if total_rows
        else 0
    )


    total_production_items = len(
        production_rows
    )

    completed_items = sum(
        1
        for row in production_rows
        if (
            row.workflow_status
            == ProductionWorkStatus.COMPLETE
        )
    )

    review_items = sum(
        1
        for row in production_rows
        if (
            row.workflow_status
            == ProductionWorkStatus.IN_REVIEW
        )
    )

    progress_items = sum(
        1
        for row in production_rows
        if (
            row.workflow_status
            == ProductionWorkStatus.IN_PROGRESS
        )
    )

    pending_items = sum(
        1
        for row in production_rows
        if (
            row.workflow_status
            == ProductionWorkStatus.NOT_STARTED
        )
    )

    production_percent = (
        round(
            (
                completed_items
                / total_production_items
            )
            * 100
        )
        if total_production_items
        else 0
    )
    balance = defaultdict(lambda: {"points": 0, "items": 0})
    unassigned_points = 0
    for row in production_rows:
        if row.responsible:
            key = row.responsible.display_name
            balance[key]["points"] += row.points or 0
            balance[key]["items"] += 1
        else:
            unassigned_points += row.points or 0
    balance_rows = [{"name": name, **data} for name, data in sorted(balance.items())]

    strategy_label = {
        "study": "Estudio SEO: elegir servicios por tendencia/oportunidad",
        "client_services": "Servicios del cliente: pueden aplicarse globalmente a todos los condados",
    }.get(seo_strategy, "Sin estrategia definida en la ficha técnica")

    return render(request, "operations/development_production.html", {
        "project": project,
        "sheet": sheet,
        "structure_form": structure_form,

        "pages": pages,
        "counties": counties,
        "cities": cities,
        "internal_sections": internal_sections,

        "unassigned_cities": unassigned_cities,

        "developers": developers,

        "service_catalog": service_catalog,
        "seo_strategy": seo_strategy,
        "strategy_label": strategy_label,

        "total_rows": total_rows,
        "completed_rows": completed_rows,
        "reviewed_rows": reviewed_rows,

        "completed_percent": completed_percent,
        "reviewed_percent": reviewed_percent,

        "production_statuses": ProductionWorkStatus.choices,

        "total_production_items": total_production_items,
        "completed_items": completed_items,
        "review_items": review_items,
        "progress_items": progress_items,
        "pending_items": pending_items,
        "production_percent": production_percent,

        "balance_rows": balance_rows,
        "unassigned_points": unassigned_points,

        "questionnaire": questionnaire,
    })


def _production_row_for(
    sheet,
    row_type,
    row_id,
):
    mapping = {
        "page": (
            WebProductionPage,
            {"sheet": sheet},
        ),
        "county": (
            WebProductionCounty,
            {"sheet": sheet},
        ),
        "service": (
            WebProductionCountyService,
            {"county__sheet": sheet},
        ),
        "city": (
            WebProductionCity,
            {"sheet": sheet},
        ),
        "internal_section": (
            WebProductionInternalSection,
            {"sheet": sheet},
        ),
    }

    model_info = mapping.get(
        row_type
    )

    if not model_info:
        return None

    model, scope = model_info

    return model.objects.filter(
        pk=row_id,
        **scope,
    ).first()



@role_required("developer")
@require_POST
def web_production_quick_toggle(
    request,
    project_pk,
):
    project = get_object_or_404(
        Project,
        pk=project_pk,
    )

    if not can_access_project(
        request.user,
        project,
    ):
        raise PermissionDenied(
            "Este proyecto no está asignado a Desarrollo."
        )

    sheet = get_object_or_404(
        WebProductionSheet,
        project=project,
    )

    row_type = request.POST.get(
        "row_type",
        "",
    )

    row_id = request.POST.get(
        "row_id",
        "",
    )

    field = request.POST.get(
        "field",
        "",
    )

    value = request.POST.get(
        "value",
        "",
    )

    if not str(row_id).isdigit():
        messages.error(
            request,
            "Cambio rápido inválido.",
        )
        return redirect(
            "operations:web_production_sheet",
            project_pk=project.pk,
        )

    obj = _production_row_for(
        sheet,
        row_type,
        int(row_id),
    )

    if not obj:
        messages.error(
            request,
            "No se encontró la fila de producción.",
        )
        return redirect(
            "operations:web_production_sheet",
            project_pk=project.pk,
        )

    if field == "workflow_status":

        if not hasattr(
            obj,
            "workflow_status",
        ):
            messages.error(
                request,
                "Este elemento no admite estado de producción.",
            )
            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        if (
            value
            not in ProductionWorkStatus.values
        ):
            messages.error(
                request,
                "Estado de producción inválido.",
            )
            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        obj.workflow_status = value

    elif field == "state":

        if not hasattr(
            obj,
            "state",
        ):
            messages.error(
                request,
                "Este elemento no admite estado legacy.",
            )
            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        if value not in CompleteStatus.values:
            messages.error(
                request,
                "Estado inválido.",
            )
            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        if (
            value
            == CompleteStatus.COMPLETE
        ):
            obj.workflow_status = (
                ProductionWorkStatus.COMPLETE
            )
        else:
            obj.workflow_status = (
                ProductionWorkStatus.NOT_STARTED
            )

    elif field == "review_status":

        if not hasattr(
            obj,
            "review_status",
        ):
            messages.error(
                request,
                "Este elemento no admite revisión.",
            )
            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        if value not in CompleteStatus.values:
            messages.error(
                request,
                "Estado de revisión inválido.",
            )
            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        obj.review_status = value

    else:
        messages.error(
            request,
            "Cambio rápido inválido.",
        )
        return redirect(
            "operations:web_production_sheet",
            project_pk=project.pk,
        )

    obj.updated_by = request.user
    obj.save()

    sheet.updated_by = request.user
    sheet.save(
        update_fields=[
            "updated_by",
            "updated_at",
        ]
    )

    log_activity(
        request.user,
        "development",
        "production_quick_toggle",
        obj,
        description=f"{field}: {value}",
    )

    return redirect(
        "operations:web_production_sheet",
        project_pk=project.pk,
    )
