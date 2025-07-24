from django.db import models
from .accion import Cartera

class ValorCartera(models.Model):
    fecha = models.DateField()
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    cartera = models.ForeignKey(Cartera, on_delete=models.CASCADE, related_name='valores')
