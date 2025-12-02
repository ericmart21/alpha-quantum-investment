.# alpha_quantum/views.py
from __future__ import annotations
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.timezone import now
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib.auth.forms import UserCreationForm
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view

from django.db.models import Sum
from decimal import Decimal, InvalidOperation
from datetime import date, datetime, timedelta
import json
import requests

from django.views.decorators.http import require_POST

# ===== Modelos y forms =====
from .models import Accion, Cartera, PrecioHistorico
from .models.historico import HistoricoCartera
from .models.dividendo import Dividendo
from .models.transaccion import Transaccion
from .models.watchlist import Watchlist
from .models.cashflow import CashFlow
from .models.propiedad_alquilada import PropiedadAlquiler
from .models.prestamo import Prestamo
from .models.calendario import EventoFinanciero

from .forms import (
    AccionForm, LoginForm, CustomUserCreationForm, WatchlistForm,
    CashFlowForm, PropiedadAlquilerForm, PrestamoForm,
    DividendoForm, TransaccionForm
)

from .utils import (
    obtener_precio_actual, calcular_resumen, calcular_upside, generar_recomendacion,
    snapshot_cartera_diario, backfill_snapshots, obtener_datos_finnhub,
    obtener_eventos_financieros_alpha_vantage, obtener_datos_fundamentales_alpha_vantage
)

# ===========================
#          HOME
# ===========================
def index(request):
    acciones = Accion.objects.all()
    acciones_json = json.dumps([{'nombre': a.nombre, 'cantidad': a.cantidad} for a in acciones])
    return render(request, 'alpha_quantum/index.html', {'acciones': acciones, 'acciones_json': acciones_json})

def agregar_accion(request):
    if request.method == "POST":
        nombre = request.POST["nombre"]
        ticker = request.POST["ticker"]
        cantidad = int(request.POST["cantidad"])
        precio_compra = float(request.POST["precio_compra"])
        fecha_str = request.POST.get("fecha")
        if not fecha_str:
            return HttpResponse("Debes introducir una fecha.", status=400)

        try:
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        except ValueError:
            return HttpResponse("Formato de fecha inválido.", status=400)

        cartera, _ = Cartera.objects.get_or_create(usuario=request.user, nombre="Cartera Principal")

        Accion.objects.create(
            user=request.user, nombre=nombre, ticker=ticker.upper(),
            cantidad=cantidad, precio_compra=precio_compra, fecha=fecha, cartera=cartera
        )
        return redirect("index")
    return render(request, "alpha_quantum/agregar.html")


# ===========================
#        DASHBOARD
# ===========================
@login_required
def dashboard(request):
    user = request.user

    # 1) Actualiza precios mínimamente (si API falla conserva último precio)
    acciones_user = Accion.objects.filter(user=user)
    for a in acciones_user:
        try:
            p = obtener_precio_actual(a.ticker) or 0.0
            if p > 0:
                a.precio_actual = Decimal(str(p))
                a.save(update_fields=["precio_actual"])
        except Exception:
            pass

    # 2) Snapshot del día
    snapshot_cartera_diario(user)

    # 3) KPIs
    total_invertido = Decimal("0")
    valor_actual = Decimal("0")
    valor_por_ticker = {}

    for a in acciones_user:
        pc = Decimal(str(a.precio_compra or 0))
        pa = Decimal(str(a.precio_actual or 0))
        qty = Decimal(str(a.cantidad or 0))
        total_invertido += pc * qty
        valor_ticker = pa * qty
        valor_actual += valor_ticker
        if qty > 0:
            valor_por_ticker[a.ticker] = valor_ticker

    rentabilidad_total = valor_actual - total_invertido

    # 4) Distribución
    if valor_actual > 0:
        dist_labels = list(valor_por_ticker.keys())
        dist_values = [float(v / valor_actual * Decimal('100')) for v in valor_por_ticker.values()]
    else:
        invertido_por_ticker = {
            a.ticker: Decimal(str(a.precio_compra or 0)) * Decimal(str(a.cantidad or 0))
            for a in acciones_user if a.cantidad
        }
        suma_inv = sum(invertido_por_ticker.values()) or Decimal('1')
        dist_labels = list(invertido_por_ticker.keys())
        dist_values = [float(v / suma_inv * Decimal('100')) for v in invertido_por_ticker.values()]

    # 5) Serie histórica
    qs_hist = HistoricoCartera.objects.filter(user=user).order_by("fecha")
    if not qs_hist.exists():
        backfill_snapshots(user, days=90)
        qs_hist = HistoricoCartera.objects.filter(user=user).order_by("fecha")

    hist_labels = [h.fecha.strftime("%Y-%m-%d") for h in qs_hist]
    hist_values = [float(h.valor - h.invertido) for h in qs_hist]

    # 6) Listas para tabla
    dividendos = Dividendo.objects.filter(accion__user=user).select_related("accion").order_by("-fecha")
    transacciones = Transaccion.objects.filter(user=user).order_by("-fecha", "-id")
    if total_invertido > 0:
        rentabilidad_pct_total = float((rentabilidad_total / total_invertido) * Decimal('100'))
    else:
        rentabilidad_pct_total = 0.0
    context = {
        "valor_total_cartera": round(float(valor_actual), 2),
        "rentabilidad_total": round(float(rentabilidad_total), 2),
        "rentabilidad_pct_total": round(float(rentabilidad_pct_total), 2),
        "total_invertido": round(float(total_invertido), 2),
        "hist_labels": json.dumps(hist_labels),
        "hist_values": json.dumps(hist_values),
        "dist_labels": json.dumps(dist_labels),
        "dist_values": json.dumps(dist_values),
        "dividendos": dividendos,
        "transacciones": transacciones,
    }
    return render(request, "alpha_quantum/dashboard.html", context)

from decimal import Decimal
from datetime import date, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth.decorators import login_required

# ...

from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import Accion

@login_required
def cartera(request):
    """
    Vista de cartera con KPIs, tabla enriquecida y rebalanceo igual-ponderado.
    """
    acciones = Accion.objects.filter(user=request.user)  # <<-- IMPORTANTE filtrar por user

    items = []
    total_val = Decimal('0')
    total_inv = Decimal('0')

    for a in acciones:
        qty = Decimal(str(a.cantidad or 0))
        pc  = Decimal(str(a.precio_compra or 0))
        # si no hay precio_actual, usa precio_compra para evitar nulos
        pa  = Decimal(str(a.precio_actual or a.precio_compra or 0))

        inv = qty * pc
        val = qty * pa
        pnl = val - inv
        rr  = (pnl / inv * Decimal('100')) if inv > 0 else Decimal('0')

        items.append({
            "id": a.id,
            "ticker": a.ticker,
            "precio_compra": float(pc),
            "precio_actual": float(pa),
            "cantidad": int(qty),
            "valor_total": float(val),
            "pnl_eur": float(pnl),
            "pnl_pct": float(rr),
        })
        total_val += val
        total_inv += inv

    # % del total y KPIs
    for it in items:
        it["pct_total"] = float(
            (Decimal(str(it["valor_total"])) / (total_val or Decimal('1'))) * Decimal('100')
        )

    rentab_total_eur = total_val - total_inv
    rentab_total_pct = (rentab_total_eur / total_inv * Decimal('100')) if total_inv > 0 else Decimal('0')

    # Rebalanceo igual ponderado simple
    n = len(items) or 1
    target = Decimal('100') / Decimal(str(n))
    rebalance = []
    for it in items:
        actual = Decimal(str(it["pct_total"]))
        diff = target - actual
        sug = 'ok'
        if diff > Decimal('0.25'):
            sug = 'buy'
        elif diff < Decimal('-0.25'):
            sug = 'sell'
        rebalance.append({
            "ticker": it["ticker"],
            "target": float(target),
            "actual": float(actual),
            "diff": float(diff),
            "sug": sug,
        })

    context = {
        "items": items,
        "valor_actual": float(total_val),
        "total_invertido": float(total_inv),
        "rentab_total_eur": float(rentab_total_eur),
        "rentab_total_pct": float(rentab_total_pct),
        "rebalance": rebalance,
    }
    return render(request, "alpha_quantum/cartera.html", context)



from datetime import date
from rest_framework.views import APIView
from rest_framework.response import Response

class SparklineAPI(APIView):
    """
    Devuelve últimos 'days' precios para un ticker.
    Funciona tanto si PrecioHistorico tiene un campo 'ticker' (CharField)
    como si usa una FK 'accion' -> Accion (tu caso).
    """
    def get(self, request):
        ticker = (request.GET.get("ticker") or "").strip()
        days = int(request.GET.get("days", 30))
        if not ticker:
            return Response({"labels": [], "values": []})

        # ¿El modelo PrecioHistorico tiene un campo 'ticker'?
        has_ticker_field = any(
            getattr(f, "name", None) == "ticker"
            for f in getattr(PrecioHistorico, "_meta").get_fields()
        )

        if has_ticker_field:
            qs = PrecioHistorico.objects.filter(
                ticker__iexact=ticker
            ).order_by("-fecha")[:days]
        else:
            # Caso habitual: FK a Accion
            acc = Accion.objects.filter(
                user=request.user, ticker__iexact=ticker
            ).first()
            if not acc:
                return Response({"labels": [], "values": []})
            qs = PrecioHistorico.objects.filter(
                accion=acc
            ).order_by("-fecha")[:days]

        data = list(qs)[::-1]  # en orden cronológico ascendente
        labels = [
            (getattr(x, "fecha", date.today())).strftime("%Y-%m-%d")
            for x in data
        ]
        # El campo de precio en tu modelo es 'valor'
        values = [float(getattr(x, "valor", 0)) for x in data]

        return Response({"labels": labels, "values": values})



@login_required
def grafico_rentabilidad(request):
    user = request.user
    hoy = now().date()
    hace_6_meses = hoy - timedelta(days=180)

    # Obtenemos histórico de los últimos 6 meses
    historico = (
        HistoricoCartera.objects
        .filter(user=user, fecha__gte=hace_6_meses)
        .order_by("fecha")
        .values("fecha")
        .annotate(
            valor_total=Sum("valor_total"),
            invertido_total=Sum("invertido_total")
        )
    )

    fechas = []
    rentabilidades = []

    for registro in historico:
        fechas.append(registro["fecha"].strftime("%Y-%m-%d"))

        valor_total = registro["valor_total"] or Decimal("0")
        invertido_total = registro["invertido_total"] or Decimal("0")

        if invertido_total > 0:
            rentabilidad = ((valor_total - invertido_total) / invertido_total) * 100
        else:
            rentabilidad = 0

        rentabilidades.append(round(float(rentabilidad), 2))

    data = {
        "fechas": fechas,
        "rentabilidades": rentabilidades
    }

    return JsonResponse(data)

