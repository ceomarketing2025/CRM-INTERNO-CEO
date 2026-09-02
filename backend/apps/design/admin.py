from django.contrib import admin
from .models import ColorPalette, DesignBrief, PaletteColor, PaletteGradient
admin.site.register(DesignBrief)
admin.site.register(ColorPalette)
admin.site.register(PaletteColor)
admin.site.register(PaletteGradient)
