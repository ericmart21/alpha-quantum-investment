from django.conf import settings
from django.db import models
from datetime import date

User = settings.AUTH_USER_MODEL

class Prestamo(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)
    monto_total = models.DecimalField(max_digits=12, decimal_places=2)
    cuota_mensual = models.DecimalField(max_digits=10, decimal_places=2)
    meses_restantes = models.PositiveIntegerField()
    fecha_inicio = models.DateField()
    activo = models.BooleanField(default=True)

    def total_pagado(self):
        # (opcional, según tu lógica)
        meses_transcurridos = (date.today().year - self.fecha_inicio.year) * 12 + (date.today().month - self.fecha_inicio.month)
        meses_pagados = max(0, min(meses_transcurridos, self.meses_restantes))
        return meses_pagados * self.cuota_mensual

    @property
    def balance_actual(self):
        return self.meses_restantes * self.cuota_mensual if self.activo else 0

    def __str__(self):
        return self.nombre