from django.db import models

class PrecioHistorico(models.Model):
    accion = models.ForeignKey('Accion', on_delete=models.CASCADE, related_name='precios')
    fecha = models.DateField()
    valor = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.accion.ticker} - {self.fecha}: {self.valor}"
