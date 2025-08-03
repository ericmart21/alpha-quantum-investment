from django.db import models
from django.contrib.auth import get_user_model
from datetime import date
from dateutil.relativedelta import relativedelta

User = get_user_model()

class Prestamo(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)
    monto_total = models.DecimalField(max_digits=12, decimal_places=2)
    cuota_mensual = models.DecimalField(max_digits=10, decimal_places=2)
    meses_restantes = models.PositiveIntegerField()
    fecha_inicio = models.DateField()
    activo = models.BooleanField(default=True)

    def total_pagado(self):
        # Calcular meses transcurridos desde inicio
        meses_transcurridos = (date.today().year - self.fecha_inicio.year) * 12 + (date.today().month - self.fecha_inicio.month)
        meses_pagados = max(0, meses_transcurridos - self.meses_restantes)
        return meses_pagados * self.cuota_mensual

    def balance_actual(self):
        return self.meses_restantes * self.cuota_mensual if self.activo else 0

    def __str__(self):
        return self.nombre