@login_required
def RentabilidadAPI(request):
    user = request.user

    historico = (
        HistoricoCartera.objects
        .filter(user=user)
        .order_by("fecha")
        .values("fecha")
        .annotate(
            valor_total=Sum("valor_total"),
            invertido_total=Sum("invertido_total")
        )
    )

    fechas = []
    rentabilidades = []

    for registro in historico:
        fechas.append(registro["fecha"].strftime("%Y-%m-%d"))

        valor_total = registro["valor_total"] or Decimal("0")
        invertido_total = registro["invertido_total"] or Decimal("0")

        if invertido_total > 0:
            rentabilidad = ((valor_total - invertido_total) / invertido_total) * 100
        else:
            rentabilidad = 0

        rentabilidades.append(round(float(rentabilidad), 2))

    return JsonResponse({
        "fechas": fechas,
        "rentabilidades": rentabilidades
    })


# ===========================
#        API Dashboard
# ===========================
class HistoricoCarteraAPI(APIView):
    def get(self, request):
        user = request.user
        dias = int(request.GET.get("dias", 365))
        hoy = date.today()
        desde = hoy - timedelta(days=dias)

        qs = HistoricoCartera.objects.filter(user=user, fecha__gte=desde).order_by("fecha")
        labels = [h.fecha.strftime("%Y-%m-%d") for h in qs]
        values = [float(h.valor - h.invertido) for h in qs]
        return Response({"labels": labels, "values": values})


def _position_on(user, ticker: str, cutoff) -> Decimal:
    """Acciones netas a la fecha (compras - ventas) <= cutoff."""
    qs = Transaccion.objects.filter(user=user, ticker__iexact=ticker, fecha__lte=cutoff)
    buys = qs.filter(tipo='BUY').aggregate(s=Sum('cantidad'))['s'] or Decimal('0')
    sells = qs.filter(tipo='SELL').aggregate(s=Sum('cantidad'))['s'] or Decimal('0')
    return Decimal(buys) - Decimal(sells)

class DashboardDataView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        user = request.user
        acciones = Cartera.objects.filter(user=user)

        total_invertido = Decimal("0")
        valor_actual_total = Decimal("0")
        historico = []
        top_ganadoras = []
        top_perdedoras = []

        for acc in acciones:
            try:
                precio_actual = obtener_precio_actual(acc.ticker)
                if precio_actual:
                    acc.precio_actual = precio_actual
                    acc.save(update_fields=["precio_actual"])
            except Exception as e:
                print(f"[DASHBOARD] Error actualizando {acc.ticker}: {e}")

            inversion_accion = acc.cantidad * acc.precio_compra
            valor_accion = acc.cantidad * (acc.precio_actual or acc.precio_compra)

            valor_actual = sum([accion.cantidad * obtener_precio_actual(accion.ticker) for accion in acciones])
            beneficio_neto = valor_actual - total_invertido
            rentabilidad_pct = (beneficio_neto / total_invertido * 100) if total_invertido > 0 else 0
            total_invertido += inversion_accion
            valor_actual_total += valor_accion

            rentabilidad = ((valor_accion - inversion_accion) / inversion_accion * 100) if inversion_accion > 0 else 0
            historico.append({
                "ticker": acc.ticker,
                "rentabilidad": float(round(rentabilidad, 2)),
                "valor_actual": float(round(valor_accion, 2)),
                'beneficio_neto': round(beneficio_neto, 2),
                'rentabilidad_pct': round(rentabilidad_pct, 2),
            })

        # Ordenar para top 3 ganadoras y perdedoras
        historico_ordenado = sorted(historico, key=lambda x: x["rentabilidad"], reverse=True)
        top_ganadoras = historico_ordenado[:3]
        top_perdedoras = sorted(historico, key=lambda x: x["rentabilidad"])[:3]

        rentabilidad_total = ((valor_actual_total - total_invertido) / total_invertido * 100) if total_invertido > 0 else 0

        data = {
            "total_invertido": float(round(total_invertido, 2)),
            "valor_actual_total": float(round(valor_actual_total, 2)),
            "rentabilidad_total": float(round(rentabilidad_total, 2)),
            "top_ganadoras": top_ganadoras,
            "top_perdedoras": top_perdedoras,
            "historico": historico,
        }
        return JsonResponse(data)

@login_required
def dividendos_api(request):
    """
    Devuelve dividendos desde BD (sin llamadas a API externas).
    Calcula importe = (monto_por_accion * acciones_en_fecha).
    Filtros: ?anio=YYYY&ticker=AAA
    """
    qs = Dividendo.objects.filter(accion__user=request.user).select_related('accion')

    anio = request.GET.get('anio')
    ticker = request.GET.get('ticker')
    if anio:
        qs = qs.filter(fecha__year=anio)
    if ticker:
        qs = qs.filter(accion__ticker__iexact=ticker)

    items = []
    total_periodo = Decimal('0')

    for d in qs.order_by('-fecha'):
        tk = d.accion.ticker
        qty_on_date = _position_on(request.user, tk, d.fecha)
        cobro = (Decimal(d.monto) * Decimal(qty_on_date)).quantize(Decimal('0.01'))
        items.append({
            "fecha": d.fecha.strftime("%Y-%m-%d"),
            "ticker": tk,
            "por_accion": float(d.monto),
            "acciones": float(qty_on_date),
            "importe": float(cobro),
        })
        total_periodo += cobro

    # agregado por ticker (opcional)
    por_ticker = {}
    for it in items:
        por_ticker.setdefault(it["ticker"], Decimal('0'))
        por_ticker[it["ticker"]] += Decimal(str(it["importe"]))

    por_ticker_list = [
        {"ticker": k, "total": float(v.quantize(Decimal('0.01')))}
        for k, v in sorted(por_ticker.items(), key=lambda x: x[0])
    ]

    return JsonResponse({
        "items": items,
        "total": float(total_periodo.quantize(Decimal('0.01'))),
        "por_ticker": por_ticker_list
    })


class CarteraAPIView(APIView):
    """Usada por el doughnut de distribución."""
    def get(self, request):
        acciones = Accion.objects.filter(user=request.user)

        # Refresco ligero de precios
        for a in acciones:
            nuevo_precio = obtener_precio_actual(a.ticker)
            if nuevo_precio is not None and nuevo_precio > 0:
                try:
                    a.precio_actual = Decimal(str(nuevo_precio))
                    a.save(update_fields=["precio_actual"])
                except (InvalidOperation, ValueError):
                    continue

        total_cartera = Decimal('0.0')
        for a in acciones:
            if a.precio_actual is not None:
                try:
                    total_cartera += Decimal(str(a.precio_actual)) * Decimal(str(a.cantidad))
                except (InvalidOperation, TypeError):
                    continue

        data = []
        for a in acciones:
            if a.precio_actual is None:
                continue
            try:
                precio_actual = Decimal(str(a.precio_actual))
                precio_compra = Decimal(str(a.precio_compra))
                cantidad = Decimal(str(a.cantidad))

                valor_total = precio_actual * cantidad
                invertido = precio_compra * cantidad
                rentab_eur = valor_total - invertido
                rentab_pct = (rentab_eur / invertido * Decimal('100')) if invertido > 0 else Decimal('0')
                pct_cartera = (valor_total / total_cartera * Decimal('100')) if total_cartera > 0 else Decimal('0')

                data.append({
                    "id": a.id,
                    "nombre": a.nombre,
                    "ticker": a.ticker,
                    "precio_compra": f"{precio_compra:.2f}",
                    "precio_actual": f"{precio_actual:.2f}",
                    "cantidad": int(cantidad),
                    "valor_total": f"{valor_total:.2f}",
                    "rentabilidad_eur": f"{rentab_eur:.2f}",
                    "rentabilidad_pct": f"{rentab_pct:.2f}",
                    "porcentaje_total": f"{pct_cartera:.2f}",
                })
            except Exception:
                continue

        return Response({"total_cartera": f"{total_cartera:.2f}", "acciones": data})


# ===========================
#     TRANSACCIONES (CSV)
# ===========================
@login_required
def transacciones_export_csv(request):
    import csv
    qs = Transaccion.objects.filter(user=request.user).order_by('fecha', 'id')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=transacciones.csv'
    writer = csv.writer(response)
    writer.writerow(['Fecha','Ticker','Tipo','Cantidad','Precio','Comision','Importe','P/L (aprox)','Rentabilidad %'])

    costo_avg, pos = {}, {}
    for tr in qs:
        tk = tr.ticker.upper()
        if tk not in costo_avg:
            costo_avg[tk] = 0.0; pos[tk] = 0.0
        pnl = 0.0
        rr  = 0.0
        if tr.tipo == 'BUY':
            total_cost = costo_avg[tk]*pos[tk] + float(tr.precio)*float(tr.cantidad) + float(tr.comision)
            pos[tk] += float(tr.cantidad)
            costo_avg[tk] = total_cost/pos[tk] if pos[tk] else 0.0
        elif tr.tipo == 'SELL':
            base_cost = costo_avg[tk] if pos[tk] > 0 else 0.0
            pnl = ((float(tr.precio)-base_cost) * float(tr.cantidad) - float(tr.comision))
            inv_base = base_cost * float(tr.cantidad)
            rr  = (pnl / inv_base * 100.0) if inv_base > 0 else 0.0
            pos[tk] = max(0.0, pos[tk]-float(tr.cantidad))
            if pos[tk] == 0:
                costo_avg[tk] = 0.0
        else:  # DIV
            pnl = float(tr.importe())

        writer.writerow([
            tr.fecha, tr.ticker, tr.get_tipo_display(), float(tr.cantidad), float(tr.precio),
            float(tr.comision), round(float(tr.importe()),2), round(pnl,2), round(rr,2)
        ])
    return response

