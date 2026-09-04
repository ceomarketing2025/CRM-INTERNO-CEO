from decimal import Decimal
from django.core.management.base import BaseCommand
from apps.finance.models import FinanceCategory
from apps.plans.models import ServicePlan
from apps.questionnaires.models import Question, QuestionnaireSection, QuestionnaireTemplate


class Command(BaseCommand):
    help = "Carga catálogos y plantillas V3 de forma idempotente."

    def handle(self, *args, **options):
        self.seed_finance_categories()
        self.seed_plans()
        self.backfill_project_plans()
        self.seed_website_questionnaire()
        self.seed_software_questionnaire()
        self.stdout.write(self.style.SUCCESS("Datos base V3 verificados."))

    def seed_finance_categories(self):
        categories = [
            ("credential_purchase", "Compra de credenciales", "Compra de accesos, cuentas o recursos operativos."),
            ("domain_purchase", "Compra de dominios", "Registro inicial de dominios."),
            ("domain_renewal", "Renovación de dominios", "Renovaciones anuales o extraordinarias."),
            ("salaries", "Pago de sueldos", "Sueldos y pagos al equipo."),
            ("website_costs", "Costo de páginas web", "Costos asociados a producción de páginas web."),
            ("social_media_plans", "Planes Social Media", "Costos y movimientos de planes de social media."),
            ("software_costs", "Costos de software", "Costos directos de proyectos de software."),
            ("hosting_servers", "Hosting / servidores", "Hosting, VPS, nubes y servidores."),
            ("tools_subscriptions", "Herramientas / suscripciones", "Licencias y herramientas recurrentes."),
            ("client_income", "Ingresos de clientes", "Cobros e ingresos relacionados a clientes y planes."),
            ("other", "Otros", "Movimientos no clasificados."),
        ]
        for code, name, description in categories:
            FinanceCategory.objects.update_or_create(code=code, defaults={"name": name, "description": description, "is_active": True})

    def seed_plans(self):
        """Carga el catálogo comercial vigente sin pisar ediciones hechas en el CRM.

        La fuente vigente es la hoja "Hoja de Producción CEO Marketing" recibida
        el 04/09/2026. Los planes de referencia cargados por error en la versión
        anterior se retiran del catálogo; si alguno ya fue usado por un proyecto
        se conserva únicamente como registro histórico inactivo.
        """
        obsolete_reference_codes = [
            "ref-live-studio-redes-1", "ref-live-studio-standard", "ref-live-studio-redes-3",
            "ref-live-studio-tiktok-1", "ref-agency360-gestion-redes", "ref-since-mercurio",
            "ref-since-jupiter", "ref-since-urano", "ref-interweb-landing",
            "ref-interweb-corporativa-pymes", "ref-interweb-ecommerce", "ref-vayolet-landing",
            "ref-vayolet-corporativa", "ref-vayolet-ecommerce", "ref-nmtech-landing",
            "ref-nmtech-corporativa", "ref-nmtech-ecommerce", "ref-agency360-landing",
            "ref-eaweb-seo", "ref-mgweb-seo", "ref-pablo-ronquillo-seo", "ref-since-seo",
            "ref-apo-ads-single", "ref-apo-meta-google", "ref-since-ads",
        ]
        for plan in ServicePlan.objects.filter(code__in=obsolete_reference_codes):
            if not plan.purchases.exists() and not plan.project_assignments.exists():
                plan.delete()
                continue
            rules = dict(plan.rules or {})
            rules["obsolete_wrong_seed"] = True
            rules["obsolete_reason"] = "Catálogo de referencia cargado desde el archivo equivocado."
            plan.rules = rules
            plan.is_active = False
            plan.save(update_fields=["rules", "is_active", "updated_at"])

        # Los placeholders antiguos de Web/Social ya tienen reemplazo comercial real.
        # Se retiran si nunca se usaron; si tienen historial, se ocultan sin romper FKs.
        retired_generic_codes = ["website-basic", "website-medium", "website-advanced", "social-media-custom"]
        for plan in ServicePlan.objects.filter(code__in=retired_generic_codes):
            if not plan.purchases.exists() and not plan.project_assignments.exists():
                plan.delete()
                continue
            rules = dict(plan.rules or {})
            rules["retired_catalog_seed"] = True
            rules["obsolete_reason"] = "Placeholder histórico reemplazado por el catálogo comercial vigente."
            plan.rules = rules
            plan.is_active = False
            plan.save(update_fields=["rules", "is_active", "updated_at"])

        plans = [
            # Software se mantiene como base porque la hoja comercial no trae un plan cerrado.
            dict(code="software-custom", name="Software Personalizado", department="developer", service_type="software", description="Base para cotizaciones y desarrollos de software a medida.", base_price=Decimal("0.00"), billing_cycle="one_time", rules={"legacy_generic": True}),

            # ===== SITIOS WEB / DESARROLLO =====
            dict(
                code="ceo-website-1-basica", name="Website 1 Básica", department="developer", service_type="website",
                base_price=Decimal("2400.00"), billing_cycle="one_time", website_pages=7, branding_pages=8,
                scope_range="7 secciones base + 8 branding pages",
                description="Web básica · 8 branding pages + SEO + indexación + Google Business + Google Guarantee / LSA. Estructura: Home, About, Services, Areas We Service, FAQ, Contact Us y Blog + SEO.",
                rules={"source":"Hoja de Producción CEO Marketing", "includes":["SEO", "Indexación Google", "Google Business", "Google Guarantee / LSA"], "core_sections":["Home","About","Services","Areas We Service","FAQ","Contact Us","Blog + SEO"]},
            ),
            dict(
                code="ceo-website-2-media", name="Website 2 Media", department="developer", service_type="website",
                base_price=Decimal("3200.00"), billing_cycle="one_time", website_pages=7, branding_pages=20,
                scope_range="7 secciones base + 20 branding pages",
                description="Web media · 20 branding pages + indexación + Google Business + Google Guarantee / LSA. Areas We Service se desarrolla por área cuando corresponda.",
                rules={"source":"Hoja de Producción CEO Marketing", "includes":["Indexación Google", "Google Business", "Google Guarantee / LSA"], "core_sections":["Home","About","Services","Areas We Service por área","FAQ","Contact Us","Blog + SEO"]},
            ),
            dict(
                code="ceo-website-3-avanzada", name="Website 3 Avanzada", department="developer", service_type="website",
                base_price=Decimal("42000.00"), billing_cycle="one_time", website_pages=7, branding_pages=40,
                scope_range="7 secciones base + 40 branding pages",
                description="Web avanzada · 40 branding pages + indexación + Google Business + Google Guarantee / LSA. Servicios y ciudades se trabajan en páginas separadas según alcance.",
                rules={"source":"Hoja de Producción CEO Marketing", "includes":["Indexación Google", "Google Business", "Google Guarantee / LSA"], "core_sections":["Home","About","Servicios por separado","Ciudades por separado","FAQ","Contact Us","Blog + SEO"]},
            ),
            dict(
                code="ceo-seo-indexacion-lsa", name="Plugin SEO + Indexación + Local Service Ads / Guarantee",
                department="developer", service_type="seo", base_price=Decimal("1200.00"), billing_cycle="one_time",
                scope_range="Configuración SEO + Google + LSA",
                description="SEO e indexación del website para posicionamiento, más creación/configuración de Google Business y Local Service Ads / Google Guarantee.",
                rules={"source":"Hoja de Producción CEO Marketing", "includes_marketing":True, "includes":["SEO", "Indexación Google", "Google Business", "Local Service Ads", "Google Guarantee"]},
            ),
            dict(
                code="ceo-analisis-web-google-tools", name="Análisis sitio web completo + Google Tools",
                department="developer", service_type="seo", base_price=Decimal("300.00"), billing_cycle="one_time",
                scope_range="Auditoría web + herramientas Google",
                description="Análisis completo del sitio web y revisión/configuración de herramientas de Google relacionadas.",
                rules={"source":"Hoja de Producción CEO Marketing", "includes_marketing":True},
            ),

            # ===== DISEÑO =====
            dict(
                code="ceo-social-media-basico", name="Social Media Básico", department="design", service_type="social_media",
                base_price=Decimal("250.00"), billing_cycle="monthly", weekly_posts=20, weekly_videos=0,
                description="Plan mensual. Google Business: 20 posts por ciclo. Incluye creación de banners y fotos de perfil.",
                rules={"source":"Hoja de Producción CEO Marketing", "networks":["google_business"], "deliverables":{"google_business_posts":20}, "includes":["Banners", "Fotos de perfil"]},
            ),
            dict(
                code="ceo-social-media-medio", name="Social Media Medio", department="design", service_type="social_media",
                base_price=Decimal("450.00"), billing_cycle="monthly", weekly_posts=32, weekly_videos=0,
                description="Plan mensual. Google Business: 20 posts + Facebook e Instagram: 12 posts. Incluye creación de banners y fotos de perfil.",
                rules={"source":"Hoja de Producción CEO Marketing", "networks":["google_business","facebook","instagram"], "deliverables":{"google_business_posts":20,"social_posts":12}, "includes":["Banners", "Fotos de perfil"]},
            ),
            dict(
                code="ceo-social-media-avanzado", name="Social Media Avanzado", department="design", service_type="social_media",
                base_price=Decimal("600.00"), billing_cycle="monthly", weekly_posts=32, weekly_videos=4,
                description="Plan mensual. Google Business: 20 posts + Facebook e Instagram: 12 posts + 4 videos. Incluye optimización de perfiles Business y LSA, análisis de rendimiento, banners y fotos de perfil.",
                rules={"source":"Hoja de Producción CEO Marketing", "networks":["google_business","facebook","instagram"], "deliverables":{"google_business_posts":20,"social_posts":12,"videos":4}, "includes":["Optimización Business", "Optimización LSA", "Análisis de rendimiento", "Banners", "Fotos de perfil"]},
            ),
            dict(code="ceo-diseno-logotipo", name="Diseño de Logotipo", department="design", service_type="branding", base_price=Decimal("300.00"), billing_cycle="one_time", description="Diseño de logotipo.", rules={"source":"Hoja de Producción CEO Marketing"}),
            dict(code="ceo-diseno-logotipo-manual", name="Diseño de Logotipo + Manual de Marca", department="design", service_type="branding", base_price=Decimal("450.00"), billing_cycle="one_time", description="Diseño de logotipo más manual de marca.", rules={"source":"Hoja de Producción CEO Marketing"}),
            dict(code="ceo-business-cards-diseno", name="Diseño de Business Cards", department="design", service_type="graphic_design", base_price=Decimal("100.00"), billing_cycle="one_time", description="Diseño de tarjetas de presentación.", rules={"source":"Hoja de Producción CEO Marketing"}),
            dict(code="ceo-1000-tarjetas", name="1000 Tarjetas", department="design", service_type="other_design", base_price=Decimal("150.00"), billing_cycle="one_time", description="Producción de 1000 tarjetas.", rules={"source":"Hoja de Producción CEO Marketing", "quantity":1000}),
            dict(code="ceo-business-cards-1000", name="Diseño de Business Cards + 1000 Tarjetas", department="design", service_type="graphic_design", base_price=Decimal("250.00"), billing_cycle="one_time", description="Diseño de Business Cards más producción de 1000 tarjetas.", rules={"source":"Hoja de Producción CEO Marketing", "quantity":1000}),
            dict(code="ceo-jackets", name="Jackets", department="design", service_type="jackets", base_price=Decimal("38.00"), billing_cycle="one_time", description="Precio por unidad.", rules={"source":"Hoja de Producción CEO Marketing", "unit":"unidad"}),
            dict(code="ceo-buzos-poliester", name="Buzos Poliéster", department="design", service_type="other_design", base_price=Decimal("21.00"), billing_cycle="one_time", description="Precio por unidad.", rules={"source":"Hoja de Producción CEO Marketing", "unit":"unidad"}),
            dict(code="ceo-buzos-polialgodon", name="Buzos Polialgodón", department="design", service_type="other_design", base_price=Decimal("19.00"), billing_cycle="one_time", description="Precio por unidad.", rules={"source":"Hoja de Producción CEO Marketing", "unit":"unidad"}),
            dict(code="ceo-camisetas-polo-vendedores", name="Camisetas Polo Vendedores", department="design", service_type="other_design", base_price=Decimal("25.00"), billing_cycle="one_time", description="Precio por unidad.", rules={"source":"Hoja de Producción CEO Marketing", "unit":"unidad"}),
            dict(code="ceo-diseno-yard-sign", name="Diseño de Yard Sign", department="design", service_type="graphic_design", base_price=Decimal("100.00"), billing_cycle="one_time", description="Diseño de yard sign.", rules={"source":"Hoja de Producción CEO Marketing"}),
            dict(code="ceo-logo-450", name="Logo", department="design", service_type="branding", base_price=Decimal("450.00"), billing_cycle="one_time", description="Producto Logo según la hoja comercial vigente.", rules={"source":"Hoja de Producción CEO Marketing"}),

            # ===== ADMINISTRACIÓN =====
            dict(code="ceo-transferencia-dominio", name="Transferencia de Dominio", department="administration", service_type="domain_host", base_price=Decimal("300.00"), billing_cycle="one_time", description="Servicio de transferencia de dominio.", rules={"source":"Hoja de Producción CEO Marketing"}),
            dict(code="ceo-host-dominio", name="Comprar Host y Dominio", department="administration", service_type="domain_host", base_price=Decimal("150.00"), billing_cycle="one_time", description="Compra/configuración inicial de hosting y dominio.", rules={"source":"Hoja de Producción CEO Marketing"}),

            # ===== MARKETING =====
            dict(code="ceo-google-business", name="Google My Business", department="marketing", service_type="google_business", base_price=Decimal("300.00"), billing_cycle="one_time", description="Creación/configuración de Google Business Profile.", rules={"source":"Hoja de Producción CEO Marketing"}),
            dict(code="ceo-google-guarantee", name="Google Guarantee", department="marketing", service_type="google_guarantee", base_price=Decimal("500.00"), billing_cycle="one_time", description="Configuración de Google Guarantee / Local Services Ads.", rules={"source":"Hoja de Producción CEO Marketing", "lsa":True}),
            dict(code="ceo-google-ads", name="Google Ads", department="marketing", service_type="google_ads", base_price=Decimal("500.00"), billing_cycle="one_time", description="Configuración/servicio de Google Ads según la hoja comercial vigente.", rules={"source":"Hoja de Producción CEO Marketing"}),
            dict(code="ceo-coaching-juan-alvaro", name="Coaching Juan Álvaro", department="marketing", service_type="other_marketing", base_price=Decimal("1000.00"), billing_cycle="one_time", description="Sesión personalizada por día.", rules={"source":"Hoja de Producción CEO Marketing", "unit":"sesión personalizada por día"}),
            dict(code="ceo-coaching-karla-samaniego", name="Coaching Karla Samaniego", department="marketing", service_type="other_marketing", base_price=Decimal("1000.00"), billing_cycle="one_time", description="Sesión personalizada por día.", rules={"source":"Hoja de Producción CEO Marketing", "unit":"sesión personalizada por día"}),
            dict(code="ceo-coaching-juan-karla", name="Coaching Juan Álvaro + Karla Samaniego", department="marketing", service_type="other_marketing", base_price=Decimal("1500.00"), billing_cycle="one_time", description="Sesión personalizada por día.", rules={"source":"Hoja de Producción CEO Marketing", "unit":"sesión personalizada por día"}),
        ]

        for item in plans:
            defaults = {**item, "currency": "USD", "is_active": True}
            code = defaults.pop("code")
            # get_or_create es intencional: una vez creado, el equipo puede editar
            # precio, nombre, alcance o facturación sin que un reinicio lo sobrescriba.
            ServicePlan.objects.get_or_create(code=code, defaults=defaults)

    def backfill_project_plans(self):
        """Conserva proyectos anteriores al nuevo esquema multi-plan."""
        from apps.projects.models import Project, ProjectPlanAssignment

        projects = Project.objects.select_related("purchased_plan__plan", "created_by").filter(
            purchased_plan__isnull=False
        )
        for project in projects:
            legacy = project.purchased_plan
            if not legacy or not legacy.plan_id:
                continue
            ProjectPlanAssignment.objects.update_or_create(
                project=project,
                plan=legacy.plan,
                defaults={
                    "subscription": legacy,
                    "agreed_price": legacy.agreed_price or legacy.plan.base_price,
                    "is_active": True,
                    "created_by": project.created_by,
                },
            )

    def upsert_template(self, code, name, project_type, description, sections):
        """Actualiza una plantilla sin romper respuestas existentes cuando una pregunta cambia de sección."""
        template, _ = QuestionnaireTemplate.objects.update_or_create(
            code=code,
            defaults={"name": name, "project_type": project_type, "description": description, "is_active": True},
        )
        valid_titles = []
        valid_question_ids = []
        for s_order, section_data in enumerate(sections, start=1):
            valid_titles.append(section_data["title"])
            section, _ = QuestionnaireSection.objects.update_or_create(
                template=template,
                title=section_data["title"],
                defaults={"description": section_data.get("description", ""), "order": s_order},
            )
            for q_order, q in enumerate(section_data["questions"], start=1):
                # La clave es estable entre versiones. Si la pregunta ya existía en otra sección,
                # la movemos en lugar de eliminarla para conservar sus respuestas relacionadas.
                question = (
                    Question.objects.filter(section__template=template, key=q["key"])
                    .order_by("id")
                    .first()
                )
                defaults = {
                    "section": section,
                    "text": q["text"],
                    "help_text": q.get("help", ""),
                    "question_type": q.get("type", "text"),
                    "required": q.get("required", False),
                    "options": q.get("options", []),
                    "order": q_order,
                }
                if question:
                    for field, value in defaults.items():
                        setattr(question, field, value)
                    question.save()
                else:
                    question = Question.objects.create(key=q["key"], **defaults)
                valid_question_ids.append(question.pk)

        Question.objects.filter(section__template=template).exclude(pk__in=valid_question_ids).delete()
        template.sections.exclude(title__in=valid_titles).delete()
        return template

    def seed_website_questionnaire(self):
        # V5: ficha técnica guiada. Los estados ya no se capturan manualmente:
        # cada bloque se considera listo en función de la información ingresada.
        sections = [
            {"title": "1) Información general", "questions": [
                {"key":"company_description", "text":"Breve descripción de la empresa / ¿A qué se dedica?", "type":"textarea", "required":True},
            ]},
            {"title": "2) Identidad, misión y visión", "questions": [
                {"key":"slogan", "text":"Slogan o frase corta", "type":"text"},
                {"key":"has_mission_vision", "text":"Misión y visión", "type":"textarea"},
            ]},
            {"title": "3) Team y servicios", "questions": [
                {"key":"show_team", "text":"Sección Team / About", "type":"textarea"},
                {"key":"main_services", "text":"Servicios de la empresa", "type":"textarea", "required":True},
            ]},
            {"title": "4) Áreas y estrategia SEO", "questions": [
                {"key":"service_areas", "text":"Áreas donde trabaja", "type":"textarea", "required":True},
                {"key":"coverage", "text":"Cobertura aproximada en millas", "type":"number"},
                {"key":"future_expansion", "text":"Expansión futura", "type":"textarea"},
                {"key":"seo_page_strategy", "text":"Cómo definir páginas de servicios", "type":"select", "options":["study", "client_services"]},
            ]},
            {"title": "5) Horario, teléfonos y redes", "questions": [
                {"key":"business_hours", "text":"Horario de trabajo", "type":"text"},
                {"key":"is_24_7", "text":"Atención 24/7", "type":"boolean"},
                {"key":"contact_numbers", "text":"Teléfonos de contacto", "type":"textarea", "required":True},
                {"key":"has_social", "text":"Redes sociales", "type":"textarea"},
            ]},
            {"title": "6) Datos compartidos con Marketing", "questions": [
                {"key":"has_webmail", "text":"Webmail", "type":"textarea"},
                {"key":"has_gbp", "text":"Google Business Profile", "type":"textarea"},
                {"key":"has_website", "text":"Sitio web actual", "type":"textarea"},
            ]},
            {"title": "7) Certificaciones y garantías", "questions": [
                {"key":"certifications", "text":"Certificaciones profesionales", "type":"textarea"},
                {"key":"warranties", "text":"Garantías", "type":"textarea"},
                {"key":"experience_years", "text":"Años de experiencia", "type":"number"},
                {"key":"internal_meeting_notes", "text":"Notas internas de la reunión", "type":"textarea"},
            ]},
            {"title": "8) Estructura y conversión web", "questions": [
                {"key":"business_logic", "text":"Lógica del negocio", "type":"textarea"},
                {"key":"quotes", "text":"Cotizaciones y canales de contacto", "type":"textarea"},
                {"key":"website_structure", "text":"Estructura del sitio web", "type":"textarea"},
                {"key":"resources", "text":"Recursos del proyecto", "type":"textarea"},
                {"key":"website_forms", "text":"Formularios y destino de contactos", "type":"textarea"},
            ]},
        ]
        self.upsert_template(
            "website-technical-v2",
            "Ficha técnica web · Desarrollo",
            "website",
            "Levantamiento guiado del cliente. Los checks verdes se completan automáticamente al llenar cada bloque.",
            sections,
        )

    def seed_software_questionnaire(self):
        sections = [
            {"title":"Objetivo del software", "questions":[
                {"key":"problem_to_solve", "text":"¿Qué problema principal debe resolver el sistema?", "type":"textarea", "required":True},
                {"key":"current_process", "text":"¿Cómo realizan actualmente este proceso?", "type":"textarea"},
                {"key":"success_result", "text":"¿Qué resultado debe lograr la primera versión para considerarla útil?", "type":"textarea"},
            ]},
            {"title":"Usuarios y roles", "questions":[
                {"key":"user_types", "text":"¿Qué tipos de usuarios utilizarán el sistema y qué hace cada uno?", "type":"textarea", "required":True},
                {"key":"access_rules", "text":"¿Qué información o módulos debe poder ver cada rol?", "type":"textarea"},
            ]},
            {"title":"Módulos y flujo", "questions":[
                {"key":"main_modules", "text":"¿Cuáles son los módulos principales que necesita?", "type":"textarea", "required":True},
                {"key":"main_workflow", "text":"Explique el flujo principal desde que inicia una operación hasta que termina.", "type":"textarea"},
                {"key":"must_have_v1", "text":"¿Qué funcionalidades son obligatorias para la V1?", "type":"textarea"},
                {"key":"later_features", "text":"¿Qué funcionalidades pueden quedar para una fase posterior?", "type":"textarea"},
            ]},
            {"title":"Datos e integraciones", "questions":[
                {"key":"existing_data", "text":"¿Existen Excel, bases de datos o sistemas actuales que debamos importar?", "type":"textarea"},
                {"key":"integrations", "text":"¿Debe conectarse con pagos, correo, WhatsApp, Google, APIs u otros sistemas?", "type":"textarea"},
                {"key":"files", "text":"¿El sistema debe manejar archivos, fotos, PDFs, contratos u otros documentos?", "type":"textarea"},
            ]},
            {"title":"Reportes y crecimiento", "questions":[
                {"key":"reports", "text":"¿Qué reportes, métricas o dashboards necesita?", "type":"textarea"},
                {"key":"notifications", "text":"¿Qué alertas o notificaciones debería generar el sistema?", "type":"textarea"},
                {"key":"future_growth", "text":"¿Cómo espera que crezca el sistema en los próximos 12 a 24 meses?", "type":"textarea"},
            ]},
        ]
        self.upsert_template(
            "software-discovery-v2",
            "Ficha técnica · Software V3",
            "software",
            "Plantilla inicial y escalable para levantamiento de proyectos de software.",
            sections,
        )
