from django.db import models
from django.conf import settings

class AnalisisFundamental(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ticker = models.CharField(max_length=10)
    fecha = models.DateField(auto_now_add=True)
    datos = models.JSONField()
