from io import BytesIO
from textwrap import wrap
from django.utils import timezone
from reportlab.lib.colors import HexColor, black, white, Color
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

DEFAULT_RULES = [
    "Establecer tamaño de márgenes y mantener consistencia entre secciones.",
    "Estandarizar el tamaño de imágenes por sección.",
    "Utilizar imágenes de alta calidad considerando el peso y la velocidad de carga.",
    "Mantener tipografía legible y jerarquías claras.",
    "Si una imagen o video es muy claro, usar texto oscuro o una caja de contraste.",
    "Negro y blanco pueden usarse como neutros cuando la paleta no lo prohíba.",
]


def complete_design_brief(*, brief, user):
    brief.completed = True
    brief.completed_at = timezone.now()
    brief.completed_by = user
    brief.save(update_fields=["completed", "completed_at", "completed_by", "updated_at"])
    project = brief.project
    # V3: Diseño no cambia el estado ni bloquea a otras áreas.
    # La ficha de Desarrollo se deja preparada por conveniencia, pero puede completarse antes o después.
    from apps.questionnaires.models import ProjectQuestionnaire, QuestionnaireTemplate
    template = QuestionnaireTemplate.objects.filter(code="website-technical-v2", is_active=True).first()
    if template and project.project_type == "website":
        ProjectQuestionnaire.objects.get_or_create(
            project=project,
            template=template,
            defaults={"created_by": user, "status": "draft"},
        )
    return project


def _hex_to_color(value, fallback="#FFFFFF"):
    try:
        return HexColor(value or fallback)
    except Exception:
        return HexColor(fallback)


def _contrast(hex_value):
    value = (hex_value or "#FFFFFF").lstrip("#")
    try:
        r, g, b = [int(value[i:i+2], 16) for i in (0, 2, 4)]
    except Exception:
        return black
    luminance = (0.299*r + 0.587*g + 0.114*b)
    return black if luminance > 165 else white


def _draw_wrapped(c, text, x, y, width_chars=92, leading=13, font="Helvetica", size=9, bullet=False):
    c.setFont(font, size)
    lines = []
    for paragraph in (text or "").splitlines() or [""]:
        lines.extend(wrap(paragraph, width=width_chars) or [""])
    for line in lines:
        prefix = "• " if bullet else ""
        c.drawString(x, y, prefix + line)
        y -= leading
    return y


