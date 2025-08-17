# alpha_quantum/models/historico.py
from django.conf import settings
from django.db import models

class HistoricoCartera(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="historicos_cartera")
    fecha = models.DateField(db_index=True)
    valor = models.DecimalField(max_digits=18, decimal_places=2)      # valor actual de la cartera
    invertido = models.DecimalField(max_digits=18, decimal_places=2)  # suma de (precio_compra * cantidad)

    class Meta:
        unique_together = ("user", "fecha")
        ordering = ["fecha"]

    def __str__(self):
        return f"{self.user} | {self.fecha} | valor={self.valor} invertido={self.invertido}"
