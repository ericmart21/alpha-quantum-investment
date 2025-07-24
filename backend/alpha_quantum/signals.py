# backend/alpha_quantum/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from alpha_quantum.models.accion import Accion
from alpha_quantum.utils import obtener_eventos_financieros_alpha_vantage


@receiver(post_save, sender=Accion)
def crear_eventos_financieros(sender, instance, created, **kwargs):
    if created:
        try:
            user = instance.cartera.usuario
            obtener_eventos_financieros_alpha_vantage(instance.ticker, user)
        except Exception as e:
            print(f"❌ Error al generar eventos tras crear acción: {e}")
