# models/alarma.py
from django.db import models
from .accion import Accion
from .cartera import Cartera
from django.conf import settings

class AlarmaPrecio(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='alarmas')
    accion = models.ForeignKey(Accion, on_delete=models.CASCADE)
    precio_objetivo = models.DecimalField(max_digits=10, decimal_places=2)
    es_activada = models.BooleanField(default=False)

    def __str__(self):
        return f"Alarma {self.accion.ticker} - {self.precio_objetivo}€"
