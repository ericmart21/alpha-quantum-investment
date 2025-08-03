from django import forms
from .models import Accion, Cartera
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import CustomUser

class AccionForm(forms.ModelForm):
    class Meta:
        model = Accion
        fields = ['cartera', 'nombre', 'ticker', 'cantidad', 'precio_compra', 'fecha']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'cartera': forms.Select(attrs={'class': 'form-select'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'ticker': forms.TextInput(attrs={'class': 'form-control'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control'}),
            'precio_compra': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        usuario = kwargs.pop('usuario', None)
        super().__init__(*args, **kwargs)
        if usuario:
            self.fields['cartera'].queryset = Cartera.objects.filter(usuario=usuario)

class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de usuario'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Contraseña'})
    )

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ['username', 'email']

    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de usuario'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Correo electrónico'})
    )
    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Contraseña'})
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirmar contraseña'})
    )

class CustomLoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control bg-dark text-white border-secondary',
            'placeholder': 'Nombre de usuario'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control bg-dark text-white border-secondary',
            'placeholder': 'Contraseña'
        })
    )

from .models.watchlist import Watchlist

class WatchlistForm(forms.ModelForm):
    class Meta:
        model = Watchlist
        fields = ['nombre', 'ticker', 'valor_objetivo', 'recomendacion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre'}),
            'ticker': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ticker (ej: AAPL)'}),
            'valor_objetivo': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 175.00', 'step': '0.01'}),
            'recomendacion': forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'}),
        }

from django import forms
from .models.cashflow import CashFlow 
from .models.prestamo import Prestamo
from .models.propiedad_alquilada import PropiedadAlquiler

class CashFlowForm(forms.ModelForm):
    class Meta:
        model = CashFlow
        fields = ['date', 'amount', 'category', 'tipo_ingreso', 'description']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'tipo_ingreso': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
        }

class PropiedadAlquilerForm(forms.ModelForm):
    class Meta:
        model = PropiedadAlquiler
        fields = ['nombre', 'ingreso_mensual', 'hipoteca_mensual', 'meses_restantes_hipoteca', 'gastos_mantenimiento']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'ingreso_mensual': forms.NumberInput(attrs={'class': 'form-control'}),
            'hipoteca_mensual': forms.NumberInput(attrs={'class': 'form-control'}),
            'meses_restantes_hipoteca': forms.NumberInput(attrs={'class': 'form-control'}),
            'gastos_mantenimiento': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class PrestamoForm(forms.ModelForm):
    class Meta:
        model = Prestamo
        fields = ['nombre', 'cuota_mensual', 'meses_restantes', 'fecha_inicio', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'cuota_mensual': forms.NumberInput(attrs={'class': 'form-control'}),
            'meses_restantes': forms.NumberInput(attrs={'class': 'form-control'}),
            'fecha_inicio': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }