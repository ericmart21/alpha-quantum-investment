from django.db import models
from django.conf import settings

class Cartera(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='carteras')
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.nombre} - {self.usuario.username}"
