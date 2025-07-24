from django.db import models
from django.conf import settings

class Watchlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)
    ticker = models.CharField(max_length=10)
    valor_objetivo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    upside = models.FloatField(null=True, blank=True)
    max_52s = models.FloatField(null=True, blank=True)
    min_52s = models.FloatField(null=True, blank=True)
    per = models.FloatField(null=True, blank=True)
    recomendacion = models.CharField(max_length=20, choices=[
        ('COMPRAR', 'Comprar'),
        ('REVISAR', 'Revisar'),
        ('ESPERAR', 'Esperar')
    ], blank=True, null=True)
    precio_actual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.ticker} - {self.nombre}"