def transacciones_view(request):
    qs = Transaccion.objects.filter(user=request.user)

    # filtros
    t = request.GET.get("ticker")
    anio = request.GET.get("anio")
    if t:
        qs = qs.filter(ticker__iexact=t)
    if anio:
        qs = qs.filter(fecha__year=anio)

    # P/L realizado simple por ticker usando coste medio
    costo_avg, pos = {}, {}
    pnl_map, rr_map, realized = {}, {}, 0.0  # <-- añadimos rr_map

    for tr in qs.order_by('fecha', 'id'):
        tk = tr.ticker.upper()
        if tk not in costo_avg:
            costo_avg[tk] = 0.0
            pos[tk] = 0.0

        if tr.tipo == 'BUY':
            # nuevo coste medio ponderado
            total_cost = costo_avg[tk] * pos[tk] + float(tr.precio) * float(tr.cantidad) + float(tr.comision)
            pos[tk] += float(tr.cantidad)
            costo_avg[tk] = total_cost / pos[tk] if pos[tk] else 0.0
            pnl_map[tr.id] = 0.0
            rr_map[tr.id]  = 0.0
        elif tr.tipo == 'SELL':
            # si no hay posición previa, tratamos como cierre sin base (no debería pasar)
            base_cost = costo_avg[tk] if pos[tk] > 0 else 0.0
            pnl = (float(tr.precio) - base_cost) * float(tr.cantidad) - float(tr.comision)
            pnl_map[tr.id] = round(pnl, 2)
            inv_base = base_cost * float(tr.cantidad)
            rr_map[tr.id]  = round((pnl / inv_base * 100.0), 2) if inv_base > 0 else 0.0
            realized += pnl
            # reducimos posición
            pos[tk] = max(0.0, pos[tk] - float(tr.cantidad))
            if pos[tk] == 0:
                costo_avg[tk] = 0.0
        else:  # DIV
            pnl_map[tr.id] = float(tr.importe())
            rr_map[tr.id]  = 0.0

    return render(request, "alpha_quantum/transacciones.html", {
        "items": qs.order_by('-fecha', '-id'),
        "pnl_map": pnl_map,
        "rr_map": rr_map,                # <-- pasa rentabilidad por operación
        "realized_total": round(realized, 2),
    })

# ===========================
#  FORMULARIOS (MODALES)
# ===========================
@login_required
def dividendo_crear(request):
    if request.method == "POST":
        f = DividendoForm(request.POST)
        if f.is_valid():
            obj = f.save(commit=False)
            if obj.accion.user != request.user:
                messages.error(request, "Esa acción no es tuya.")
                return redirect("dashboard")
            obj.save()
            messages.success(request, "💸 Dividendo guardado.")
    return redirect("dashboard")

@login_required
def dividendo_editar(request, pk):
    d = get_object_or_404(Dividendo, pk=pk, accion__user=request.user)
    if request.method == "POST":
        f = DividendoForm(request.POST, instance=d)
        if f.is_valid():
            f.save()
            messages.success(request, "💾 Dividendo actualizado.")
            return redirect("dashboard")
    else:
        f = DividendoForm(instance=d)
    return render(request, "alpha_quantum/dashboard/_modal_dividendo_form.html", {"form": f, "edit": True, "obj": d})

@login_required
def dividendo_borrar(request, pk):
    d = get_object_or_404(Dividendo, pk=pk, accion__user=request.user)
    d.delete()
    messages.success(request, "🗑️ Dividendo eliminado.")
    return redirect("dashboard")

@login_required
def transaccion_crear(request):
    if request.method == "POST":
        f = TransaccionForm(request.POST, user=request.user)
        if f.is_valid():
            obj = f.save(commit=False)
            obj.user = request.user
            obj.ticker = obj.ticker.upper().strip()
            obj.save()  # las señales actualizan la cartera
            messages.success(request, "📈 Transacción guardada.")
            return redirect("dashboard")
        else:
            messages.error(request, "Revisa el formulario de transacción.")
    else:
        f = TransaccionForm(user=request.user)
    return render(request, "alpha_quantum/dashboard/_modal_transaccion_form.html", {"form": f})


@login_required
def transaccion_editar(request, pk):
    t = get_object_or_404(Transaccion, pk=pk, user=request.user)
    if request.method == "POST":
        f = TransaccionForm(request.POST, instance=t, user=request.user)
        if f.is_valid():
            obj = f.save(commit=False)
            obj.user = request.user
            obj.ticker = obj.ticker.upper().strip()
            obj.save()  # señales -> actualiza cartera
            messages.success(request, "💾 Transacción actualizada.")
            return redirect("dashboard")
        else:
            messages.error(request, "Revisa el formulario.")
    else:
        f = TransaccionForm(instance=t, user=request.user)
    return render(request, "alpha_quantum/dashboard/_modal_transaccion_form.html", {"form": f, "edit": True, "obj": t})


@login_required
def transaccion_borrar(request, pk):
    t = get_object_or_404(Transaccion, pk=pk, user=request.user)
    ticker = t.ticker
    user = t.user
    t.delete()  # señales -> actualiza cartera
    messages.success(request, "🗑️ Transacción eliminada.")
    return redirect("dashboard")

#  WATCHLISTS (múltiples)
# ===========================

import csv
from typing import Optional, List

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Q, Prefetch
from django.http import HttpResponse, JsonResponse, HttpRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render

# ── Modelos
from .models.watchlist import Watchlist, WatchlistLista

# ── Formularios (si los tienes). Si no, el código usa POST plano.
try:
    from .forms import WatchlistForm  # type: ignore
except Exception:
    WatchlistForm = None  # fallback si no existe

# ── Utilidades para datos de mercado y lógica de recomendación
try:
    from .utils import obtener_datos_finnhub, calcular_upside, generar_recomendacion  # type: ignore
except Exception:
    # Fallbacks mínimos por si no tienes utils aún
    def obtener_datos_finnhub(ticker: str) -> Optional[dict]:
        return None

    def calcular_upside(valor_objetivo, precio_actual) -> Optional[float]:
        try:
            vo = float(valor_objetivo or 0)
            pa = float(precio_actual or 0)
            if vo and pa:
                return round((vo - pa) / pa * 100, 4)
            return None
        except Exception:
            return None

    def generar_recomendacion(upside: Optional[float]) -> Optional[str]:
        if upside is None:
            return None
        if upside > 20:
            return "COMPRAR"
        if upside < -10:
            return "ESPERAR"  # o "VENDER" si prefieres
        return "REVISAR"


# ===========================
#   HELPERS
# ===========================

def _items_filtrados_qs(user, q: str, estado: str, orden: str):
    """Construye el queryset de items filtrado y ordenado."""
    ordenar_map = {
        "ticker": "ticker", "-ticker": "-ticker",
        "upside": "upside", "-upside": "-upside",
        "precio": "precio_actual", "-precio": "-precio_actual",
        "per": "per", "-per": "-per",
    }

    qs = Watchlist.objects.filter(user=user)
    if q:
        qs = qs.filter(Q(ticker__icontains=q) | Q(nombre__icontains=q))
    if estado in {"COMPRAR", "REVISAR", "ESPERAR"}:
        qs = qs.filter(recomendacion=estado)
    qs = qs.order_by(ordenar_map.get(orden, "ticker"))
    return qs


def _accion_to_dict(a: Watchlist) -> dict:
    return {
        "id": a.id,
        "ticker": a.ticker,
        "nombre": a.nombre,
        "precio_actual": float(a.precio_actual or 0),
        "valor_objetivo": float(a.valor_objetivo or 0),
        "upside": float(a.upside) if a.upside is not None else None,
        "per": a.per,
        "max_52s": a.max_52s,
        "min_52s": a.min_52s,
        "recomendacion": a.recomendacion or "N/A",
    }


# ===========================
# WATCHLISTS (overview apilado)
# ===========================
import csv
from typing import Optional, List

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Q
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render

from .models.watchlist import Watchlist, WatchlistLista

# (Opcional) si tienes un form, úsalo; si no, el código trabaja con POST plano.
try:
    from .forms import WatchlistForm  # type: ignore
except Exception:
    WatchlistForm = None  # fallback

# Utilidades externas; fallbacks mínimos si no existen.
try:
    from .utils import obtener_datos_finnhub, calcular_upside, generar_recomendacion  # type: ignore
except Exception:
    def obtener_datos_finnhub(ticker: str):
        return None

    def calcular_upside(vo, pa):
        try:
            vo, pa = float(vo or 0), float(pa or 0)
            return round((vo - pa) / pa * 100, 4) if vo and pa else None
        except Exception:
            return None

    def generar_recomendacion(upside):
        if upside is None:
            return None
        if upside > 20:
            return "COMPRAR"
        if upside < -10:
            return "ESPERAR"
        return "REVISAR"


# ---------------------------
# Helpers
# ---------------------------
def _items_queryset_base(user, q: str, estado: str, orden: str):
    """QS base con filtros y orden para prefetch (Django lo partirá por lista_id)."""
    ordenar_map = {
        "ticker": "ticker",
        "-ticker": "-ticker",
        "upside": "upside",
        "-upside": "-upside",
        "precio": "precio_actual",
        "-precio": "-precio_actual",
        "per": "per",
        "-per": "-per",
    }
    qs = (
        Watchlist.objects.filter(user=user)
        .only(
            "id",
            "lista_id",
            "ticker",
            "nombre",
            "precio_actual",
            "valor_objetivo",
            "upside",
            "per",
            "max_52s",
            "min_52s",
            "recomendacion",
        )
        .order_by(ordenar_map.get(orden, "ticker"))
    )
    if q:
        qs = qs.filter(Q(ticker__icontains=q) | Q(nombre__icontains=q))
    if estado in {"COMPRAR", "REVISAR", "ESPERAR"}:
        qs = qs.filter(recomendacion=estado)
    return qs


# ---------------------------
# Overview apilado
# ---------------------------
@login_required
def ver_watchlists(request: HttpRequest):
    """
    Muestra TODAS las watchlists del usuario, apiladas, con métricas (precio, 52s, PER, etc.).
    """
    q = (request.GET.get("q") or "").strip()
    estado = request.GET.get("estado") or ""
    orden = request.GET.get("orden") or "ticker"

    items_qs = _items_queryset_base(request.user, q, estado, orden)

    listas = (
        WatchlistLista.objects.filter(user=request.user)
        .order_by("titulo")
        .prefetch_related(Prefetch("items", queryset=items_qs, to_attr="items_filtrados"))
    )

    total_over, total_under = 0, 0
    listas_ctx: List[dict] = []

    for l in listas:
        acciones = []
        for a in getattr(l, "items_filtrados", []):
            if a.upside is not None:
                if a.upside > 0:
                    total_under += 1
                elif a.upside < 0:
                    total_over += 1
            acciones.append(
                {
                    "id": a.id,
                    "ticker": a.ticker,
                    "nombre": a.nombre,
                    "precio_actual": float(a.precio_actual or 0),
                    "valor_objetivo": float(a.valor_objetivo or 0)
                    if a.valor_objetivo is not None
                    else None,
                    "upside": float(a.upside) if a.upside is not None else None,
                    "per": a.per,
                    "max_52s": a.max_52s,
                    "min_52s": a.min_52s,
                    "recomendacion": a.recomendacion or "N/A",
                }
            )
        listas_ctx.append(
            {
                "id": l.id,
                "titulo": l.titulo,
                "descripcion": l.descripcion,
                "count": len(acciones),
                "acciones": acciones,
            }
        )

    return render(
        request,
        "alpha_quantum/watchlist.html",
        {
            "listas": listas_ctx,
            "stats": {"over": total_over, "under": total_under},
            "filtros": {"q": q, "estado": estado, "orden": orden},
        },
    )


