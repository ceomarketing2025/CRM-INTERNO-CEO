from django.db import models


class StyleDirection(models.TextChoices):
    MINIMAL = "minimal", "Minimalista"
    MODERN = "modern", "Moderno"
    CORPORATE = "corporate", "Corporativo"
    PREMIUM = "premium", "Premium / elegante"
    BOLD = "bold", "Fuerte / llamativo"
    FRIENDLY = "friendly", "Cercano / amigable"
    CUSTOM = "custom", "Personalizado"


class LogoStatus(models.TextChoices):
    HAS_LOGO = "has_logo", "Ya tiene logo"
    NEEDS_LOGO = "needs_logo", "Necesita logo"
    REVIEW = "review", "Debe modificarse / revisarse"


class LogoFormat(models.TextChoices):
    EDITABLE = "editable", "Editable (AI, SVG, etc.)"
    IMAGE = "image", "Imagen (PNG, JPG)"
    UNKNOWN = "unknown", "No sabe"


class WebVisualStructure(models.TextChoices):
    SIMPLE = "simple", "Sencilla"
    VISUAL = "visual", "Visual"
    HIGH_DESIGN = "high_design", "Muy diseñada"


class BackgroundStyle(models.TextChoices):
    LIGHT = "light", "Claro"
    DARK = "dark", "Oscuro"
    MIXED = "mixed", "Mixto (blanco + secciones con color)"


class PhotoAvailability(models.TextChoices):
    OWN = "own", "Tiene fotos propias"
    NONE = "none", "No tiene fotos"
    PARTIAL = "partial", "Tiene algunas fotos"


class StockUsage(models.TextChoices):
    MIX = "mix", "Mezcla (propias + profesionales)"
    PROFESSIONAL = "professional", "Mayormente profesionales"
    NONE = "none", "No usar stock"


class PaletteColorRole(models.TextChoices):
    TEXT = "text", "Texto"
    BACKGROUND = "background", "Fondo"
    PRIMARY = "primary", "Primario"
    SECONDARY = "secondary", "Secundario"
    ACCENT = "accent", "Acento"
    EXTRA = "extra", "Extra"
