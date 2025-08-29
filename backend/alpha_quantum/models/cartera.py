from django.db import models
from django.conf import settings

class Cartera(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='carteras')
    nombre = models.CharField(max_length=100)
    descripcion  = models.TextField(blank=True, null=True)
    moneda_base  = models.CharField(max_length=10, default="EUR")
    creada       = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} - {self.usuario.username}"
