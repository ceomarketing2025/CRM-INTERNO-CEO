from textwrap import dedent

from apps.design.models import ColorPalette
from apps.operations.models import DEFAULT_TYPOGRAPHY_CONFIG, WebProductionSheet


SOCIAL_LABELS = {
    "facebook": "Facebook",
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "youtube": "YouTube",
    "twitter": "X / Twitter",
    "yelp": "Yelp",
    "linkedin": "LinkedIn",
    "nextdoor": "Nextdoor",
}


DEVELOPMENT_RULES = dedent(
    """
    REGLAS DE DESARROLLO Y SEO

    Utiliza toda la información de este documento como única fuente oficial del proyecto.

    No inventes datos, URLs, servicios, ciudades, condados, beneficios, certificaciones, experiencia, garantías, teléfonos, correos, horarios, ubicaciones ni información comercial que no haya sido confirmada.

    SEO Y CONTENIDO
    - El H1 principal del hero debe contener únicamente la keyword principal correspondiente a la página, en Title Case.
    - Debe existir un solo H1 principal por página.
    - No agregues nombre de empresa, slogans, ciudades adicionales, beneficios ni frases promocionales dentro del H1.
    - Utiliza la keyword principal de forma natural y las keywords secundarias como variaciones semánticas.
    - No hagas keyword stuffing.
    - La keyword principal nunca debe colocarse en negrita.
    - No modifiques la keyword principal.
    - No redactes la keyword como si fuera el nombre de la empresa ni como sujeto artificial de una oración.
    - No copies contenido entre ciudades, condados, servicios o páginas cambiando únicamente la ubicación.
    - Cada nueva página debe tener contenido nuevo, específico y relacionado con su intención de búsqueda.
    - El contenido debe escribirse para el cliente final, con intención comercial y de conversión.
    - No utilizar frases como “confirmed counties”, “confirmed cities”, “confirmed services” o equivalentes.
    - No inventar años de experiencia, certificaciones, garantías, disponibilidad 24/7, licencias, seguros, premios, testimonios, calificaciones o estadísticas.
    - Evita lenguaje genérico de IA y frases corporativas vacías.
    - No iniciar continuamente los textos con las mismas palabras.
    - Los H2 deben ser claros y evitar extensiones innecesarias.
    - Los párrafos de encabezado de sección deben ser breves y naturales.
    - El contenido de cada página debe mantener coherencia con su slug, keyword principal, keywords secundarias, Meta Title y Meta Description.
    - Meta Title y Meta Description se utilizan como guía de intención y no deben reemplazarse salvo instrucción expresa.

    REGLAS DE CÓDIGO
    Cuando se entregue HTML, CSS o JavaScript:
    - Mantener todos los IDs.
    - Mantener todas las clases.
    - Mantener todos los estilos.
    - Mantener todos los scripts.
    - Mantener formularios, campos, nombres y validaciones.
    - Mantener la estructura visual original.
    - No agregar librerías nuevas.
    - No reordenar elementos salvo instrucción expresa.
    - No eliminar contenido estructural.
    - No agregar o eliminar botones salvo instrucción expresa.
    - No cambiar el texto visible de los botones salvo autorización.
    - No cambiar enlaces correctos.
    - No inventar redirecciones.
    - No dejar placeholders.
    - Entregar siempre el código completo.
    - No responder “el resto permanece igual”.
    - Eliminar comentarios innecesarios del código cuando corresponda.

    IMÁGENES Y ALT
    - Revisar los atributos alt de las imágenes existentes.
    - Al menos una imagen relevante de la página debe utilizar naturalmente la keyword principal en su alt.
    - No repetir exactamente el mismo alt en todas las imágenes.
    - Las imágenes decorativas pueden conservar alt vacío.
    - No inventar detalles visuales que no puedan verificarse.
    - No cambiar src salvo que se haya proporcionado expresamente una imagen oficial para sustituirla.
    - Este documento no incluye banco de imágenes ni links de imágenes.

    REDIRECCIONES
    - Call Now debe utilizar el teléfono oficial.
    - Botones de estimado o cotización deben utilizar el formulario o destino oficial definido.
    - View Services debe dirigir a la página oficial de servicios.
    - Areas We Service debe dirigir a la página oficial de cobertura.
    - Ciudades, Counties y servicios deben utilizar únicamente URLs registradas en la estructura del proyecto.
    - No inventar slugs ni URLs.

    CONTROL ANTES DE ENTREGAR
    - H1 correcto y único.
    - SEO correspondiente a la URL.
    - Información oficial correcta.
    - Teléfono y enlaces tel correctos.
    - Email y enlaces mailto correctos.
    - Redirecciones correctas.
    - Contenido nuevo y sin duplicaciones.
    - Sin datos inventados.
    - Código completo.
    - Estructura original conservada.
    """
).strip()


