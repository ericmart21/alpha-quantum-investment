from django.db import models
from django.conf import settings
from decimal import Decimal

class PropiedadAlquiler(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=120)
    ingreso_mensual = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    hipoteca_mensual = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gastos_mantenimiento = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    meses_restantes_hipoteca = models.IntegerField(default=0)


    @property
    def beneficio_neto(self) -> Decimal:
        """Ingreso - hipoteca - mantenimiento"""
        return (self.ingreso_mensual or 0) - (self.hipoteca_mensual or 0) - (self.gastos_mantenimiento or 0)

    def __str__(self):
        return self.nombre