def build_palette_pdf(project, palette):
    """Genera el PDF en memoria. Nunca lo guarda en FileField ni en disco."""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 38

    client = project.client
    brief = getattr(project, "design_brief", None)
    colors = list(palette.colors.all())
    by_role = {item.role: item for item in colors}
    ordered_roles = ["text", "background", "primary", "secondary", "accent"]
    role_defaults = {
        "text": ("Texto", "#000000"),
        "background": ("Fondo", "#FFFFFF"),
        "primary": ("Primario", "#1F4F8F"),
        "secondary": ("Secundario", "#C9CBD1"),
        "accent": ("Acento", "#2571B7"),
    }

    c.setTitle(f"Asesoría Visual - {client.business_name}")
    c.setFont("Helvetica", 20)
    c.drawCentredString(width/2, height-44, "Asesoría Visual")
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width/2, height-70, client.business_name.upper())
    c.setFont("Helvetica", 8)
    c.setFillColor(HexColor("#6B7280"))
    c.drawCentredString(width/2, height-84, f"Cliente: {client.full_name or '—'} · Proyecto: {project.project_code}")
    c.setFillColor(black)

    y = height - 120
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "PALETA DE COLOR")
    y -= 22

    gap = 6
    box_w = (width - 2*margin - gap*4) / 5
    box_h = 88
    for idx, role in enumerate(ordered_roles):
        item = by_role.get(role)
        default_label, default_hex = role_defaults[role]
        hex_value = item.hex_code if item else default_hex
        label = item.label if item and item.label else default_label
        x = margin + idx * (box_w + gap)
        c.setFillColor(_hex_to_color(hex_value))
        c.rect(x, y-box_h, box_w, box_h, fill=1, stroke=1)
        c.setFillColor(_contrast(hex_value))
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(x + box_w/2, y-box_h/2+8, hex_value.lstrip("#").lower())
        c.drawCentredString(x + box_w/2, y-box_h/2-8, label)
    c.setFillColor(black)
    y -= box_h + 18

    usage_text = [
        "Color Primario (60%): domina el diseño, llamados a la acción y secciones principales.",
        "Color Secundario (30%): complemento, botones y tarjetas de información menos importantes.",
        "Color de Acento (10%): elementos clave, resultados, hipervínculos y detalles.",
        "Colores Neutros: blancos, grises o negros para fondos y textos.",
    ]
    for line in usage_text:
        y = _draw_wrapped(c, line, margin+4, y, width_chars=100, leading=12, size=8.5)
    y -= 8

    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "DEGRADADOS")
    y -= 16
    gradients = list(palette.gradients.all())[:3]
    if not gradients:
        primary = by_role.get("primary")
        secondary = by_role.get("secondary")
        accent = by_role.get("accent")
        bg = by_role.get("background")
        p = primary.hex_code if primary else role_defaults["primary"][1]
        s = secondary.hex_code if secondary else role_defaults["secondary"][1]
        a = accent.hex_code if accent else role_defaults["accent"][1]
        b = bg.hex_code if bg else role_defaults["background"][1]
        gradients = [
            type("G", (), {"name":"PRIMERO", "start_hex":a, "end_hex":p})(),
            type("G", (), {"name":"SEGUNDO", "start_hex":s, "end_hex":a})(),
            type("G", (), {"name":"TERCERO", "start_hex":b, "end_hex":p})(),
        ]
    grad_x = margin + 16
    grad_w = width - 2*margin - 32
    grad_h = 31
    for grad in gradients:
        start = _hex_to_color(grad.start_hex)
        end = _hex_to_color(grad.end_hex)
        steps = 48
        strip_w = grad_w / steps
        for i in range(steps):
            t = i / max(steps - 1, 1)
            mixed = Color(
                start.red + (end.red - start.red) * t,
                start.green + (end.green - start.green) * t,
                start.blue + (end.blue - start.blue) * t,
            )
            c.setFillColor(mixed)
            c.rect(grad_x + i*strip_w, y-grad_h, strip_w+0.3, grad_h, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(grad_x+grad_w/2, y-grad_h/2-4, grad.name.upper())
        y -= grad_h + 2
    c.setFillColor(black)
    y -= 12

    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "REGLAS GENERALES")
    y -= 15
    rules = [line.strip(" •-	") for line in (palette.general_rules or "").splitlines() if line.strip()] or DEFAULT_RULES
    for rule in rules:
        y = _draw_wrapped(c, rule, margin+6, y, width_chars=105, leading=11, size=8, bullet=True)

    # Logo opcional: se guarda la imagen fuente si Diseño la carga, pero nunca se guarda el PDF generado.
    if brief and brief.logo_file:
        try:
            img = ImageReader(brief.logo_file.path)
            max_w, max_h = 150, 95
            iw, ih = img.getSize()
            scale = min(max_w / iw, max_h / ih)
            dw, dh = iw * scale, ih * scale
            c.drawImage(img, (width-dw)/2, max(24, y-dh-6), width=dw, height=dh, mask='auto', preserveAspectRatio=True)
        except Exception:
            pass

    # Página 2: respaldo del brief visual, solo si existe.
    if brief:
        c.showPage()
        c.setFont("Helvetica-Bold", 17)
        c.drawString(margin, height-48, "Datos de asesoría visual")
        c.setFont("Helvetica", 9)
        y = height - 76
        rows = [
            ("Empresa", client.business_name),
            ("Cliente", client.full_name),
            ("Datos generales", brief.general_location),
            ("Business", brief.business_notes),
            ("Redes", brief.social_notes),
            ("Encargados", brief.meeting_attendees),
            ("Logo", brief.get_logo_status_display()),
            ("Cambios de logo", brief.logo_change_notes),
            ("Formato de logo", brief.get_logo_format_display()),
            ("Estructura visual", brief.get_visual_structure_display()),
            ("Detalle visual", brief.visual_structure_notes),
            ("Dirección de estilo", brief.get_style_direction_display()),
            ("Base de color", brief.color_base_notes),
            ("Fondo", brief.get_background_style_display()),
            ("Imágenes", brief.get_photo_availability_display()),
            ("Uso de stock", brief.get_stock_usage_display()),
            ("Servicios", brief.services),
            ("Tipografía", brief.typography_direction),
            ("Referencias", brief.visual_references),
            ("Evitar", brief.elements_to_avoid),
        ]
        for label, value in rows:
            if not value:
                continue
            c.setFont("Helvetica-Bold", 8.5)
            c.drawString(margin, y, f"{label}:")
            c.setFont("Helvetica", 8.5)
            y = _draw_wrapped(c, str(value), margin+105, y, width_chars=72, leading=11, size=8.5)
            y -= 3
            if y < 55:
                c.showPage(); y = height - 48

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def ensure_current_social_media_cycle(client_plan, today=None):
    """Crea/sincroniza el ciclo vigente y sus entregables del plan Social Media."""
    from django.db import transaction
    from django.utils import timezone

    from apps.plans.models.choices import ServiceType
    from apps.plans.services import current_cycle_bounds
    from .models import SocialMediaContentItem, SocialMediaCycle

    today = today or timezone.localdate()
    if not client_plan.is_active or client_plan.plan.service_type != ServiceType.SOCIAL_MEDIA:
        return None

    start, due = current_cycle_bounds(client_plan.start_date or today, client_plan.renewal_frequency, today=today)

    with transaction.atomic():
        cycle, _ = SocialMediaCycle.objects.get_or_create(
            client_plan=client_plan,
            period_start=start,
            defaults={"due_date": due},
        )
        if cycle.due_date != due:
            cycle.due_date = due
            cycle.save(update_fields=["due_date", "updated_at"])

        if client_plan.renewal_date != due:
            client_plan.renewal_date = due
            client_plan.save(update_fields=["renewal_date", "updated_at"])

        _sync_social_items(
            cycle,
            SocialMediaContentItem.ContentType.POST,
            client_plan.plan.weekly_posts,
        )
        _sync_social_items(
            cycle,
            SocialMediaContentItem.ContentType.VIDEO,
            client_plan.plan.weekly_videos,
        )

    return cycle