# ---------------------------
# Crear lista
# ---------------------------
@login_required
def crear_watchlist(request: HttpRequest):
    if request.method != "POST":
        return redirect("ver_watchlists")
    titulo = (request.POST.get("titulo") or "").strip()
    descripcion = (request.POST.get("descripcion") or "").strip() or None
    if not titulo:
        messages.error(request, "Debes indicar un título.")
        return redirect("ver_watchlists")
    try:
        WatchlistLista.objects.create(
            user=request.user, titulo=titulo, descripcion=descripcion
        )
        messages.success(request, f'Lista “{titulo}” creada.')
    except IntegrityError:
        messages.warning(request, f'Ya existe una lista con el título “{titulo}”.')
    return redirect("ver_watchlists")


# ---------------------------
# Añadir item (siempre a la lista correcta)
# ---------------------------
@login_required
@transaction.atomic
def añadir_watchlist(request: HttpRequest, lista_id: int):
    """
    Guarda SIEMPRE en la lista correcta.
    - Lee 'lista_id' del path y acepta 'lista_id' oculto en el POST (por seguridad).
    - Permite el mismo ticker en distintas listas (unique por user+lista+ticker).
    """
    # Permite que un modal envíe el hidden lista_id
    post_lista_id = request.POST.get("lista_id")
    if post_lista_id:
        try:
            lista_id = int(post_lista_id)
        except Exception:
            pass

    lista = get_object_or_404(WatchlistLista, pk=lista_id, user=request.user)

    if request.method != "POST":
        messages.info(request, "Nada que guardar.")
        return redirect("ver_watchlists")

    # Si tienes formulario, podrías usarlo; mantenemos ruta POST plano para robustez
    ticker = (request.POST.get("ticker") or "").upper().strip()
    nombre = (request.POST.get("nombre") or "").strip() or None
    valor_objetivo_raw = (request.POST.get("valor_objetivo") or "").strip()

    if not ticker:
        messages.error(request, "Debes indicar un ticker.")
        return redirect("ver_watchlists")

    obj, created = Watchlist.objects.get_or_create(
        user=request.user, lista=lista, ticker=ticker, defaults={"nombre": nombre}
    )

    if not created and nombre:
        obj.nombre = nombre

    if valor_objetivo_raw:
        try:
            obj.valor_objetivo = float(valor_objetivo_raw)
        except Exception:
            messages.warning(request, "El valor objetivo no es válido. Se ignora.")

    datos = obtener_datos_finnhub(ticker)
    if datos:
        obj.precio_actual = datos.get("precio_actual")
        obj.per = datos.get("per")
        obj.max_52s = datos.get("max_52s")
        obj.min_52s = datos.get("min_52s")

    if obj.valor_objetivo and obj.precio_actual:
        obj.upside = calcular_upside(obj.valor_objetivo, obj.precio_actual)
        obj.recomendacion = generar_recomendacion(obj.upside)

    obj.save()

    if created:
        messages.success(request, f'✅ {ticker} añadida a “{lista.titulo}”.')
    else:
        messages.info(
            request, f'ℹ️ {ticker} ya estaba en “{lista.titulo}”, se actualizó su información.'
        )

    return redirect("ver_watchlists")


# ---------------------------
# Editar / eliminar item
# ---------------------------
@login_required
def editar_accion_watchlist(request: HttpRequest, lista_id: int, item_id: int):
    lista = get_object_or_404(WatchlistLista, pk=lista_id, user=request.user)
    accion = get_object_or_404(Watchlist, pk=item_id, user=request.user, lista=lista)

    if request.method == "POST":
        if WatchlistForm:
            form = WatchlistForm(request.POST, instance=accion)
            if form.is_valid():
                acc = form.save(commit=False)
                datos = obtener_datos_finnhub(acc.ticker)
                if datos:
                    acc.precio_actual = datos.get("precio_actual")
                    acc.per = datos.get("per")
                    acc.max_52s = datos.get("max_52s")
                    acc.min_52s = datos.get("min_52s")
                if acc.valor_objetivo and acc.precio_actual:
                    acc.upside = calcular_upside(acc.valor_objetivo, acc.precio_actual)
                    acc.recomendacion = generar_recomendacion(acc.upside)
                acc.save()
                messages.success(request, f"✅ {acc.ticker} actualizada.")
                return redirect("ver_watchlists")
        else:
            # POST plano
            accion.nombre = (request.POST.get("nombre") or "").strip() or accion.nombre
            vo = (request.POST.get("valor_objetivo") or "").strip()
            if vo:
                try:
                    accion.valor_objetivo = float(vo)
                except Exception:
                    messages.warning(request, "Valor objetivo inválido. Se ignora.")
            datos = obtener_datos_finnhub(accion.ticker)
            if datos:
                accion.precio_actual = datos.get("precio_actual")
                accion.per = datos.get("per")
                accion.max_52s = datos.get("max_52s")
                accion.min_52s = datos.get("min_52s")
            if accion.valor_objetivo and accion.precio_actual:
                accion.upside = calcular_upside(
                    accion.valor_objetivo, accion.precio_actual
                )
                accion.recomendacion = generar_recomendacion(accion.upside)
            accion.save()
            messages.success(request, f"✅ {accion.ticker} actualizada.")
            return redirect("ver_watchlists")

    form = WatchlistForm(instance=accion) if WatchlistForm else None
    return render(
        request,
        "alpha_quantum/editar_watchlist.html",
        {"form": form, "accion": accion, "lista": lista},
    )


@login_required
def eliminar_watchlist(request: HttpRequest, lista_id: int, item_id: int):
    lista = get_object_or_404(WatchlistLista, pk=lista_id, user=request.user)
    accion = get_object_or_404(Watchlist, pk=item_id, user=request.user, lista=lista)
    if request.method == "POST":
        ticker = accion.ticker
        accion.delete()
        messages.success(request, f"🗑️ {ticker} eliminada de “{lista.titulo}”.")
        return redirect("ver_watchlists")
    return render(
        request,
        "alpha_quantum/confirmar_eliminar.html",
        {"accion": accion, "lista": lista},
    )


# ---------------------------
# Refrescos
# ---------------------------
@login_required
def refrescar_watchlist(request: HttpRequest, lista_id: int):
    lista = get_object_or_404(WatchlistLista, pk=lista_id, user=request.user)
    items = Watchlist.objects.filter(user=request.user, lista=lista)
    count = 0
    for it in items:
        datos = obtener_datos_finnhub(it.ticker)
        if datos:
            it.precio_actual = datos.get("precio_actual")
            it.per = datos.get("per")
            it.max_52s = datos.get("max_52s")
            it.min_52s = datos.get("min_52s")
            if it.valor_objetivo and it.precio_actual:
                it.upside = calcular_upside(it.valor_objetivo, it.precio_actual)
                it.recomendacion = generar_recomendacion(it.upside)
            it.save()
            count += 1
    messages.info(request, f"🔄 Refrescadas {count} acciones de “{lista.titulo}”.")
    return redirect("ver_watchlists")


@login_required
def refrescar_watchlist_item(request: HttpRequest, lista_id: int, item_id: int):
    lista = get_object_or_404(WatchlistLista, pk=lista_id, user=request.user)
    it = get_object_or_404(Watchlist, pk=item_id, user=request.user, lista=lista)
    datos = obtener_datos_finnhub(it.ticker)
    if datos:
        it.precio_actual = datos.get("precio_actual")
        it.per = datos.get("per")
        it.max_52s = datos.get("max_52s")
        it.min_52s = datos.get("min_52s")
        if it.valor_objetivo and it.precio_actual:
            it.upside = calcular_upside(it.valor_objetivo, it.precio_actual)
            it.recomendacion = generar_recomendacion(it.upside)
        it.save()
        messages.success(request, f"🔄 {it.ticker} refrescada.")
    else:
        messages.warning(request, f"No se pudo refrescar {it.ticker}.")
    return redirect("ver_watchlists")


# ---------------------------
# Exportar CSV
# ---------------------------
@login_required
def exportar_watchlist_csv(request: HttpRequest, lista_id: int) -> HttpResponse:
    lista = get_object_or_404(WatchlistLista, pk=lista_id, user=request.user)
    items = Watchlist.objects.filter(user=request.user, lista=lista).order_by("ticker")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="watchlist_{lista.titulo}.csv"'
    writer = csv.writer(response, delimiter=";")
    writer.writerow(
        [
            "Ticker",
            "Nombre",
            "Precio",
            "Objetivo",
            "Upside(%)",
            "PER",
            "Max52s",
            "Min52s",
            "Recomendación",
        ]
    )
    for it in items:
        writer.writerow(
            [
                it.ticker,
                it.nombre or "",
                f"{it.precio_actual or ''}",
                f"{it.valor_objetivo or ''}",
                f"{it.upside or ''}",
                f"{it.per or ''}",
                f"{it.max_52s or ''}",
                f"{it.min_52s or ''}",
                it.recomendacion or "",
            ]
        )
    return response


# ---------------------------
# Autocompletar
# ---------------------------
@login_required
def autocompletar_ticker(request: HttpRequest) -> JsonResponse:
    q = (request.GET.get("q") or "").upper().strip()
    if not q:
        return JsonResponse({"suggestions": []})
    s = (
        Watchlist.objects.filter(user=request.user, ticker__startswith=q)
        .values_list("ticker", flat=True)
        .order_by("ticker")
        .distinct()[:10]
    )
    return JsonResponse({"suggestions": list(s)})

