def _clean(value):
    if value is None:
        return ""
    return str(value).strip()


def build_project_summary(project):
    client = project.client
    plan = project.purchased_plan.plan if project.purchased_plan else None
    brief = getattr(project, "design_brief", None)
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
                if answer.value_json and answer.value_json.get("values"):
                    value = ", ".join(answer.value_json.get("values", []))
                else:
                    value = answer.value_text
                if not _clean(value) and answer.state == "pending":
                    continue
                rows.append({
                    "question": question.text,
                    "key": question.key,
                    "state": answer.get_state_display(),
                    "state_code": answer.state,
                    "value": _clean(value),
                })
            if rows:
                sections.append({"title": section.title, "rows": rows})
        questionnaire_rows.append({"name": questionnaire.template.name, "status": questionnaire.get_status_display(), "sections": sections})

    design_lines = []
    if brief:
        fields = [
            ("Datos generales", brief.general_location),
            ("Business", brief.business_notes),
            ("Redes", brief.social_notes),
            ("Encargados", brief.meeting_attendees),
            ("Logo", brief.get_logo_status_display()),
            ("Cambios de logo", brief.logo_change_notes),
            ("Formato logo", brief.get_logo_format_display()),
            ("Estructura visual", brief.get_visual_structure_display()),
            ("Detalle visual", brief.visual_structure_notes),
            ("Estilo", brief.get_style_direction_display()),
            ("Base de color", brief.color_base_notes),
            ("Fondo", brief.get_background_style_display()),
            ("Imágenes", brief.get_photo_availability_display()),
            ("Stock", brief.get_stock_usage_display()),
            ("Servicios", brief.services),
            ("Tipografía", brief.typography_direction),
            ("Layout", brief.layout_preferences),
            ("Referencias", brief.visual_references),
            ("Evitar", brief.elements_to_avoid),
        ]
        design_lines = [(label, _clean(value)) for label, value in fields if _clean(value)]

    palette_lines = []
    for palette in palettes:
        colors = [f"{c.get_role_display()}: {c.hex_code}" for c in palette.colors.all()]
        palette_lines.append({"name": palette.name, "colors": colors, "primary": palette.is_primary})

    links = list(project.resource_links.all())
    images = list(project.image_references.all())

    copy_lines = [
        "RESUMEN DE INFORMACIÓN DEL PROYECTO",
        "",
        f"Cliente: {client.full_name or '—'}",
        f"Empresa: {client.business_name}",
        f"Teléfono: {client.phone or '—'}",
        f"ID: {client.identity_document or '—'}",
        f"Plan: {plan.name if plan else '—'}",
        f"Precio del plan: ${project.purchased_plan.agreed_price:,.2f}" if project.purchased_plan else "Precio del plan: —",
        f"Proyecto: {project.name} ({project.project_code})",
        f"Estado: {project.get_status_display()}",
    ]
    if design_lines:
        copy_lines.extend(["", "DISEÑO / ASESORÍA VISUAL"])
        copy_lines.extend([f"{label}: {value}" for label, value in design_lines])
    if palette_lines:
        copy_lines.extend(["", "PALETA DE COLOR"])
        for palette in palette_lines:
            copy_lines.append(f"{palette['name']}: " + " | ".join(palette["colors"]))
    for questionnaire in questionnaire_rows:
        copy_lines.extend(["", questionnaire["name"].upper()])
        for section in questionnaire["sections"]:
            copy_lines.append(section["title"])
            for row in section["rows"]:
                detail = row["value"] or row["state"]
                copy_lines.append(f"- {row['question']}: {detail}")
    if links:
        copy_lines.extend(["", "LINKS / RESPALDOS"])
        for item in links:
            copy_lines.append(f"- {item.get_kind_display()} · {item.label}: {item.url}")
    if images:
        copy_lines.extend(["", "IMÁGENES POR CATEGORÍA"])
        for item in images:
            copy_lines.append(f"- {item.category}: {item.image_url}")

    pending = []
    for questionnaire in questionnaire_rows:
        for section in questionnaire["sections"]:
            for row in section["rows"]:
                if row["state_code"] == "pending":
                    pending.append(row["question"])

    return {
        "client": client,
        "plan": plan,
        "brief": brief,
        "design_lines": design_lines,
        "palette_lines": palette_lines,
        "questionnaire_rows": questionnaire_rows,
        "links": links,
        "images": images,
        "pending": pending,
        "copy_text": "\n".join(copy_lines),
    }
