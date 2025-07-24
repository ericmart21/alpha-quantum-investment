from django.db import models
from .accion import Accion

class Dividendo(models.Model):
    accion = models.ForeignKey(Accion, on_delete=models.CASCADE)
    fecha = models.DateField()
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.accion.ticker} - {self.cantidad}€ el {self.fecha}"