@login_required
def eliminar_watchlist_lista(request, lista_id: int):
    """
    Elimina una watchlist completa (y, por cascada, todos sus items).
    Solo acepta POST (viene del modal de confirmación).
    """
    lista = get_object_or_404(WatchlistLista, pk=lista_id, user=request.user)

    if request.method == "POST":
        titulo = lista.titulo
        lista.delete()  # CASCADE se lleva sus items
        messages.success(request, f"🗑️ Lista “{titulo}” eliminada.")
        return redirect("ver_watchlists")

    # Si te llegan por GET, simplemente vuelve a la página
    messages.info(request, "Acción cancelada.")
    return redirect("ver_watchlists")
# ---------------------------
# Compat (rutas antiguas)
# ---------------------------
@login_required
def ver_watchlist(request: HttpRequest, lista_id: Optional[int] = None) -> HttpResponseRedirect:
    """Alias por compatibilidad: redirige al overview apilado."""
    return redirect("ver_watchlists")


# ===========================
#       AUTENTICACIÓN
# ===========================
def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('index')
    else:
        form = UserCreationForm()
    return render(request, 'alpha_quantum/register.html', {'form': form})

def user_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        return redirect('dashboard')
    return render(request, 'alpha_quantum/registration/login.html', {'form': form})

def user_register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = CustomUserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect('dashboard')
    return render(request, 'alpha_quantum/registration/register.html', {'form': form})

def user_logout(request):
    logout(request)
    return render(request, 'alpha_quantum/registration/logged_out.html')


# ===========================
#       CALENDARIO
# ===========================
@login_required
def calendario(request):
    user = request.user
    tipo_evento = request.GET.get("tipo_evento")
    filtro_tiempo = request.GET.get("tiempo")
    filtro_ticker = request.GET.get("ticker")

    eventos = EventoFinanciero.objects.filter(user=user)

    if tipo_evento and tipo_evento != "todos":
        eventos = eventos.filter(tipo_evento=tipo_evento)
    if filtro_ticker:
        eventos = eventos.filter(ticker__icontains=filtro_ticker)

    hoy = date.today()
    if filtro_tiempo == '30_dias':
        eventos = eventos.filter(fecha__gte=hoy - timedelta(days=30))
    elif filtro_tiempo == '3_meses':
        eventos = eventos.filter(fecha__gte=hoy - timedelta(days=90))
    elif filtro_tiempo == '6_meses':
        eventos = eventos.filter(fecha__gte=hoy - timedelta(days=180))
    elif filtro_tiempo == '1_ano':
        eventos = eventos.filter(fecha__gte=hoy - timedelta(days=365))

    eventos = eventos.order_by('-fecha')

    return render(request, 'alpha_quantum/calendario.html', {
        'eventos': eventos,
        'tipo_actual': tipo_evento,
        'tiempo_actual': filtro_tiempo,
        'ticker_actual': filtro_ticker,
    })

def calendario_financiero(request):
    tipo = request.GET.get('tipo')
    eventos = EventoFinanciero.objects.filter(user=request.user)
    if tipo:
        eventos = eventos.filter(tipo_evento=tipo)
    return render(request, "calendario.html", {"eventos": eventos})


# ===========================
#        NOTICIAS
# ===========================
FINNHUB_API_KEY = 'd1vp4b1r01qmbi8pd5e0d1vp4b1r01qmbi8pd5eg'

@login_required
def noticias(request):
    categoria = request.GET.get("categoria", "general")
    categorias_validas = ["general", "forex", "crypto", "merger", "technology"]
    if categoria not in categorias_validas:
        categoria = "general"
    url = f"https://finnhub.io/api/v1/news?category={categoria}&token={FINNHUB_API_KEY}"
    response = requests.get(url)
    noticias = response.json() if response.status_code == 200 else []
    return render(request, "alpha_quantum/noticias.html", {
        "noticias": noticias,
        "categoria_actual": categoria,
        "categorias": categorias_validas
    })


# ===========================
#     ANÁLISIS FUNDAMENTAL
# ===========================
# -*- coding: utf-8 -*-

import requests
from django.conf import settings
from django.shortcuts import render

from .utils import (
    obtener_precio_actual,
    obtener_datos_fundamentales_alpha_vantage,
)

from .models import Accion
# importa tus modelos de watchlist (como los nombraste)
from .models.watchlist import WatchlistLista

TD_KEY = getattr(settings, "TWELVE_DATA_API_KEY", None)
FH_KEY = getattr(settings, "FINNHUB_API_KEY", None)
AV_KEY = getattr(settings, "ALPHA_VANTAGE_API_KEY", None)


# ------------------- helpers -------------------

def _serie_precios_twelvedata(ticker: str, days: int = 60):
    """Cierres diarios (últimos `days`) con TwelveData"""
    if not TD_KEY:
        return []
    try:
        url = "https://api.twelvedata.com/time_series"
        params = {"symbol": ticker, "interval": "1day", "outputsize": days, "apikey": TD_KEY}
        r = requests.get(url, params=params, timeout=12)
        dj = r.json()
        values = list(reversed(dj.get("values") or []))
        return [{"t": v["datetime"], "c": float(v["close"])} for v in values]
    except Exception:
        return []


def _av_get(function: str, ticker: str):
    if not AV_KEY:
        return {}
    try:
        url = "https://www.alphavantage.co/query"
        r = requests.get(url, params={"function": function, "symbol": ticker, "apikey": AV_KEY}, timeout=15)
        return r.json() or {}
    except Exception:
        return {}


def _to_f(x, scale=1.0):
    try:
        return float(x) / scale
    except Exception:
        return None


def _income_quarterly(ticker: str, n: int = 8):
    """INCOME_STATEMENT (quarterlyReports) → labels, revenue(M), gp, opInc, netInc"""
    data = _av_get("INCOME_STATEMENT", ticker)
    rows = data.get("quarterlyReports") or []
    rows = rows[:n][::-1]  # últimos n, cronológico
    labels, revenue, gp, opi, ni = [], [], [], [], []
    for r in rows:
        labels.append(r.get("fiscalDateEnding"))
        revenue.append(_to_f(r.get("totalRevenue"), 1e6))
        gp.append(_to_f(r.get("grossProfit"), 1e6))
        opi.append(_to_f(r.get("operatingIncome"), 1e6))
        ni.append(_to_f(r.get("netIncome"), 1e6))
    return labels, revenue, gp, opi, ni


def _earnings_eps_quarterly(ticker: str, n: int = 8):
    """EARNINGS (quarterlyEarnings) → labels, reportedEPS"""
    data = _av_get("EARNINGS", ticker)
    rows = data.get("quarterlyEarnings") or []
    rows = rows[:n][::-1]
    labels, eps = [], []
    for r in rows:
        labels.append(r.get("reportedDate"))
        eps.append(_to_f(r.get("reportedEPS")))
    return labels, eps


def _balance_quarterly(ticker: str, n: int = 8):
    """BALANCE_SHEET (quarterlyReports) → labels, activos(B), pasivos(B)"""
    data = _av_get("BALANCE_SHEET", ticker)
    rows = data.get("quarterlyReports") or []
    rows = rows[:n][::-1]
    labels, assets, liab = [], [], []
    for r in rows:
        labels.append(r.get("fiscalDateEnding"))
        assets.append(_to_f(r.get("totalAssets"), 1e9))
        liab.append(_to_f(r.get("totalLiabilities"), 1e9))
    return labels, assets, liab


def _margins_from_income(labels, revenue_m, gp_m, opi_m, ni_m):
    """Devuelve % márgenes (bruto, operativo, neto) a partir de income en millones"""
    bruto, oper, neto = [], [], []
    for i in range(len(labels)):
        rev = revenue_m[i] or 0
        if rev:
            bruto.append(round((gp_m[i] or 0) / rev * 100, 2))
            oper.append(round((opi_m[i] or 0) / rev * 100, 2))
            neto.append(round((ni_m[i] or 0) / rev * 100, 2))
        else:
            bruto.append(None); oper.append(None); neto.append(None)
    return labels, bruto, oper, neto


def _fundamentales_finnhub(ticker: str):
    """Fallback de perfil + métricas si AV no responde"""
    if not FH_KEY:
        return {}, {}, None, None

    perfil, indicadores = {}, {}
    nombre, moneda = None, None
    try:
        rp = requests.get(
            "https://finnhub.io/api/v1/stock/profile2",
            params={"symbol": ticker, "token": FH_KEY},
            timeout=12,
        )
        if rp.status_code == 200:
            p = rp.json() or {}
            perfil = {
                "sector": p.get("finnhubIndustry"),
                "industria": p.get("finnhubIndustry"),
                "pais": p.get("country"),
                "empleados": p.get("employeeTotal"),
                "deuda_equity": None,
                "peg": None,
            }
            nombre = p.get("name")
            moneda = p.get("currency")

        rm = requests.get(
            "https://finnhub.io/api/v1/stock/metric",
            params={"symbol": ticker, "metric": "all", "token": FH_KEY},
            timeout=12,
        )
        if rm.status_code == 200:
            m = (rm.json() or {}).get("metric", {})
            indicadores = {
                "per": m.get("peInclExtraTTM"),
                "roe": m.get("roeTTM"),
                "roi": m.get("roiTTM"),
                "deuda_total": m.get("totalDebt"),
                "beneficio_neto": m.get("netProfitAnnual"),
                "valor_intrinseco": None,
            }
    except Exception:
        pass
    return perfil, indicadores, nombre, moneda


# ------------------- view -------------------

