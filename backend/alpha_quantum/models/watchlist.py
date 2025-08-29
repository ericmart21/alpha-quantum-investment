from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator


class WatchlistLista(models.Model):
    """
    Contenedor de una lista de seguimiento con título propio por usuario.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='watchlists'
    )
    titulo = models.CharField(max_length=120)
    descripcion = models.CharField(max_length=255, blank=True, null=True)

    # null=True para evitar prompts en migraciones si ya hay filas
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'titulo'],
                name='uq_watchlistlista_user_titulo'
            )
        ]
        ordering = ['titulo']

    def __str__(self) -> str:
        return self.titulo


class Watchlist(models.Model):
    """
    Ítems (acciones) pertenecientes a una WatchlistLista.
    """
    RECOMENDACIONES = [
        ('COMPRAR', 'Comprar'),
        ('REVISAR', 'Revisar'),
        ('ESPERAR', 'Esperar'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    # ⚠️ Dejado como null=True para migrar sin problemas si ya tienes datos.
    # Tras hacer un backfill, puedes cambiarlo a null=False en una migración posterior.
    lista = models.ForeignKey(
        WatchlistLista,
        on_delete=models.CASCADE,
        related_name='items',
        null=True,
        blank=True,
    )

    nombre = models.CharField(max_length=100)
    ticker = models.CharField(max_length=10)

    valor_objetivo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    precio_actual = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    upside = models.FloatField(null=True, blank=True)

    max_52s = models.FloatField(null=True, blank=True)
    min_52s = models.FloatField(null=True, blank=True)
    per = models.FloatField(null=True, blank=True, validators=[MinValueValidator(0)])

    sector = models.CharField(max_length=64, blank=True, null=True)
    currency = models.CharField(max_length=8, blank=True, null=True, default='USD')

    recomendacion = models.CharField(max_length=20, choices=RECOMENDACIONES, blank=True, null=True)

    # Timestamps opcionales (null=True para migrar sin prompts)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        # Evita duplicados del mismo ticker en la MISMA lista de un usuario
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'lista', 'ticker'],
                name='uq_watchlist_user_lista_ticker'
            )
        ]
        indexes = [
            models.Index(fields=['user', 'lista', 'ticker']),
        ]
        ordering = ['ticker']

    def save(self, *args, **kwargs):
        # Normaliza el ticker (MAYÚSCULAS, sin espacios)
        if self.ticker:
            self.ticker = self.ticker.upper().strip()
        super().save(*args, **kwargs)

    @property
    def computed_upside(self):
        """
        Upside calculado en tiempo real si hay valor_objetivo y precio_actual.
        """
        try:
            if self.valor_objetivo and self.precio_actual and float(self.precio_actual) > 0:
                return float((self.valor_objetivo / self.precio_actual - 1) * 100)
        except Exception:
            return None
        return None

    def __str__(self) -> str:
        pref = f"[{self.lista.titulo}] " if self.lista_id else ""
        return f"{pref}{self.ticker} - {self.nombre}"
