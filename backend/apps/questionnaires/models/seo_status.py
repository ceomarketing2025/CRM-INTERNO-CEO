from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.projects.models import Project


class SEOProjectStatus(models.Model):

    project = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name="seo_status",
    )

    sitemap_url = models.URLField(
        blank=True,
    )

    last_sitemap_read = models.DateField(
        null=True,
        blank=True,
    )

    general_notes = models.TextField(
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="seo_projects_created",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "project__client__business_name",
        ]

        verbose_name = "Estado SEO del proyecto"
        verbose_name_plural = "Estados SEO de proyectos"

    def __str__(self):
        return f"SEO · {self.project}"

    @property
    def total_urls(self):
        return self.urls.count()

    @property
    def indexed_urls(self):
        return self.urls.filter(
            status="indexed"
        ).count()

    @property
    def indexing_percent(self):
        total = self.total_urls

        if not total:
            return 0

        return round(
            self.indexed_urls / total * 100
        )

    @property
    def top_10_count(self):
        return self.urls.filter(
            current_position__gte=1,
            current_position__lte=10,
        ).count()

    @property
    def improved_count(self):
        return sum(
            1
            for url in self.urls.all()
            if url.evolution_type == "up"
        )

    @property
    def worsened_count(self):
        return sum(
            1
            for url in self.urls.all()
            if url.evolution_type == "down"
        )


class SEOUrlStatus(models.Model):

    STATUS_CHOICES = [
        ("indexed", "Indexada"),
        ("not_indexed", "No indexada"),
        ("pending", "Pendiente"),
        ("unknown", "Sin revisar"),
    ]

    ALERT_CHOICES = [
        ("ok", "Sin alerta"),
        ("monitor", "Monitorear"),
        ("attention", "Atención"),
        ("critical", "Crítica"),
    ]

    seo_project = models.ForeignKey(
        SEOProjectStatus,
        on_delete=models.CASCADE,
        related_name="urls",
    )

    entry_date = models.DateField(
        null=True,
        blank=True,
    )

    page_name = models.CharField(
        max_length=255,
    )

    url = models.URLField(
        max_length=1000,
    )

    objective = models.CharField(
        max_length=255,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="unknown",
    )

    current_position = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )

    previous_position = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )

    last_update = models.DateField(
        null=True,
        blank=True,
    )

    last_sitemap_read = models.DateField(
        null=True,
        blank=True,
    )

    pending_action = models.TextField(
        blank=True,
    )

    observations = models.TextField(
        blank=True,
    )

    alert = models.CharField(
        max_length=20,
        choices=ALERT_CHOICES,
        default="monitor",
    )

    order = models.PositiveIntegerField(
        default=0,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="seo_urls_created",
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="seo_urls_updated",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "order",
            "id",
        ]

        verbose_name = "URL SEO"
        verbose_name_plural = "URLs SEO"

    def __str__(self):
        return f"{self.page_name} · {self.url}"

    @property
    def status_light(self):

        if self.status == "indexed":
            return "green"

        if self.status == "not_indexed":
            return "red"

        if self.status == "pending":
            return "orange"

        return "gray"

    @property
    def ranking_light(self):

        if self.current_position is None:
            return "gray"

        position = float(
            self.current_position
        )

        if 1 <= position <= 10:
            return "green"

        if 10 < position <= 20:
            return "orange"

        if position > 20:
            return "red"

        return "gray"

    @property
    def evolution_type(self):

        if (
            self.current_position is None
            or self.previous_position is None
        ):
            return "neutral"

        if self.current_position < self.previous_position:
            return "up"

        if self.current_position > self.previous_position:
            return "down"

        return "neutral"

    @property
    def evolution_difference(self):

        if (
            self.current_position is None
            or self.previous_position is None
        ):
            return None

        return abs(
            self.previous_position
            - self.current_position
        )

    @property
    def evolution_label(self):

        difference = self.evolution_difference

        if difference is None:
            return "Sin comparación"

        difference = difference.quantize(
            Decimal("0.1")
        )

        if self.evolution_type == "up":
            return f"Mejoró {difference} posiciones"

        if self.evolution_type == "down":
            return f"Empeoró {difference} posiciones"

        return "Sin cambio"