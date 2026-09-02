from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import UserAccount

class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label="Correo", widget=forms.EmailInput(attrs={"autofocus": True, "placeholder": "correo@empresa.com"}))

class ManagerUserCreateForm(forms.ModelForm):
    password1 = forms.CharField(label="Contraseña", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmar contraseña", widget=forms.PasswordInput)
    class Meta:
        model = UserAccount
        fields = ["email", "first_name", "last_name", "role", "job_title", "is_active"]
    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password1") != cleaned.get("password2"):
            self.add_error("password2", "Las contraseñas no coinciden.")
        return cleaned
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user

class ManagerUserEditForm(forms.ModelForm):
    new_password = forms.CharField(label="Nueva contraseña", required=False, widget=forms.PasswordInput, help_text="Déjalo vacío para mantener la actual.")
    class Meta:
        model = UserAccount
        fields = ["email", "first_name", "last_name", "role", "job_title", "is_active"]
    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get("new_password"):
            user.set_password(self.cleaned_data["new_password"])
        if commit:
            user.save()
        return user
