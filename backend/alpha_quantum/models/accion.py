from django.db import models
from .cartera import Cartera
from django.conf import settings

class Accion(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='acciones')
    cartera = models.ForeignKey(Cartera, on_delete=models.CASCADE, related_name="acciones")
    nombre = models.CharField(max_length=100)
    ticker = models.CharField(max_length=10)
    cantidad = models.IntegerField()
    precio_compra = models.FloatField()
    precio_actual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    fecha = models.DateField()
    
    def __str__(self):
        return f"{self.nombre} ({self.ticker})"