def analisis_fundamental(request):
    ticker = (request.GET.get("ticker") or "AAPL").upper().strip()

    # Precio + serie para el gráfico
    try:
        precio = float(obtener_precio_actual(ticker) or 0)
    except Exception:
        precio = None
    ohlcv = _serie_precios_twelvedata(ticker, days=60)

    # Perfil/indicadores (Overview AV con fallback Finnhub)
    datos_av = obtener_datos_fundamentales_alpha_vantage(ticker)
    error_msg = None

    perfil = {"sector": None, "industria": None, "pais": None, "empleados": None, "deuda_equity": None, "peg": None}
    indicadores = {"per": None, "roe": None, "roi": None, "deuda_total": None, "beneficio_neto": None, "valor_intrinseco": None}
    nombre, moneda = None, "USD"

    if datos_av and not datos_av.get("error"):
        nombre = datos_av.get("nombre")
        perfil.update({
            "sector": datos_av.get("sector"),
            "industria": datos_av.get("industria"),
            "pais": datos_av.get("pais"),
            "empleados": datos_av.get("empleados"),
            "deuda_equity": datos_av.get("deuda_equity"),
            "peg": datos_av.get("PEG"),
        })
        indicadores.update({
            "per": datos_av.get("PER"),
            "roe": datos_av.get("ROE"),
            "roi": datos_av.get("ROA"),  # proxy ROI
        })
    else:
        if datos_av and datos_av.get("error"):
            error_msg = datos_av["error"]
        else:
            error_msg = "No se pudo obtener OVERVIEW en Alpha Vantage. Intento datos alternativos."
        pf, ind, nombre_fh, moneda_fh = _fundamentales_finnhub(ticker)
        perfil.update({k: v for k, v in pf.items() if v is not None})
        indicadores.update({k: v for k, v in ind.items() if v is not None})
        if nombre_fh: nombre = nombre_fh
        if moneda_fh: moneda = moneda_fh

    # -------- datos para las gráficas (AV) --------
    rev_labels, rev_values, gp_m, opi_m, ni_m = _income_quarterly(ticker, n=8)
    eps_labels, eps_values = _earnings_eps_quarterly(ticker, n=8)
    bal_labels, activos_b, pasivos_b = _balance_quarterly(ticker, n=8)
    marg_labels, margen_bruto, margen_oper, margen_neto = _margins_from_income(rev_labels, rev_values, gp_m, opi_m, ni_m)

    # -------- sidebar: cartera y watchlists --------
    holdings = []
    wlists = []
    if request.user.is_authenticated:
        for a in Accion.objects.filter(user=request.user).order_by("ticker"):
            holdings.append({
                "ticker": a.ticker,
                "nombre": getattr(a, "nombre", "") or a.ticker,
                "precio": float(a.precio_actual) if getattr(a, "precio_actual", None) else None,
                "cantidad": float(a.cantidad or 0),
            })
        for lst in WatchlistLista.objects.filter(user=request.user).prefetch_related("items"):
            wlists.append({
                "titulo": lst.titulo,
                "items": [
                    {
                        "ticker": it.ticker,
                        "nombre": it.nombre or it.ticker,
                        "precio": float(it.precio_actual) if it.precio_actual is not None else None,
                    }
                    for it in lst.items.all().order_by("ticker")
                ],
            })

    ctx = {
        "ticker": ticker,
        "datos": {"ticker": ticker, "nombre": nombre or ticker, "precio": precio, "moneda": moneda},
        "indicadores": indicadores,
        "perfil": perfil,
        "ohlcv": ohlcv,

        # charts
        "revenue_labels": rev_labels,        # fechas
        "revenue_values": rev_values,        # millones
        "eps_labels": eps_labels,
        "eps_values": eps_values,
        "margin_labels": marg_labels,
        "margen_bruto": margen_bruto,
        "margen_oper": margen_oper,
        "margen_neto": margen_neto,
        "balance_labels": bal_labels,
        "activos": activos_b,                # billones
        "pasivos": pasivos_b,                # billones

        # sidebar
        "holdings": holdings,
        "wlists": wlists,

        "error_msg": error_msg,
    }
    return render(request, "alpha_quantum/fundamental.html", ctx)


# ===========================
#         CASHFLOW
# ===========================
from collections import defaultdict
@login_required
def cashflow_dashboard(request):
    user = request.user

    registros = CashFlow.objects.filter(user=user).order_by('-date')
    ingresos = registros.filter(category='ingreso')
    gastos = registros.filter(category='gasto')

    total_ingresos = sum(i.amount for i in ingresos)
    total_gastos = sum(g.amount for g in gastos)

    propiedades = PropiedadAlquiler.objects.filter(user=user)
    ingresos_alquiler = sum(p.ingreso_mensual for p in propiedades)
    gastos_alquiler = sum(p.hipoteca_mensual + p.gastos_mantenimiento for p in propiedades)

    prestamos = Prestamo.objects.filter(user=user)
    gastos_prestamos = sum(p.cuota_mensual for p in prestamos)

    beneficio_total_propiedades = sum(p.beneficio_neto for p in propiedades)
    balance_pendiente_prestamos = sum(p.balance_actual for p in prestamos)

    balance = Decimal(total_ingresos) - Decimal(total_gastos) + Decimal(ingresos_alquiler) - Decimal(gastos_alquiler) - Decimal(gastos_prestamos)

    ingresos_por_mes = defaultdict(float)
    gastos_por_mes = defaultdict(float)

    for r in registros:
        mes = r.date.strftime('%Y-%m')
        if r.category == 'ingreso':
            ingresos_por_mes[mes] += float(r.amount)
        elif r.category == 'gasto':
            gastos_por_mes[mes] += float(r.amount)

    fecha_inicio = datetime.today().replace(day=1)
    meses_simulados = 36
    todos_meses = []
    for i in range(meses_simulados):
        mes = fecha_inicio.month + i
        año = fecha_inicio.year + (mes - 1) // 12
        mes_final = ((mes - 1) % 12) + 1
        fecha_mes = datetime(año, mes_final, 1)
        todos_meses.append(fecha_mes.strftime('%Y-%m'))

    hipotecas_por_mes = defaultdict(float)
    prestamos_por_mes = defaultdict(float)

    for propiedad in propiedades:
        cuota = float(propiedad.hipoteca_mensual)
        for i in range(propiedad.meses_restantes_hipoteca):
            if i < meses_simulados:
                clave = todos_meses[i]
                hipotecas_por_mes[clave] += cuota

    for prestamo in prestamos:
        cuota = float(prestamo.cuota_mensual)
        for i in range(prestamo.meses_restantes):
            if i < meses_simulados:
                clave = todos_meses[i]
                prestamos_por_mes[clave] += cuota

    valores_ingresos, valores_gastos, valores_balance = [], [], []
    valores_deuda_total, valores_balance_cuentas, patrimonio_neto = [], [], []
    balance_acumulado = 0

    for mes in todos_meses:
        ingreso = float(ingresos_por_mes.get(mes, 0) + ingresos_alquiler)
        gasto = float(gastos_por_mes.get(mes, 0))
        deuda_mes = hipotecas_por_mes.get(mes, 0) + prestamos_por_mes.get(mes, 0)

        balance_mes = ingreso - gasto - deuda_mes
        balance_acumulado += balance_mes
        patrimonio = balance_acumulado - deuda_mes

        valores_ingresos.append(ingreso)
        valores_gastos.append(gasto + deuda_mes)
        valores_balance.append(balance_mes)
        valores_deuda_total.append(deuda_mes)
        valores_balance_cuentas.append(balance_acumulado)
        patrimonio_neto.append(patrimonio)

    context = {
        'registros': registros,
        'total_ingresos': total_ingresos,
        'total_gastos': total_gastos,
        'total_gastos_alquiler': gastos_alquiler,
        'balance_total': balance,
        'propiedades': propiedades,
        'ingresos_alquiler': ingresos_alquiler,
        'prestamos': prestamos,
        'gastos_prestamos': gastos_prestamos,
        'ingreso_form': CashFlowForm(initial={'category': 'ingreso'}),
        'gasto_form': CashFlowForm(initial={'category': 'gasto'}),
        'propiedad_form': PropiedadAlquilerForm(),
        'prestamo_form': PrestamoForm(),
        'beneficio_total_propiedades': beneficio_total_propiedades,
        'balance_pendiente_prestamos': balance_pendiente_prestamos,
        'labels_grafico': json.dumps(todos_meses),
        'valores_ingresos': json.dumps(valores_ingresos),
        'valores_gastos': json.dumps(valores_gastos),
        'valores_balance': json.dumps(valores_balance),
        'valores_deuda_total': json.dumps(valores_deuda_total),
        'valores_patrimonio_neto': json.dumps(patrimonio_neto),
        'valores_balance_cuentas': json.dumps(valores_balance_cuentas),
        'valores_hipoteca_restante': json.dumps(valores_deuda_total),
    }
    return render(request, 'alpha_quantum/cashflow/flujo_de_caja.html', context)


from datetime import date
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

from .models.cashflow import CashFlow
from .models.propiedad_alquilada import PropiedadAlquiler
from .models.prestamo import Prestamo

def _first_of_month(d: date) -> date:
    return d.replace(day=1)

def _coalesce_date(obj, *names, default=None):
    """Devuelve la primera fecha encontrada entre los atributos names, normalizada a 1er día de mes."""
    for n in names:
        if hasattr(obj, n):
            v = getattr(obj, n)
            if isinstance(v, date):
                return _first_of_month(v)
    return _first_of_month(default or date.today())