def _sync_social_items(cycle, content_type, target):
    from .models import SocialMediaContentItem

    target = max(int(target or 0), 0)
    existing = {item.sequence: item for item in cycle.items.filter(content_type=content_type)}

    for sequence in range(1, target + 1):
        if sequence not in existing:
            SocialMediaContentItem.objects.create(
                cycle=cycle,
                content_type=content_type,
                sequence=sequence,
            )

    # Si baja la cantidad del plan, solo se eliminan entregables todavía vacíos.
    for sequence, item in existing.items():
        if sequence <= target:
            continue
        if item.ready or item.published_networks or item.notes:
            continue
        item.delete()


# ---------------------------------------------------------------------------
# Tareas operativas de Diseño V2: auto-creación + ciclos recurrentes.
# ---------------------------------------------------------------------------

def ensure_default_design_tasks_for_project(project, user=None):
    """Crea una actividad base por cada producto de Diseño contratado.

    Es idempotente: si el producto ya tiene una o más tareas, no agrega otra.
    Social Media nace como contenido recurrente *sin configurar* para que Diseño
    defina si se controlará semanal, quincenal o mensualmente.
    """
    from apps.design.models import DesignTask
    from apps.plans.models.choices import PlanDepartment, ServiceType

    assignments = project.contracted_plans.select_related("plan").filter(
        is_active=True,
        plan__department=PlanDepartment.DESIGN,
    )
    created = []
    actor = user if getattr(user, "is_authenticated", False) else None
    for assignment in assignments:
        is_social = assignment.plan.service_type == ServiceType.SOCIAL_MEDIA
        if is_social:
            # Un servicio Social Media siempre necesita al menos un control de
            # publicaciones, incluso si el equipo ya creó otras tareas manuales.
            if assignment.design_tasks.filter(task_type=DesignTask.TaskType.CONTENT).exists():
                continue
        elif assignment.design_tasks.exists():
            continue
        task = DesignTask.objects.create(
            project_plan=assignment,
            title="Publicaciones / contenido" if is_social else assignment.plan.name,
            description=(
                "Configura la frecuencia de publicación para comenzar el control por periodos."
                if is_social
                else f"Actividad creada automáticamente al contratar {assignment.plan.name}."
            ),
            status=DesignTask.Status.TODO,
            task_type=DesignTask.TaskType.CONTENT if is_social else DesignTask.TaskType.STANDARD,
            recurrence_frequency=DesignTask.Recurrence.NONE,
            recurrence_start_date=None,
            configuration_required=is_social,
            auto_generated=True,
            created_by=actor,
            updated_by=actor,
        )
        created.append(task)
    return created


