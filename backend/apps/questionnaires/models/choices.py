from django.db import models


class QuestionType(models.TextChoices):
    TEXT = "text", "Texto corto"
    TEXTAREA = "textarea", "Texto largo"
    BOOLEAN = "boolean", "Sí / No"
    URL = "url", "URL"
    NUMBER = "number", "Número"
    SELECT = "select", "Selección"
    MULTI = "multi", "Selección múltiple"


class QuestionnaireStatus(models.TextChoices):
    DRAFT = "draft", "Borrador"
    IN_PROGRESS = "in_progress", "En progreso"
    COMPLETE = "complete", "Completo"


class AnswerState(models.TextChoices):
    PENDING = "pending", "Pendiente"
    CONFIRMED = "confirmed", "Confirmado"
    NO = "no", "No"
    NOT_APPLICABLE = "na", "No aplica"