def _clean(value):
    return str(value or "").strip()


def _bullet_lines(values, empty="Pendiente por confirmar."):
    values = [_clean(value) for value in values if _clean(value)]
    if not values:
        return empty
    return "\n".join(f"- {value}" for value in values)


def _primary_service(data):
    items = data.get("main_services", {}).get("json", {}).get("items", []) or []
    for item in items:
        if item.get("primary") and not item.get("excluded") and _clean(item.get("name")):
            return _clean(item.get("name"))
    for item in items:
        if not item.get("excluded") and _clean(item.get("name")):
            return _clean(item.get("name"))
    return "Pendiente por confirmar con el cliente."


def _services(data):
    items = data.get("main_services", {}).get("json", {}).get("items", []) or []
    return [
        _clean(item.get("name"))
        for item in items
        if _clean(item.get("name")) and not item.get("excluded")
    ]


def _areas(data):
    items = data.get("service_areas", {}).get("json", {}).get("items", []) or []
    labels = {"state": "Estado", "county": "County", "city": "Ciudad"}
    result = []
    for item in items:
        name = _clean(item.get("name"))
        if not name:
            continue
        result.append((item.get("type") or "city", name, f"{labels.get(item.get('type'), 'Área')}: {name}"))
    return result


def _primary_phone(data, client):
    numbers = data.get("contact_numbers", {}).get("json", {}).get("numbers", []) or []
    for item in numbers:
        if item.get("primary") and _clean(item.get("number")):
            return _clean(item.get("number"))
    for item in numbers:
        if _clean(item.get("number")):
            return _clean(item.get("number"))
    return _clean(getattr(client, "phone", "")) or "Por favor, ayúdenos confirmando el número de contacto principal."


def _mission_vision(data):
    info = data.get("has_mission_vision", {}).get("json", {}) or {}
    if info.get("has") == "yes":
        return (
            _clean(info.get("mission")) or "Pendiente por confirmar con el cliente.",
            _clean(info.get("vision")) or "Pendiente por confirmar con el cliente.",
        )
    if info.get("has") == "no":
        return (
            "Pendiente de redacción y confirmación con el cliente según la lógica del negocio recopilada.",
            "Pendiente de redacción y confirmación con el cliente según la lógica del negocio recopilada.",
        )
    return (
        "Pendiente por confirmar con el cliente.",
        "Pendiente por confirmar con el cliente.",
    )


def _social_lines(data):
    info = data.get("has_social", {}).get("json", {}) or {}
    if info.get("has") == "no":
        return "No registra redes sociales."

    lines = []
    for key, url in (info.get("networks") or {}).items():
        url = _clean(url)
        if url:
            lines.append(f"{SOCIAL_LABELS.get(key, key.title())}: {url}")
    for item in info.get("custom", []) or []:
        name = _clean(item.get("name")) or "Otra red"
        url = _clean(item.get("url"))
        if url:
            lines.append(f"{name}: {url}")
    return "\n".join(lines) or "Por favor, comparta los enlaces oficiales de las redes sociales que desea incluir."


