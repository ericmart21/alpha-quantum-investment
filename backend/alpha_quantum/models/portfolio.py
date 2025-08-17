# alpha_quantum/services/portfolio.py  (si no lo tenías ya)
from decimal import Decimal
from django.db import transaction
from ..models import Accion
from ..models.transaccion import Transaccion

def recompute_position(user, ticker: str):
    qs = (
        Transaccion.objects
        .filter(user=user, ticker__iexact=ticker)
        .order_by("fecha", "id")
    )
    qty = Decimal("0")
    invested = Decimal("0")
    for t in qs:
        if t.tipo == "BUY":
            qty += Decimal(t.cantidad)
            invested += Decimal(t.cantidad) * Decimal(t.precio) + Decimal(t.comision or 0)
        elif t.tipo == "SELL":
            qty -= Decimal(t.cantidad)

    qty = qty.quantize(Decimal("0.0001"))
    if qty <= 0:
        Accion.objects.filter(user=user, ticker__iexact=ticker).delete()
        return

    avg_cost = invested / qty if qty != 0 else Decimal("0")

    with transaction.atomic():
        Accion.objects.update_or_create(
            user=user, ticker=ticker.upper(),
            defaults={"cantidad": qty, "precio_compra": avg_cost.quantize(Decimal("0.0001"))}
        )
