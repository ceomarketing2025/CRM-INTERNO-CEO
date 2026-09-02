from django import forms
from .models import ColorPalette, DesignBrief, PaletteColor, PaletteGradient


class DesignBriefForm(forms.ModelForm):
    class Meta:
        model = DesignBrief
        exclude = ["project", "completed", "completed_at", "completed_by"]
        widgets = {
            "social_notes": forms.Textarea(attrs={"rows": 2}),
            "meeting_attendees": forms.Textarea(attrs={"rows": 2, "placeholder": "Ej.: Dakmar, Oscar..."}),
            "logo_change_notes": forms.Textarea(attrs={"rows": 3}),
            "visual_structure_notes": forms.Textarea(attrs={"rows": 3}),
            "color_base_notes": forms.Textarea(attrs={"rows": 2}),
            "services": forms.Textarea(attrs={"rows": 3}),
            "page_style_notes": forms.Textarea(attrs={"rows": 3}),
            "typography_direction": forms.Textarea(attrs={"rows": 2}),
            "layout_preferences": forms.Textarea(attrs={"rows": 3}),
            "visual_references": forms.Textarea(attrs={"rows": 3}),
            "elements_to_avoid": forms.Textarea(attrs={"rows": 2}),
            "designer_notes": forms.Textarea(attrs={"rows": 3}),
        }


class PaletteForm(forms.ModelForm):
    class Meta:
        model = ColorPalette
        fields = ["name", "description", "is_primary", "general_rules"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2}), "general_rules": forms.Textarea(attrs={"rows": 5})}


class PaletteColorForm(forms.ModelForm):
    class Meta:
        model = PaletteColor
        fields = ["role", "label", "hex_code", "usage", "order"]
        widgets = {"hex_code": forms.TextInput(attrs={"type": "color", "class": "color-input"})}


class PaletteGradientForm(forms.ModelForm):
    class Meta:
        model = PaletteGradient
        fields = ["name", "start_hex", "end_hex", "order"]
        widgets = {
            "start_hex": forms.TextInput(attrs={"type": "color", "class": "color-input"}),
            "end_hex": forms.TextInput(attrs={"type": "color", "class": "color-input"}),
        }