@login_required
def cashflow_series_api(request):
    rng = (request.GET.get("range") or "1A").upper()
    months = {"3M": 3, "6M": 6, "1A": 12, "5A": 60, "TODO": 24}.get(rng, 12)

    today = _first_of_month(date.today())
    start = today
    end   = today + relativedelta(months=months)

    user = request.user

    # ==== CashFlow base (solo formulario) ====
    from collections import defaultdict
    regs = CashFlow.objects.filter(
        user=user,
        date__gte=today - relativedelta(months=1),  # para tomar el "último" y arrastrar
        date__lt=end
    )
    ing_mes, gas_mes = defaultdict(Decimal), defaultdict(Decimal)
    for r in regs:
        k = _first_of_month(r.date).strftime("%Y-%m")
        a = Decimal(str(r.amount or 0))
        if r.category == "ingreso":
            ing_mes[k] += a
        else:
            gas_mes[k] += a

    last_key = (today - relativedelta(months=1)).strftime("%Y-%m")
    last_ing = ing_mes.get(last_key, Decimal("0"))
    last_gas = gas_mes.get(last_key, Decimal("0"))

    # ==== Propiedades y préstamos (con fecha de inicio) ====
    props = PropiedadAlquiler.objects.filter(user=user)
    prestamos = Prestamo.objects.filter(user=user)

    hipos = [{
        "hip":  Decimal(str(p.hipoteca_mensual or 0)),
        "rest": int(p.meses_restantes_hipoteca or 0),
        "ing":  Decimal(str(p.ingreso_mensual or 0)),
        "man":  Decimal(str(p.gastos_mantenimiento or 0)),
        "ini":  _coalesce_date(p, "fecha_inicio_hipoteca", "fecha_inicio", "inicio", "created_at", default=today),
    } for p in props]

    loans = [{
        "cuota": Decimal(str(l.cuota_mensual or 0)),
        "rest":  int(l.meses_restantes or 0),
        "ini":   _coalesce_date(l, "fecha_inicio", "inicio", "created_at", default=today),
    } for l in prestamos]

    deuda_total_ini = sum(h["hip"] * Decimal(h["rest"]) for h in hipos) + \
                      sum(l["cuota"] * Decimal(l["rest"]) for l in loans)

    labels = []
    ingresos_series, gastos_series = [], []
    deuda_total_series, balance_series = [], []
    deuda_mensual_series = []
    deuda_pend = deuda_total_ini
    balance_acum = Decimal("0")

    # KPIs del último mes simulado
    k_ing = k_gas = k_deuda_mens = k_ben_prop = Decimal("0")
    k_mes = ""

    for i in range(months):
        mes = start + relativedelta(months=i)
        mkey = mes.strftime("%Y-%m")
        labels.append(mkey)
        k_mes = mkey

        # 1) Ingresos/Gastos base (constantes si no hay nuevos)
        inc_base = ing_mes.get(mkey, last_ing)
        gas_base = gas_mes.get(mkey, last_gas)
        last_ing = inc_base
        last_gas = gas_base

        # 2) Beneficio propiedades y pagos de hipoteca (la hipoteca ya resta en el beneficio)
        ben_prop_mes = Decimal("0")
        pago_hip_mes = Decimal("0")
        for h in hipos:
            if mes >= h["ini"]:
                if h["rest"] > 0:
                    pago_hip_mes += h["hip"]
                    ben_prop_mes += (h["ing"] - h["man"] - h["hip"])
                    h["rest"] -= 1
                else:
                    ben_prop_mes += (h["ing"] - h["man"])
            else:
                # Si quieres que no haya renta antes del inicio, deja 0.
                # Si quieres que exista renta incluso antes, usa:
                # ben_prop_mes += (h["ing"] - h["man"])
                ben_prop_mes += Decimal("0")

        # 3) Préstamos personales (se restan aparte)
        pago_prest_mes = Decimal("0")
        for l in loans:
            if mes >= l["ini"] and l["rest"] > 0:
                pago_prest_mes += l["cuota"]
                l["rest"] -= 1

        # 4) Deuda pendiente baja por hipotecas+préstamos
        pago_deuda_total_mes = pago_hip_mes + pago_prest_mes
        if deuda_pend > 0:
            deuda_pend = max(deuda_pend - pago_deuda_total_mes, Decimal("0"))

        # 5) Balance acumulado: ingresos base - gastos base + beneficio prop - préstamos
        balance_mes = inc_base - gas_base + ben_prop_mes - pago_prest_mes
        balance_acum += balance_mes

        # Series
        ingresos_series.append(float(inc_base))
        gastos_series.append(float(gas_base))
        deuda_total_series.append(float(deuda_pend))
        deuda_mensual_series.append(float(pago_deuda_total_mes))
        balance_series.append(float(balance_acum))

        # KPIs del mes corriente (el último del bucle queda como "último período")
        k_ing = inc_base
        k_gas = gas_base
        k_deuda_mens = pago_deuda_total_mes
        k_ben_prop = ben_prop_mes

    # 6) Tasa de ahorro del último mes
    base = k_ing + k_ben_prop
    tasa_ahorro = float(((base - (k_gas + k_deuda_mens)) / base * Decimal("100"))) if base > 0 else 0.0

    return JsonResponse({
        "labels": labels,
        "ingresos": ingresos_series,
        "gastos": gastos_series,
        "deuda_total": deuda_total_series,
        "deuda_mensual": deuda_mensual_series,
        "balance_cuentas": balance_series,
        "kpis": {
            "ingresos": float(k_ing),
            "gastos": float(k_gas),
            "beneficio_propiedades": float(k_ben_prop),
            "deuda_mensual": float(k_deuda_mens),
            "balance_total": float(balance_acum),
            "tasa_ahorro": tasa_ahorro,
            "mes": k_mes
        }
    })



@login_required
def cashflow_export_csv(request):
    """Exporta ingresos/gastos a CSV (opcional)."""
    import csv
    registros = CashFlow.objects.filter(user=request.user).order_by('date')
    resp = HttpResponse(content_type="text/csv")
    resp['Content-Disposition'] = 'attachment; filename=flujo_de_caja.csv'
    w = csv.writer(resp)
    w.writerow(["Fecha","Tipo","Categoria","Descripcion","Monto"])
    for r in registros:
        w.writerow([r.date, r.category, r.subcategory or "", r.description or "", float(r.amount)])
    return resp

@login_required
def agregar_ingreso(request):
    if request.method == 'POST':
        form = CashFlowForm(request.POST)
        if form.is_valid():
            ingreso = form.save(commit=False)
            ingreso.user = request.user
            ingreso.category = 'ingreso'
            ingreso.save()
    return redirect('flujo_de_caja')

@login_required
def agregar_gasto(request):
    if request.method == 'POST':
        form = CashFlowForm(request.POST)
        if form.is_valid():
            gasto = form.save(commit=False)
            gasto.user = request.user
            gasto.category = 'gasto'
            gasto.save()
    return redirect('flujo_de_caja')

@login_required
def editar_registro(request, pk):
    registro = get_object_or_404(CashFlow, pk=pk, user=request.user)
    if request.method == 'POST':
        form = CashFlowForm(request.POST, instance=registro)
        if form.is_valid():
            form.save()
            return redirect('flujo_de_caja')
    else:
        form = CashFlowForm(instance=registro)
    return render(request, 'alpha_quantum/cashflow/editar_registro.html', {'form': form})

@login_required
def agregar_propiedad(request):
    if request.method == 'POST':
        form = PropiedadAlquilerForm(request.POST)
        if form.is_valid():
            propiedad = form.save(commit=False)
            propiedad.user = request.user
            propiedad.save()
    return redirect('flujo_de_caja')

@login_required
def agregar_prestamo(request):
    if request.method == 'POST':
        form = PrestamoForm(request.POST)
        if form.is_valid():
            p = form.save(commit=False)
            # ⚠️ Asegúrate de que tu modelo tenga el ForeignKey llamado 'user'
            p.user = request.user

            # Si existe monto_total en el modelo y no viene informado, lo calculamos
            if hasattr(p, 'monto_total') and (p.monto_total is None or p.monto_total == 0):
                try:
                    cuota = Decimal(p.cuota_mensual)
                    meses = int(p.meses_restantes or 0)
                    p.monto_total = cuota * meses
                except (InvalidOperation, ValueError, TypeError):
                    # Si falla el cálculo no rompemos el flujo
                    p.monto_total = p.monto_total or Decimal('0')

            p.save()
            messages.success(request, "✅ Préstamo añadido correctamente.")
        else:
            messages.error(request, "Revisa los datos del préstamo.")

    # Volvemos al dashboard de cashflow (el modal se cerrará al recargar)
    return redirect('flujo_de_caja')


from django.views.decorators.http import require_POST

# --- CASHFLOW (ingresos/gastos) ---
@login_required
@require_POST
def eliminar_registro(request, pk):
    registro = get_object_or_404(CashFlow, pk=pk, user=request.user)
    registro.delete()
    messages.success(request, "🗑️ Registro eliminado.")
    return redirect('flujo_de_caja')


# --- PROPIEDADES ---
@login_required
def editar_propiedad(request, pk):
    propiedad = get_object_or_404(PropiedadAlquiler, pk=pk, user=request.user)
    if request.method == 'POST':
        form = PropiedadAlquilerForm(request.POST, instance=propiedad)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Propiedad actualizada.")
            return redirect('flujo_de_caja')
    else:
        form = PropiedadAlquilerForm(instance=propiedad)
    return render(request, 'alpha_quantum/cashflow/editar_propiedad.html', {'form': form, 'obj': propiedad})

@login_required
@require_POST
def eliminar_propiedad(request, pk):
    propiedad = get_object_or_404(PropiedadAlquiler, pk=pk, user=request.user)
    propiedad.delete()
    messages.success(request, "🗑️ Propiedad eliminada.")
    return redirect('flujo_de_caja')


# --- PRÉSTAMOS ---
@login_required
def editar_prestamo(request, pk):
    prestamo = get_object_or_404(Prestamo, pk=pk, user=request.user)
    if request.method == 'POST':
        form = PrestamoForm(request.POST, instance=prestamo)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Préstamo actualizado.")
            return redirect('flujo_de_caja')
    else:
        form = PrestamoForm(instance=prestamo)
    return render(request, 'alpha_quantum/cashflow/editar_prestamo.html', {'form': form, 'obj': prestamo})

@login_required
@require_POST
def eliminar_prestamo(request, pk):
    prestamo = get_object_or_404(Prestamo, pk=pk, user=request.user)
    prestamo.delete()
    messages.success(request, "🗑️ Préstamo eliminado.")
    return redirect('flujo_de_caja')


from .models.calendario import EventoFinanciero
from .utils import obtener_eventos_financieros_alpha_vantage

@login_required
def eventos_api(request):
    user = request.user
    ticker = request.GET.get("ticker")

    # Si nos pasan un ticker, intentamos traer/actualizar eventos para ese ticker
    if ticker:
        try:
            obtener_eventos_financieros_alpha_vantage(ticker, user)
        except Exception as e:
            print(f"[CAL] error sincronizando eventos de {ticker}: {e}")

    qs = EventoFinanciero.objects.filter(user=user)
    if ticker:
        qs = qs.filter(ticker__iexact=ticker)
    qs = qs.order_by("-fecha")

    eventos = [{
        "ticker": ev.ticker,
        "tipo": ev.tipo_evento,          # campo del modelo
        "fecha": ev.fecha.strftime("%Y-%m-%d") if hasattr(ev.fecha, "strftime") else str(ev.fecha),
        "descripcion": ev.descripcion or ""
    } for ev in qs]

    return JsonResponse({"eventos": eventos})


@login_required
def precios_watchlist_api(request):
    acciones = Watchlist.objects.filter(user=request.user)
    data = []

    for acc in acciones:
        try:
            precio = obtener_precio_actual(acc.ticker)
            if precio:
                acc.precio_actual = precio
                acc.save(update_fields=["precio_actual"])
        except Exception as e:
            # no rompemos la respuesta si alguna API falla
            print(f"[WATCHLIST] error actualizando {acc.ticker}: {e}")

        data.append({
            "id": acc.id,
            "nombre": acc.nombre,
            "ticker": acc.ticker,
            "precio_actual": float(acc.precio_actual or 0),
        })

    return JsonResponse({"acciones": data})

