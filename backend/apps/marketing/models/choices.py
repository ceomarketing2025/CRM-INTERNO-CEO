from django.db import models
class MarketingTaskStatus(models.TextChoices):
    TODO = "todo", "Pendiente"
    DOING = "doing", "En proceso"
    REVIEW = "review", "Revisión"
    DONE = "done", "Finalizada"