def _certifications(data):
    info = data.get("certifications", {}).get("json", {}) or {}
    if info.get("has") == "no":
        return "No"
    if info.get("has") == "yes":
        return _clean(info.get("detail")) or "Pendiente por detallar."
    return "Por favor, confirme si la empresa cuenta con certificaciones."


def _free_estimates(data):
    value = _clean(data.get("quotes", {}).get("json", {}).get("free_estimates"))
    mapping = {
        "yes": "Sí",
        "no": "No",
        "si": "Sí",
        "sí": "Sí",
    }
    return mapping.get(value.lower(), value or "Pendiente por confirmar con el cliente.")


def _slogan_block(data):
    info = data.get("slogan", {}).get("json", {}) or {}
    mode = info.get("mode")
    text = _clean(info.get("text"))
    if mode == "none":
        return ""
    if text:
        return f"\n*Slogan:*\n{text}\n"
    if mode in {"existing", "create"}:
        return "\n*Slogan:*\nPendiente por confirmar con el cliente.\n"
    return ""


def build_client_message(project, data):
    client = project.client
    mission, vision = _mission_vision(data)
    services = _services(data)
    areas = _areas(data)
    coverage = _clean(data.get("coverage", {}).get("json", {}).get("miles"))
    hours = _clean(data.get("business_hours", {}).get("text"))
    experience = _clean(data.get("experience_years", {}).get("text"))

    if areas:
        areas_text = _bullet_lines([item[2] for item in areas])
        main_area = areas[0][1]
    else:
        areas_text = (
            "Por favor, ayúdenos compartiendo una lista de los estados, counties y/o ciudades "
            "donde actualmente ofrecen sus servicios."
        )
        main_area = "Pendiente por confirmar con el cliente."

    return dedent(
        f"""
        Buen día estimado cliente, un placer saludarle.

        Por favor su gentil ayuda revisando la información en base a la lógica del negocio y completando los campos que faltan.
        Agradezco de antemano el tiempo invertido en el proceso.

        *Misión*
        {mission}

        *Visión*
        {vision}

        *Servicios:*

        Main Service:
        {_primary_service(data)}

        Lista de servicios:
        {_bullet_lines(services, "Por favor, ayúdenos confirmando la lista completa de servicios que desea promocionar.")}

        *Áreas de Servicio:*
        {areas_text}

        Área principal:
        {main_area}

        Millas:
        {(coverage + " millas") if coverage else "Por favor, ayúdenos confirmando el radio de cobertura en millas."}

        *¿Estimados gratuitos?*
        {_free_estimates(data)}
        {_slogan_block(data)}
        *Horario:*
        {hours or "Por favor, ayúdenos confirmando el horario de atención."}

        *Teléfono:*
        {_primary_phone(data, client)}

        *Dirección Principal:*
        {_clean(client.address) or "Por favor, ayúdenos confirmando la dirección principal de la empresa."}

        *Email:*
        {_clean(client.email) or "Por favor, ayúdenos confirmando el correo electrónico principal."}

        *Años de experiencia:*
        {(experience + " años") if experience else "Por favor, indíquenos cuántos años de experiencia tiene la empresa."}

        *Certificaciones:*
        {_certifications(data)}

        *Redes Sociales:*
        {_social_lines(data)}

        Por favor indíquenos si toda la información es correcta o envíenos las modificaciones o datos pendientes correspondientes.

        Muchas gracias por su colaboración.
        """
    ).strip()


