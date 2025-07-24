# cronjobs/management/commands/actualizar_eventos.py

from django.core.management.base import BaseCommand
from alpha_quantum.models.watchlist import Watchlist
from alpha_quantum.models.calendario import EventoFinanciero
from alpha_quantum.utils import obtener_eventos_financieros_finnhub

class Command(BaseCommand):
    help = 'Actualiza eventos financieros desde Finnhub'

    def handle(self, *args, **kwargs):
        for watch in Watchlist.objects.all():
            obtener_eventos_financieros_finnhub(watch.ticker, watch.user)
        self.stdout.write(self.style.SUCCESS("✅ Eventos actualizados correctamente."))
