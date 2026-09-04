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
        plans = [
            dict(code="website-basic", name="Página Web Básica", service_type="website", description="Plan web básico.", base_price=Decimal("1200.00"), billing_cycle="one_time", rules={"level": "basic"}),
            dict(code="website-medium", name="Página Web Media", service_type="website", description="Plan web intermedio.", base_price=Decimal("2400.00"), billing_cycle="one_time", rules={"level": "medium"}),
            dict(code="website-advanced", name="Página Web Avanzada", service_type="website", description="Plan web avanzado.", base_price=Decimal("4000.00"), billing_cycle="one_time", rules={"level": "advanced"}),
            dict(code="software-custom", name="Software Personalizado", service_type="software", description="Base para cotizaciones y desarrollos de software a medida.", base_price=Decimal("0.00"), billing_cycle="custom", rules={}),
            dict(code="social-media-custom", name="Social Media", service_type="social_media", description="Base para planes de gestión de redes sociales.", base_price=Decimal("0.00"), billing_cycle="monthly", rules={}),
        ]
        for item in plans:
            code = item.pop("code")
            ServicePlan.objects.update_or_create(code=code, defaults={**item, "currency": "USD", "is_active": True})

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