def ensure_current_design_task_cycle(task, today=None):
    """Devuelve/crea el periodo vigente para una tarea recurrente configurada."""
    from datetime import timedelta
    from django.utils import timezone
    from apps.design.models import DesignTaskCycle
    from apps.plans.services import current_cycle_bounds

    today = today or timezone.localdate()
    if not task.is_recurring or task.needs_configuration:
        return None

    period_start, next_start = current_cycle_bounds(
        task.recurrence_start_date,
        task.recurrence_frequency,
        today=today,
    )
    if not next_start:
        return None
    period_end = next_start - timedelta(days=1)
    label = design_cycle_label(task.recurrence_frequency, period_start, period_end)
    cycle, _ = DesignTaskCycle.objects.get_or_create(
        task=task,
        period_start=period_start,
        defaults={"period_end": period_end, "label": label},
    )
    changed = []
    if cycle.period_end != period_end:
        cycle.period_end = period_end
        changed.append("period_end")
    if cycle.label != label:
        cycle.label = label
        changed.append("label")
    if changed:
        cycle.save(update_fields=changed + ["updated_at"])
    return cycle


def design_cycle_label(frequency, start, end):
    months = [
        "", "Ene", "Feb", "Mar", "Abr", "May", "Jun",
        "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",
    ]
    if frequency == "weekly":
        prefix = "Semana"
    elif frequency == "biweekly":
        prefix = "Quincena"
    else:
        return f"{months[start.month]} {start.year} · {start.day:02d}/{start.month:02d}–{end.day:02d}/{end.month:02d}"
    return f"{prefix} · {start.day:02d}/{start.month:02d}–{end.day:02d}/{end.month:02d}"


def design_task_progress(task, today=None):
    """Estado normalizado 0–100 usado por Diseño y Auditoría General."""
    if task.task_type == task.TaskType.CONTENT:
        if task.needs_configuration:
            return {
                "progress": 0,
                "state": "red",
                "label": "Configurar renovación",
                "cycle": None,
                "needs_configuration": True,
            }
        cycle = ensure_current_design_task_cycle(task, today=today)
        if not cycle:
            return {
                "progress": 0,
                "state": "red",
                "label": "Sin periodo activo",
                "cycle": None,
                "needs_configuration": False,
            }
        return {
            "progress": cycle.progress_percent,
            "state": cycle.state_code,
            "label": cycle.state_label,
            "cycle": cycle,
            "needs_configuration": False,
        }

    progress = task.standard_progress_percent
    if progress >= 100:
        state = "green"
    elif progress >= 50:
        state = "yellow"
    else:
        state = "red"
    return {
        "progress": progress,
        "state": state,
        "label": task.get_status_display(),
        "cycle": None,
        "needs_configuration": False,
    }