# alpha_quantum/views.py

# views.py
from decimal import Decimal
from collections import defaultdict
from datetime import date, timedelta
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Sum

# Usa tu helper ya definido arriba
# def _position_on(user, ticker: str, cutoff) -> Decimal: ...

@login_required
def resumen_cartera(request):
    """
    Dashboard de resumen con:
      - KPIs (valor actual, invertido, P/L, %)
      - Beneficios por empresa (€)
      - Coste vs Valor de mercado
      - Distribuciones (ticker, sector, divisa)
      - Rentabilidad últimos 12m (línea)
      - Dividendos: próximo calendario, mensual últimos 12m, total anual y yield
      - Métricas: volatilidad (simple), Sharpe (aprox), % en cash (si no hay, 0)
    """
    from .models import Accion
    from .models.dividendo import Dividendo
    from .models.historico import HistoricoCartera

    user = request.user

    acciones = Accion.objects.filter(user=user).order_by('ticker')
    dividendos = Dividendo.objects.filter(accion__user=user).select_related('accion').order_by('fecha')

    total_invertido = Decimal('0')
    valor_actual     = Decimal('0')

    # ---------- Posiciones y agregados ----------
    posiciones = []
    by_sector  = defaultdict(Decimal)
    by_divisa  = defaultdict(Decimal)

    for a in acciones:
        qty = Decimal(str(a.cantidad or 0))
        pc  = Decimal(str(a.precio_compra or 0))
        pa  = Decimal(str(a.precio_actual or a.precio_compra or 0))

        inv = qty * pc
        val = qty * pa
        pnl = val - inv

        total_invertido += inv
        valor_actual    += val

        sector = getattr(a, 'sector', None) or "Sin sector"
        divisa = getattr(a, 'divisa', None) or "Sin divisa"

        posiciones.append({
            "ticker": a.ticker,
            "cantidad": float(qty),
            "precio_compra": float(pc),
            "precio_actual": float(pa),
            "valor_total": float(val),
            "coste_total": float(inv),
            "pnl": float(pnl),
            "sector": sector,
            "divisa": divisa,
        })

        by_sector[sector] += val
        by_divisa[divisa] += val

    # KPIs base
    rentabilidad = valor_actual - total_invertido
    rentabilidad_pct = float((rentabilidad / total_invertido * Decimal('100'))) if total_invertido > 0 else 0.0

    # ---------- Distribuciones ----------
    dist_ticker_labels = [p["ticker"] for p in posiciones]
    dist_ticker_values = [p["valor_total"] for p in posiciones]

    dist_sector_labels = list(by_sector.keys())
    dist_sector_values = [float(v) for v in by_sector.values()]

    dist_divisa_labels = list(by_divisa.keys())
    dist_divisa_values = [float(v) for v in by_divisa.values()]

    # ---------- Coste vs Valor ----------
    coste_labels = [p["ticker"] for p in posiciones]
    coste_values = [p["coste_total"] for p in posiciones]
    valor_values = [p["valor_total"] for p in posiciones]

    # ---------- Beneficios por empresa ----------
    beneficios_labels = [p["ticker"] for p in posiciones]
    beneficios_values = [p["pnl"] for p in posiciones]

    # ---------- Rentabilidad últimos 12m (línea) ----------
    hoy = date.today()
    hace_12m = hoy - timedelta(days=365)
    # HistoricoCartera: tus campos pueden ser valor/invertido o valor_total/invertido_total según tus seeds
    # Intentamos ambos nombres de forma robusta
    hist = HistoricoCartera.objects.filter(user=user, fecha__gte=hace_12m).order_by('fecha')
    fechas_series, serie_valor = [], []
    for h in hist:
        fechas_series.append(h.fecha.strftime("%Y-%m-%d"))
        v = getattr(h, 'valor', None)
        if v is None:
            v = getattr(h, 'valor_total', 0)
        serie_valor.append(float(v or 0))

    rent_12m_labels, rent_12m_values = [], []
    if len(serie_valor) >= 2:
        base = serie_valor[0]
        for idx, v in enumerate(serie_valor):
            rr = 0.0 if base == 0 else (v - base) / base * 100.0
            rent_12m_labels.append(fechas_series[idx])
            rent_12m_values.append(rr)

    # ---------- Volatilidad y Sharpe (aprox) ----------
    # volatilidad = std de rendimientos diarios * sqrt(252)
    # sharpe = (avg_ret * 252) / (std_daily * sqrt(252))  => simplifica a avg_ret/std_daily * sqrt(252)
    daily_returns = []
    if len(serie_valor) >= 2:
        for i in range(1, len(serie_valor)):
            prev, cur = serie_valor[i-1], serie_valor[i]
            if prev != 0:
                daily_returns.append((cur/prev) - 1.0)

    def _std(xs):
        if len(xs) < 2: return 0.0
        m = sum(xs)/len(xs)
        var = sum((x-m)**2 for x in xs)/(len(xs)-1)
        return var**0.5

    vol_pct = 0.0
    sharpe  = 0.0
    if daily_returns:
        std_d = _std(daily_returns)
        avg_d = sum(daily_returns)/len(daily_returns)
        vol_pct = (std_d * (252**0.5)) * 100.0
        sharpe  = (avg_d/std_d)*(252**0.5) if std_d > 0 else 0.0

    # ---------- Dividendos ----------
    #  a) últimos 12 meses por mes (sumando monto * shares en fecha)
    meses = []
    div_mes_map = defaultdict(Decimal)
    hace_12m_div = hoy - timedelta(days=365)
    for d in dividendos:
        if not hasattr(d, 'fecha') or d.fecha is None:
            continue
        if d.fecha < hace_12m_div:
            continue
        key = d.fecha.strftime("%Y-%m")
        tk = d.accion.ticker
        qty_on_date = _position_on(user, tk, d.fecha)
        div_mes_map[key] += Decimal(str(d.monto or 0)) * Decimal(qty_on_date)

    meses = sorted(div_mes_map.keys())
    div_mensual_labels = meses
    div_mensual_values = [float(div_mes_map[m]) for m in meses]
    dividendos_12m_total = float(sum(div_mes_map.values()))

    #  b) total por año y por ticker (para barras apiladas o simple)
    div_por_anio = defaultdict(lambda: defaultdict(Decimal))
    for d in dividendos:
        if not hasattr(d, 'fecha') or d.fecha is None:
            continue
        anio = d.fecha.year
        qty_on_date = _position_on(user, d.accion.ticker, d.fecha)
        div_por_anio[anio][d.accion.ticker] += Decimal(str(d.monto or 0)) * Decimal(qty_on_date)

    dividendos_anuales = {int(y): {tk: float(v) for tk, v in m.items()} for y, m in div_por_anio.items()}
    anios_div = sorted(dividendos_anuales.keys())
    anio_actual = anios_div[-1] if anios_div else date.today().year
    div_actual_labels = list(dividendos_anuales.get(anio_actual, {}).keys())
    div_actual_values = list(dividendos_anuales.get(anio_actual, {}).values())

    #  c) yield por dividendos (últimos 12m / valor actual)
    dividend_yield_pct = (dividendos_12m_total / float(valor_actual)) * 100.0 if valor_actual > 0 else 0.0

    # ---------- Próximos "dividendos" (si no tienes calendario, dejamos vacío) ----------
    # Puedes poblarlos desde tu modelo EventoFinanciero si lo deseas.
    proximos_dividendos = []  # [{"ticker":"AAPL","fecha":"2025-09-01","importe":12.34}, ...]

    # ---------- % en cash (si no tienes modelo de cash, 0) ----------
    cash_pct = 0.0

    context = {
        # KPIs
        "total_invertido": float(total_invertido),
        "valor_actual": float(valor_actual),
        "rentabilidad": float(rentabilidad),
        "rentabilidad_pct": float(rentabilidad_pct),

        # Métricas avanzadas
        "volatilidad_pct": float(vol_pct),
        "sharpe_ratio": float(sharpe),
        "cash_pct": float(cash_pct),

        # Beneficios
        "beneficios_labels": beneficios_labels,
        "beneficios_values": beneficios_values,

        # Coste vs valor
        "coste_labels": coste_labels,
        "coste_values": coste_values,
        "valor_values": valor_values,

        # Distribución
        "dist_ticker_labels": dist_ticker_labels,
        "dist_ticker_values": dist_ticker_values,
        "dist_sector_labels": dist_sector_labels,
        "dist_sector_values": dist_sector_values,
        "dist_divisa_labels": dist_divisa_labels,
        "dist_divisa_values": dist_divisa_values,

        # Rentabilidad últimos 12m
        "rent_12m_labels": rent_12m_labels,
        "rent_12m_values": rent_12m_values,

        # Dividendos
        "div_mensual_labels": div_mensual_labels,
        "div_mensual_values": div_mensual_values,
        "dividendos_12m_total": float(dividendos_12m_total),
        "dividend_yield_pct": float(dividend_yield_pct),
        "anio_dividendo": int(anio_actual),
        "div_actual_labels": div_actual_labels,
        "div_actual_values": div_actual_values,
        "proximos_dividendos": proximos_dividendos,
    }
    return render(request, "alpha_quantum/resumen.html", context)




@login_required
def editar_accion(request, accion_id):
    accion = get_object_or_404(Accion, id=accion_id, user=request.user)

    if request.method == "POST":
        form = AccionForm(request.POST, instance=accion)
        if form.is_valid():
            form.save()
            messages.success(request, "La acción ha sido actualizada correctamente.")
            return redirect("dashboard")
        else:
            messages.error(request, "Corrige los errores del formulario.")
    else:
        form = AccionForm(instance=accion)

    return render(request, "alpha_quantum/editar_accion.html", {"form": form})


@login_required
def alpha_bots(request):
    """Renderiza la página de Alpha Bots."""
    return render(request, "alpha_quantum/alpha_bots.html", {})

@login_required
def alpha_indicators(request):
    """Renderiza la página de Alpha Indicators."""
    return render(request, "alpha_quantum/alpha_indicators.html", {})

@login_required
def macroeconomia(request):
    """Renderiza la página de Macroeconomía."""
    return render(request, "alpha_quantum/macroeconomia.html", {})

@login_required
def foro(request):
    """Renderiza la página del Foro."""
    return render(request, "alpha_quantum/foro.html", {})

@login_required
def alpha_risk_lab(request):
    """Renderiza la página de Risk Lab."""
    return render(request, "alpha_quantum/alpha_risk_lab.html", {})
