from django.db import models
from .accion import Accion

class AnalisisFundamental(models.Model):
    accion = models.OneToOneField(Accion, on_delete=models.CASCADE)
    PER = models.FloatField(null=True, blank=True)
    ROE = models.FloatField(null=True, blank=True)
    ROI = models.FloatField(null=True, blank=True)
    deuda_total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    beneficio_neto = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    valor_intrinseco = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"Análisis {self.accion.ticker}"