def _production_structure(sheet):
    if not sheet:
        return "La estructura del sitio todavía no ha sido configurada en Ficha de Producción."

    lines = []
    pages = list(sheet.pages.all().order_by("order", "id"))
    if pages:
        lines.append("PÁGINAS PRINCIPALES")
        for page in pages:
            lines.append(f"├── {_clean(page.name) or 'Página sin nombre'}")

    counties = list(sheet.counties.all().prefetch_related("services", "cities").order_by("order", "id"))
    if counties:
        if lines:
            lines.append("")
        lines.append("ÁREAS / COUNTIES")
        for county in counties:
            county_name = _clean(county.name) or "County sin nombre"
            lines.append(county_name)
            children = []
            for service in county.services.all().order_by("order", "id"):
                name = _clean(service.name) or _clean(service.service_name)
                if name:
                    children.append(("Servicio", name))
            for city in county.cities.all().order_by("order", "id"):
                name = _clean(city.name)
                if name:
                    children.append(("Ciudad", name))
            for index, (kind, name) in enumerate(children):
                branch = "└──" if index == len(children) - 1 else "├──"
                lines.append(f"{branch} {kind}: {name}")

    unassigned = list(sheet.cities.filter(county__isnull=True).order_by("order", "id"))
    if unassigned:
        if lines:
            lines.append("")
        lines.append("CIUDADES SIN COUNTY ASIGNADO")
        for city in unassigned:
            lines.append(f"├── {_clean(city.name) or 'Ciudad sin nombre'}")

    return "\n".join(lines) if lines else "La estructura del sitio todavía no tiene páginas, counties o ciudades configuradas."


def build_structure_for_client(project, sheet):
    return dedent(
        f"""
        Buen día estimado cliente.

        A continuación le presentamos la estructura o arquitectura propuesta para su sitio web, organizada en función de los servicios y áreas definidos para el proyecto.

        {_production_structure(sheet)}

        Esta estructura nos permitirá organizar el sitio de forma clara para que cada servicio y cada zona importante tenga el espacio correspondiente dentro de la página web.

        Por favor revise la estructura y confírmenos si está correcta o si desea realizar algún ajuste antes de continuar con el desarrollo.
        """
    ).strip()


def _seo_rows(sheet):
    if not sheet:
        return "Sin planificación SEO en Ficha de Producción."

    rows = []

    def add(kind, obj, parent=""):
        label = _clean(getattr(obj, "name", "")) or _clean(getattr(obj, "service_name", "")) or "Sin nombre"
        if parent:
            label = f"{parent} > {label}"
        rows.extend([
            f"[{kind}] {label}",
            f"Keyword principal: {_clean(getattr(obj, 'keyword', '')) or 'Pendiente'}",
            f"Slug: {_clean(getattr(obj, 'slug', '')) or 'Pendiente'}",
            f"Meta Title: {_clean(getattr(obj, 'meta_title', '')) or 'Pendiente'}",
            f"Meta Description: {_clean(getattr(obj, 'meta_description', '')) or 'Pendiente'}",
            f"Keywords secundarias: {_clean(getattr(obj, 'secondary_keywords', '')) or 'Pendiente'}",
            "",
        ])

    for page in sheet.pages.all().order_by("order", "id"):
        add("Página", page)
    for county in sheet.counties.all().prefetch_related("services").order_by("order", "id"):
        add("County", county)
        for service in county.services.all().order_by("order", "id"):
            add("Servicio por County", service, _clean(county.name))
    for city in sheet.cities.all().select_related("county").order_by("order", "id"):
        parent = _clean(city.county.name) if city.county else ""
        add("Ciudad", city, parent)

    return "\n".join(rows).strip() or "Sin URLs SEO configuradas."


def _typography_text(sheet):
    source = (sheet.typography_config if sheet else {}) or {}
    lines = []
    labels = {
        "h1": "H1",
        "h2": "H2",
        "h3": "H3",
        "h4": "H4",
        "h5": "H5",
        "paragraph": "Párrafo",
        "kicker": "Kicker",
    }
    for key, default in DEFAULT_TYPOGRAPHY_CONFIG.items():
        config = dict(default)
        if isinstance(source.get(key), dict):
            config.update(source[key])
        extra = f" · Letter spacing {config.get('letter_spacing')}" if config.get("letter_spacing") else ""
        lines.append(
            f"{labels.get(key, key)}: {config.get('font')} · {config.get('size')}px · {config.get('weight')} · line-height {config.get('line_height')}{extra}"
        )
    return "\n".join(lines)


