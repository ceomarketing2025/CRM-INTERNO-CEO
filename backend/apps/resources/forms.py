from django import forms


class DesignCoreLinksForm(forms.Form):
    information_url = forms.URLField(required=False, label="Información / documento de respaldo", widget=forms.URLInput(attrs={"placeholder": "https://docs.google.com/..."}))
    logo_url = forms.URLField(required=False, label="Logo", widget=forms.URLInput(attrs={"placeholder": "https://drive.google.com/..."}))
    palette_url = forms.URLField(required=False, label="Paleta de colores", widget=forms.URLInput(attrs={"placeholder": "https://drive.google.com/..."}))


class DesignPhotoLinkForm(forms.Form):
    service_name = forms.CharField(max_length=140, label="Nombre del servicio", widget=forms.TextInput(attrs={"placeholder": "Ej.: Dumpster Rental"}))
    url = forms.URLField(label="URL", widget=forms.URLInput(attrs={"placeholder": "https://drive.google.com/..."}))
