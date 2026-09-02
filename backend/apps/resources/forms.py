from django import forms
from .models import ImageReference, ProjectResourceLink


class ProjectResourceLinkForm(forms.ModelForm):
    class Meta:
        model = ProjectResourceLink
        fields = ["area", "kind", "label", "url", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}


class ImageReferenceForm(forms.ModelForm):
    class Meta:
        model = ImageReference
        fields = ["category", "image_url", "source", "notes", "order"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}
