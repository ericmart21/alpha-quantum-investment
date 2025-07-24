from django.db import models
from django.conf import settings

class EventoFinanciero(models.Model):
    TIPO_EVENTO_CHOICES = [
        ('resultado', 'Resultado Trimestral'),
        ('dividendo', 'Dividendo'),
        ('compra', 'Compra'),
        ('venta', 'Venta'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ticker = models.CharField(max_length=10)
    tipo_evento = models.CharField(max_length=10, choices=TIPO_EVENTO_CHOICES)
    descripcion = models.TextField(blank=True)
    fecha = models.DateField()
    hora = models.TimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.ticker} - {self.tipo_evento} - {self.fecha}"
