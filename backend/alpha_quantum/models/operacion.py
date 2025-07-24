# models/operacion.py
from django.db import models
from .accion import Accion
from .cartera import Cartera

class Operacion(models.Model):
    TIPO_CHOICES = (
        ('compra', 'Compra'),
        ('venta', 'Venta'),
    )
    cartera = models.ForeignKey(Cartera, on_delete=models.CASCADE, related_name='operaciones')
    accion = models.ForeignKey(Accion, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    fecha = models.DateField()
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    cantidad = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.tipo} - {self.accion.ticker} - {self.cantidad}"
