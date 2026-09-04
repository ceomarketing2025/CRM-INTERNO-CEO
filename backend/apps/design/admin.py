from django.contrib import admin
from .models import (
    ColorPalette,
    DesignBrief,
    DesignTask,
    DesignTaskCycle,
    DesignTaskCycleItem,
    PaletteColor,
    PaletteGradient,
    SocialMediaContentItem,
    SocialMediaCycle,
)

admin.site.register(DesignBrief)
admin.site.register(DesignTask)
admin.site.register(DesignTaskCycle)
admin.site.register(DesignTaskCycleItem)
admin.site.register(ColorPalette)
admin.site.register(PaletteColor)
admin.site.register(PaletteGradient)
admin.site.register(SocialMediaCycle)
admin.site.register(SocialMediaContentItem)