def _palette_text(project):
    palette = (
        ColorPalette.objects.filter(project=project, is_primary=True).prefetch_related("colors").first()
        or ColorPalette.objects.filter(project=project).prefetch_related("colors").first()
    )
    if not palette:
        return "Paleta pendiente por configurar."
    lines = [f"Paleta: {palette.name}"]
    for color in palette.colors.all().order_by("order", "id"):
        label = _clean(color.label) or color.get_role_display()
        lines.append(f"- {label}: {color.hex_code}")
    return "\n".join(lines)


def build_development_start(project, data, sheet):
    client = project.client
    mission, vision = _mission_vision(data)
    services = _services(data)
    areas = _areas(data)
    business_description = _clean(data.get("company_description", {}).get("text"))
    business_logic = data.get("business_logic", {}).get("json", {}) or {}
    customer_type = _clean(business_logic.get("customer_type"))
    visitor_action = _clean(business_logic.get("visitor_action"))

    return dedent(
        f"""
        INICIO DEL DESARROLLO

        INFORMACIÓN DEL NEGOCIO

        Empresa:
        {_clean(client.business_name)}

        Descripción / lógica del negocio:
        {business_description or 'Pendiente por completar.'}
        Tipo de cliente: {customer_type or 'Pendiente'}
        Acción principal esperada del visitante: {visitor_action or 'Pendiente'}

        Misión:
        {mission}

        Visión:
        {vision}

        Servicio principal:
        {_primary_service(data)}

        Servicios:
        {_bullet_lines(services)}

        Áreas de servicio:
        {_bullet_lines([item[2] for item in areas], 'Pendiente por definir.')}

        Cobertura:
        {_clean(data.get('coverage', {}).get('text')) or 'Pendiente por definir.'}

        Horario:
        {_clean(data.get('business_hours', {}).get('text')) or 'Pendiente por definir.'}

        Free Estimates:
        {_free_estimates(data)}

        Teléfono:
        {_primary_phone(data, client)}

        Email:
        {_clean(client.email) or 'Pendiente por definir.'}

        Dirección:
        {_clean(client.address) or 'Pendiente por definir.'}

        Experiencia:
        {(_clean(data.get('experience_years', {}).get('text')) + ' años') if _clean(data.get('experience_years', {}).get('text')) else 'Pendiente por definir.'}

        Certificaciones:
        {_certifications(data)}

        Redes sociales:
        {_social_lines(data)}

        ESTRUCTURA DEL SITIO

        {_production_structure(sheet)}

        PLANIFICACIÓN SEO

        {_seo_rows(sheet)}

        ESTILOS DEL PROYECTO

        TIPOGRAFÍA
        {_typography_text(sheet)}

        PALETA DE COLORES
        {_palette_text(project)}

        BOTONES
        {_clean(sheet.button_style_code) if sheet and _clean(sheet.button_style_code) else 'Código de botones pendiente por configurar.'}

        ESTRUCTURA DEL HEADER
        {_clean(sheet.header_structure) if sheet and _clean(sheet.header_structure) else 'Header pendiente por configurar.'}

        {DEVELOPMENT_RULES}
        """
    ).strip()


def build_development_outputs(project, questionnaire):
    from .services import website_answer_payload

    data = website_answer_payload(questionnaire) if questionnaire else {}
    sheet = (
        WebProductionSheet.objects
        .filter(project=project)
        .prefetch_related("pages", "counties__services", "counties__cities", "cities__county")
        .first()
    )

    return {
        "client_message": build_client_message(project, data),
        "client_structure": build_structure_for_client(project, sheet),
        "development_start": build_development_start(project, data, sheet),
    }
