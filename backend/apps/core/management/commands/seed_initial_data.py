from decimal import Decimal
from django.core.management.base import BaseCommand
from apps.finance.models import FinanceCategory
from apps.plans.models import ServicePlan
from apps.questionnaires.models import Question, QuestionnaireSection, QuestionnaireTemplate


class Command(BaseCommand):
    help = "Carga catálogos y plantillas V2 de forma idempotente."

    def handle(self, *args, **options):
        self.seed_finance_categories()
        self.seed_plans()
        self.seed_website_questionnaire()
        self.seed_software_questionnaire()
        self.stdout.write(self.style.SUCCESS("Datos base V2 verificados."))

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
        template, _ = QuestionnaireTemplate.objects.update_or_create(
            code=code,
            defaults={"name": name, "project_type": project_type, "description": description, "is_active": True},
        )
        valid_titles = []
        for s_order, section_data in enumerate(sections, start=1):
            valid_titles.append(section_data["title"])
            section, _ = QuestionnaireSection.objects.update_or_create(
                template=template,
                title=section_data["title"],
                defaults={"description": section_data.get("description", ""), "order": s_order},
            )
            valid_keys = []
            for q_order, q in enumerate(section_data["questions"], start=1):
                valid_keys.append(q["key"])
                Question.objects.update_or_create(
                    section=section,
                    key=q["key"],
                    defaults={
                        "text": q["text"],
                        "help_text": q.get("help", ""),
                        "question_type": q.get("type", "text"),
                        "required": q.get("required", False),
                        "options": q.get("options", []),
                        "order": q_order,
                    },
                )
            section.questions.exclude(key__in=valid_keys).delete()
        template.sections.exclude(title__in=valid_titles).delete()
        return template

    def seed_website_questionnaire(self):
        # La estructura sigue el flujo real del Excel operativo: Estado + Respuesta/Detalle.
        sections = [
            {"title": "1) Información general", "questions": [
                {"key":"company_description", "text":"Breve descripción de la empresa / ¿A qué se dedica?", "type":"textarea", "required":True},
            ]},
            {"title": "2) Identidad y visión", "questions": [
                {"key":"slogan", "text":"¿Ya compartió slogan o frase corta?", "type":"text"},
                {"key":"has_mission_vision", "text":"¿La empresa ya tiene misión y visión definidas?", "type":"boolean"},
                {"key":"mission_final", "text":"Misión final", "type":"textarea"},
                {"key":"vision_final", "text":"Visión final", "type":"textarea"},
                {"key":"mission_origin", "text":"Si NO la tienen: ¿Por qué nació la empresa y cuál es su propósito actual?", "type":"textarea"},
                {"key":"audience_differentiator", "text":"Si NO la tienen: ¿A qué tipo de clientes va dirigida y qué la hace diferente?", "type":"textarea"},
                {"key":"vision_5_10_years", "text":"Si NO la tienen: ¿Cómo se imaginan en 5 a 10 años?", "type":"textarea"},
                {"key":"legacy", "text":"Si NO la tienen: ¿Qué huella o legado quieren dejar?", "type":"textarea"},
            ]},
            {"title": "3) Team, servicios y áreas", "questions": [
                {"key":"show_team", "text":"¿Desea incluir sección Team / About?", "type":"boolean"},
                {"key":"team_members", "text":"Si desea Team: ¿ya compartió fotos, nombres y cargos del equipo?", "type":"textarea"},
                {"key":"main_services", "text":"¿Ya compartió los servicios principales?", "type":"textarea", "required":True},
                {"key":"service_areas", "text":"¿Ya compartió las áreas donde trabaja?", "type":"textarea"},
                {"key":"coverage", "text":"¿Ya confirmó la cobertura aproximada (millas/minutos alrededor)?", "type":"textarea"},
                {"key":"preferred_cities", "text":"¿Ya confirmó ciudades o condados principales a incluir?", "type":"textarea"},
                {"key":"excluded_services", "text":"¿Existe algún servicio que ya no quiera ofrecer o prefiera dejar fuera?", "type":"textarea"},
                {"key":"future_expansion", "text":"¿Tiene pensado expandirse a otras zonas?", "type":"textarea"},
            ]},
            {"title": "4) Horario y contacto", "questions": [
                {"key":"business_hours", "text":"¿Ya confirmó el horario exacto de trabajo?", "type":"text"},
                {"key":"is_24_7", "text":"¿Ya confirmó si atienden 24/7?", "type":"boolean"},
                {"key":"contact_numbers", "text":"¿Ya confirmó el número de contacto principal?", "type":"textarea"},
                {"key":"has_social", "text":"¿Ya confirmó si tiene redes sociales?", "type":"boolean"},
                {"key":"facebook", "text":"Facebook", "type":"url"},
                {"key":"instagram", "text":"Instagram", "type":"url"},
                {"key":"tiktok", "text":"TikTok", "type":"url"},
                {"key":"has_webmail", "text":"¿Ya confirmó si cuenta con webmail (info@...)?", "type":"boolean"},
                {"key":"webmail_email", "text":"Correo webmail", "type":"text", "help":"No guardar contraseñas en esta ficha."},
                {"key":"has_gbp", "text":"¿Ya confirmó si tiene Google Business / reseñas reales?", "type":"boolean"},
                {"key":"gbp_notes", "text":"Estado / notas de Google Business", "type":"textarea", "help":"Registrar estado o correo. Las credenciales deben gestionarse fuera de esta ficha."},
            ]},
            {"title": "5) Certificaciones y garantías", "questions": [
                {"key":"certifications", "text":"¿Ya confirmó certificaciones profesionales?", "type":"textarea"},
                {"key":"warranties", "text":"¿Ya confirmó garantía de trabajo o instalación?", "type":"textarea"},
                {"key":"experience_years", "text":"¿Ya confirmó los años de experiencia?", "type":"text"},
                {"key":"internal_meeting_notes", "text":"Notas internas de la reunión", "type":"textarea"},
            ]},
        ]
        self.upsert_template(
            "website-technical-v2",
            "Ficha técnica web · Desarrollo",
            "website",
            "Formulario operativo basado en la ficha técnica y el Excel de trabajo. Cada pregunta permite marcar estado y guardar detalle.",
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
            "Ficha técnica · Software V2",
            "software",
            "Plantilla inicial y escalable para levantamiento de proyectos de software.",
            sections,
        )
