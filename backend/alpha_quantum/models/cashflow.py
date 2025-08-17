from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

INGRESO_CHOICES = [
    ('salario', 'Salario'),
    ('alquiler', 'Alquileres'),
    ('dividendos', 'Dividendos'),
    ('intereses', 'Intereses bancarios o préstamos'),
    ('ventas', 'Ganancias por venta de activos'),
    ('autonomo', 'Ingresos como autónomo/profesional'),
    ('empresa', 'Distribución de beneficios empresariales'),
    ('subsidios', 'Subsidios o pensiones'),
    ('regalos', 'Regalos o herencias'),
    ('otros', 'Otros ingresos')
]

class CashFlow(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateField()
    amount = models.FloatField()
    category = models.CharField(max_length=50, choices=[('ingreso', 'Ingreso'), ('gasto', 'Gasto')])
    tipo_ingreso = models.CharField(max_length=50, choices=INGRESO_CHOICES, blank=True, null=True)
    description = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.user} - {self.category} - {self.amount}€ en {self.date}"

