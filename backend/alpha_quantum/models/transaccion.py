from django.db import models
from django.conf import settings
from decimal import Decimal

class Transaccion(models.Model):
    TIPO = (
        ('BUY', 'Compra'),
        ('SELL', 'Venta'),
        ('DIV', 'Dividendo'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ticker = models.CharField(max_length=16)
    tipo = models.CharField(max_length=4, choices=TIPO)
    cantidad = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    precio = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    comision = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    fecha = models.DateField()
    nota = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-fecha', '-id']

    def importe(self) -> Decimal:
        bruto = self.cantidad * self.precio
        if self.tipo == 'BUY':
            return bruto + self.comision
        if self.tipo == 'SELL':
            return -(bruto - self.comision)
        return bruto

    def __str__(self):
        return f"{self.fecha} {self.ticker} {self.tipo} {self.cantidad} @ {self.precio}"

