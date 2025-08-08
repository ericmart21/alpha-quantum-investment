# app: alpha_quantum  (ajusta si tu app se llama distinto)
from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal

class Transaccion(models.Model):
    TIPO = (
        ('BUY', 'Compra'),
        ('SELL', 'Venta'),
        ('DIV', 'Dividendo'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ticker = models.CharField(max_length=16)
    tipo = models.CharField(max_length=4, choices=TIPO)
    cantidad = models.DecimalField(max_digits=18, decimal_places=4, default=0)   # para DIV puedes poner nº acciones
    precio = models.DecimalField(max_digits=18, decimal_places=4, default=0)     # en DIV: dividendo por acción o total
    comision = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    fecha = models.DateField()
    nota = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-fecha', '-id']

    def importe(self) -> Decimal:
        """
        BUY:  +(cantidad*precio + comision)
        SELL: -(cantidad*precio - comision)   (signo negativo: sale dinero)
        DIV:  +(cantidad*precio)  (si usas precio = div/acción * cantidad)
        """
        bruto = self.cantidad * self.precio
        if self.tipo == 'BUY':
            return bruto + self.comision
        if self.tipo == 'SELL':
            return -(bruto - self.comision)
        # DIV
        return bruto

    def __str__(self):
        return f"{self.fecha} {self.ticker} {self.tipo} {self.cantidad} @ {self.precio}"
