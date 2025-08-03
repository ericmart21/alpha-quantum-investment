from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class PropiedadAlquiler(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)
    ingreso_mensual = models.DecimalField(max_digits=10, decimal_places=2)
    hipoteca_mensual = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    meses_restantes_hipoteca = models.PositiveIntegerField(default=0)
    gastos_mantenimiento = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    @property
    def beneficio_neto(self):
        return self.ingreso_mensual - self.hipoteca_mensual - self.gastos_mantenimiento

    def __str__(self):
        return self.nombre

