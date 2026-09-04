def _clean(value):
    if value is None:
        return ""
    return str(value).strip()


def build_project_summary(project):
    client = project.client
    plan = project.purchased_plan.plan if project.purchased_plan else None
    brief = getattr(project, "design_brief", None)
    marketing = getattr(project, "marketing_workspace", None)
    social_tracking = getattr(client, "social_media_tracking", None)
    palettes = list(project.color_palettes.prefetch_related("colors", "gradients").all())

    questionnaire_rows = []
    for questionnaire in project.questionnaires.select_related("template").prefetch_related("template__sections__questions", "answers"):
        answer_by_question = {a.question_id: a for a in questionnaire.answers.all()}
        sections = []
        for section in questionnaire.template.sections.all():
            rows = []
            for question in section.questions.all():
                answer = answer_by_question.get(question.id)
                if not answer:
                    continue
                value = ", ".join(answer.value_json.get("values", [])) if answer.value_json and answer.value_json.get("values") else answer.value_text
                if not _clean(value) and answer.state == "pending":
                    continue
                rows.append({"question": question.text, "key": question.key, "state": answer.get_state_display(), "state_code": answer.state, "value": _clean(value)})
            if rows:
                sections.append({"title": section.title, "rows": rows})
        questionnaire_rows.append({"name": questionnaire.template.name, "status": questionnaire.get_status_display(), "sections": sections})

    design_lines = []
    if brief:
        fields = [
            ("Datos generales", brief.general_location), ("Business", brief.business_notes), ("Redes", brief.social_notes),
            ("Encargados", brief.meeting_attendees), ("Logo", brief.get_logo_status_display()), ("Cambios de logo", brief.logo_change_notes),
            ("Formato logo", brief.get_logo_format_display()), ("Estructura visual", brief.get_visual_structure_display()),
            ("Detalle visual", brief.visual_structure_notes), ("Estilo", brief.get_style_direction_display()),
            ("Base de color", brief.color_base_notes), ("Fondo", brief.get_background_style_display()),
            ("Imágenes", brief.get_photo_availability_display()), ("Stock", brief.get_stock_usage_display()),
            ("Servicios", brief.services), ("Tipografía", brief.typography_direction), ("Layout", brief.layout_preferences),
            ("Referencias", brief.visual_references), ("Evitar", brief.elements_to_avoid),
        ]
        design_lines = [(label, _clean(value)) for label, value in fields if _clean(value)]

    palette_lines = []
    for palette in palettes:
        colors = [f"{c.get_role_display()}: {c.hex_code}" for c in palette.colors.all()]
        palette_lines.append({"name": palette.name, "colors": colors, "primary": palette.is_primary})

    marketing_lines = []
    marketing_checks = []
    marketing_documents = []
    if marketing:
        fields = [
            ("Datos reunión", marketing.meeting_summary), ("Dueño", marketing.owner_name), ("Nombre legal", marketing.legal_business_name),
            ("Fecha fundación", marketing.founding_date), ("Redes", marketing.social_links), ("Descripción", marketing.company_description),
            ("Horario", marketing.business_hours), ("Servicios", marketing.services), ("Áreas", marketing.service_areas),
            ("Gmail", marketing.gmail_email), ("Google Business", marketing.get_business_profile_status_display()),
            ("Link Google Business", marketing.business_profile_link), ("Link reviews", marketing.review_link),
            ("Mensaje reviews", marketing.review_message), ("Documentos", marketing.get_documents_available_display()),
            ("Verificación Google Ads", marketing.get_google_ads_verification_display()),
            ("Verificación LSA", marketing.get_google_lsa_verification_display()),
            ("Google Guarantee", marketing.get_google_guarantee_launched_display()),
        ]
        marketing_lines = [(label, _clean(value)) for label, value in fields if _clean(value)]
        marketing_checks = list(marketing.checklist_items.all())
        marketing_documents = list(marketing.documents.all())

    production_rows = list(project.production_records.select_related("collaborator").all())
    web_production = getattr(project, "web_production_sheet", None)
    web_pages = list(web_production.pages.select_related("responsible").all()) if web_production else []
    web_counties = list(web_production.counties.select_related("responsible").prefetch_related("services__responsible").all()) if web_production else []
    web_cities = list(web_production.cities.select_related("county", "responsible").all()) if web_production else []
    credential_rows = list(project.credential_purchases.all())
    campaign_rows = list(project.ad_campaigns.select_related("assigned_to").all())
    social_plan_rows = list(project.social_media_plans.select_related("assigned_to").all())
    reminders = list(project.reminders.filter(status="pending").select_related("assigned_to")[:20])
    links = list(project.resource_links.all())
    images = list(project.image_references.all())

    copy_lines = [
        "RESUMEN SINCRONIZADO DEL PROYECTO", "",
        "ADMINISTRACIÓN",
        f"Cliente: {client.full_name or '—'}", f"Empresa: {client.business_name}", f"Teléfono: {client.phone or '—'}",
        f"Correo: {client.email or '—'}", f"ID: {client.identity_document or '—'}",
        f"Plan: {plan.name if plan else '—'}", f"Proyecto: {project.name} ({project.project_code})",
        f"Estado general: {project.get_status_display()}", f"Fecha inicio: {project.start_date or '—'}",
    ]
    if design_lines:
        copy_lines.extend(["", "DISEÑO / ASESORÍA VISUAL"])
        copy_lines.extend([f"{label}: {value}" for label, value in design_lines])
    if palette_lines:
        copy_lines.extend(["", "PALETA DE COLOR"])
        for palette in palette_lines:
            copy_lines.append(f"{palette['name']}: " + " | ".join(palette["colors"]))
    if marketing_lines:
        copy_lines.extend(["", "MARKETING"])
        copy_lines.extend([f"{label}: {value}" for label, value in marketing_lines])
    if marketing_checks:
        copy_lines.extend(["", "CHECKLIST MARKETING"])
        for item in marketing_checks:
            detail = f" · {item.detail}" if item.detail else ""
            copy_lines.append(f"- [{item.get_status_display()}] {item.get_area_display()}: {item.label}{detail}")
    for questionnaire in questionnaire_rows:
        copy_lines.extend(["", "DESARROLLO · " + questionnaire["name"].upper()])
        for section in questionnaire["sections"]:
            copy_lines.append(section["title"])
            for row in section["rows"]:
                detail = row["value"] or row["state"]
                copy_lines.append(f"- {row['question']}: {detail}")
    if production_rows:
        copy_lines.extend(["", "CONTROL ADMINISTRATIVO DE PRODUCCIÓN"])
        for row in production_rows:
            copy_lines.append(f"- {row.project_site}: {row.get_status_display()} · Diseño {row.get_design_status_display()} · Tec {row.get_tech_status_display()} · Colaborador {row.collaborator.display_name if row.collaborator else '—'} · Web {row.website_url or '—'}")
    if web_production:
        copy_lines.extend(["", "DESARROLLO · FICHA DE PRODUCCIÓN WEB"])
        copy_lines.append(f"Objetivo: {web_production.main_page_target} páginas principales · {web_production.county_target} condados · {web_production.services_per_county_target} servicios por condado")
        if web_production.header_structure:
            copy_lines.append(f"Header: {web_production.header_structure}")
        for row in web_pages:
            copy_lines.append(f"- Página | {row.name or '—'} | slug: {row.slug or '—'} | keyword: {row.keyword or '—'} | responsable: {row.responsible.display_name if row.responsible else '—'} | lista: {'Sí' if row.state == 'complete' else 'No'} | revisión: {'Sí' if row.review_status == 'complete' else 'No'}")
        for county in web_counties:
            copy_lines.append(f"- Condado | {county.name or '—'} | slug: {county.slug or '—'} | keyword: {county.keyword or '—'} | responsable: {county.responsible.display_name if county.responsible else '—'} | lista: {'Sí' if county.state == 'complete' else 'No'} | revisión: {'Sí' if county.review_status == 'complete' else 'No'}")
            for service in county.services.all():
                copy_lines.append(f"  - Servicio | {service.name or '—'} | base: {service.service_name or '—'} | slug: {service.slug or '—'} | keyword: {service.keyword or '—'} | responsable: {service.responsible.display_name if service.responsible else '—'} | lista: {'Sí' if service.state == 'complete' else 'No'} | revisión: {'Sí' if service.review_status == 'complete' else 'No'}")
        for city in web_cities:
            copy_lines.append(f"- Ciudad | {city.name or '—'} | condado: {city.county.name if city.county else '—'} | slug: {city.slug or '—'} | keyword: {city.keyword or '—'} | responsable: {city.responsible.display_name if city.responsible else '—'} | lista: {'Sí' if city.state == 'complete' else 'No'} | revisión: {'Sí' if city.review_status == 'complete' else 'No'}")
    if credential_rows:
        copy_lines.extend(["", "CREDENCIALES / RENOVACIONES"])
        for row in credential_rows:
            copy_lines.append(f"- {row.credential_name} · {row.get_provider_display()} · renovación {row.renewal_date or '—'}")
    if campaign_rows:
        copy_lines.extend(["", "CAMPAÑAS"])
        for row in campaign_rows:
            copy_lines.append(f"- {row.get_platform_display()} · {row.name} · {row.get_status_display()} · {row.start_date or '—'} a {row.end_date or '—'}")
    if social_tracking:
        copy_lines.extend(["", "SEGUIMIENTO SOCIAL / GOOGLE", f"Reviews: {social_tracking.get_reviews_display()}", f"Productos: {social_tracking.get_products_display()}", f"GB: {social_tracking.get_google_business_display()}", f"Redes: {social_tracking.get_networks_display()}", f"LSA: {social_tracking.get_lsa_display()}", f"Ads verificado: {social_tracking.get_ads_verified_display()}", f"Seguimiento Google: {social_tracking.get_google_followup_display()}"])
    if links:
        copy_lines.extend(["", "LINKS / RESPALDOS"])
        for item in links:
            copy_lines.append(f"- {item.get_kind_display()} · {item.label}: {item.url}")
    if marketing_documents:
        copy_lines.extend(["", "DOCUMENTOS MARKETING"])
        for item in marketing_documents:
            ref = item.drive_url or (item.file.url if item.file else "")
            copy_lines.append(f"- {item.title}: {ref or 'registrado'}")
    if images:
        copy_lines.extend(["", "IMÁGENES POR CATEGORÍA"])
        for item in images:
            copy_lines.append(f"- {item.category}: {item.image_url}")
    if reminders:
        copy_lines.extend(["", "RECORDATORIOS PENDIENTES"])
        for item in reminders:
            copy_lines.append(f"- {item.due_at:%Y-%m-%d}: {item.title}")

    pending = []
    for questionnaire in questionnaire_rows:
        for section in questionnaire["sections"]:
            for row in section["rows"]:
                if row["state_code"] == "pending":
                    pending.append(row["question"])
    for item in marketing_checks:
        if item.status == "incomplete":
            pending.append(item.label)
    if web_production:
        for row in web_pages:
            if row.state == "incomplete":
                pending.append(f"Producción · {row.name or 'Página sin nombre'}")
        for county in web_counties:
            if county.state == "incomplete":
                pending.append(f"Producción · {county.name or 'Condado sin nombre'}")
            for service in county.services.all():
                if service.state == "incomplete":
                    pending.append(f"Producción · {county.name or 'Condado'} / {service.name or 'Servicio'}")
        for city in web_cities:
            if city.state == "incomplete":
                pending.append(f"Producción · {city.name or 'Ciudad sin nombre'}")

    return {
        "client": client, "plan": plan, "brief": brief, "design_lines": design_lines,
        "palette_lines": palette_lines, "questionnaire_rows": questionnaire_rows,
        "marketing": marketing, "marketing_lines": marketing_lines, "marketing_checks": marketing_checks,
        "marketing_documents": marketing_documents, "production_rows": production_rows, "web_production": web_production,
        "web_pages": web_pages, "web_counties": web_counties, "web_cities": web_cities, "credential_rows": credential_rows,
        "campaign_rows": campaign_rows, "social_plan_rows": social_plan_rows, "social_tracking": social_tracking,
        "reminders": reminders, "links": links, "images": images, "pending": pending, "copy_text": "\n".join(copy_lines),
    }
