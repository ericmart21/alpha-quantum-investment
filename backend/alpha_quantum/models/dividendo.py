from django.db import models
from .accion import Accion

class Dividendo(models.Model):
    accion = models.ForeignKey(
        "alpha_quantum.Accion",
        on_delete=models.CASCADE,
        related_name="dividendos",
    )
    fecha = models.DateField()                      
    monto = models.DecimalField(max_digits=10, decimal_places=4)
    nota  = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ("-fecha",)

    def __str__(self):
        return f"{self.accion.ticker} {self.fecha} {self.monto}"