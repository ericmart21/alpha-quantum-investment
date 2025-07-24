from django.contrib import admin
from .models import CustomUser, Cartera, Accion, Dividendo, PrecioHistorico, AnalisisFundamental, Operacion, AlarmaPrecio
from .models.watchlist import Watchlist
from .models.calendario import EventoFinanciero
admin.site.register(CustomUser)
admin.site.register(Cartera)
admin.site.register(Accion)
admin.site.register(Dividendo)
admin.site.register(PrecioHistorico)
admin.site.register(AnalisisFundamental)
admin.site.register(Operacion)
admin.site.register(AlarmaPrecio)
admin.site.register(Watchlist)
admin.site.register(EventoFinanciero)