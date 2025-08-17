# alpha_quantum/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.utils.timezone import now, timedelta
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

    context = {
        "valor_total_cartera": round(float(valor_actual), 2),
        "rentabilidad_total": round(float(rentabilidad_total), 2),
        "total_invertido": round(float(total_invertido), 2),
        "hist_labels": json.dumps(hist_labels),
        "hist_values": json.dumps(hist_values),
        "dist_labels": json.dumps(dist_labels),
        "dist_values": json.dumps(dist_values),
        "dividendos": dividendos,
        "transacciones": transacciones,
    }
    return render(request, "alpha_quantum/dashboard.html", context)

@login_required
def resumen_cartera(request):
    user = request.user
    acciones = Cartera.objects.filter(user=user)

    total_invertido = Decimal("0")
    valor_actual_total = Decimal("0")

    for acc in acciones:
        try:
            precio_actual = obtener_precio_actual(acc.ticker)
            if precio_actual:
                acc.precio_actual = precio_actual
                acc.save(update_fields=["precio_actual"])
        except Exception as e:
            print(f"[RESUMEN CARTERA] Error obteniendo precio para {acc.ticker}: {e}")

        inversion_accion = acc.cantidad * acc.precio_compra
        valor_accion = acc.cantidad * (acc.precio_actual or acc.precio_compra)

        total_invertido += inversion_accion
        valor_actual_total += valor_accion

    rentabilidad_total = ((valor_actual_total - total_invertido) / total_invertido * 100) if total_invertido > 0 else 0

    data = {
        "total_invertido": float(round(total_invertido, 2)),
        "valor_actual_total": float(round(valor_actual_total, 2)),
        "rentabilidad_total": float(round(rentabilidad_total, 2)),
    }
    return JsonResponse(data)

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

# ===========================
#      WATCHLIST
# ===========================
@login_required
def ver_watchlist(request):
    acciones = Watchlist.objects.filter(user=request.user)
    acciones_context = [{
        "id": a.id, "nombre": a.nombre, "ticker": a.ticker.upper(),
        "precio_actual": float(a.precio_actual or 0), "valor_objetivo": float(a.valor_objetivo or 0),
        "upside": float(a.upside or 0), "recomendacion": a.recomendacion or "N/A",
        "max_52s": a.max_52s, "min_52s": a.min_52s, "per": a.per,
    } for a in acciones]
    return render(request, 'alpha_quantum/watchlist.html', { "acciones": acciones_context })

@login_required
def añadir_watchlist(request):
    if request.method == 'POST':
        form = WatchlistForm(request.POST)
        if form.is_valid():
            nueva = form.save(commit=False)
            nueva.user = request.user
            datos = obtener_datos_finnhub(nueva.ticker)
            if datos:
                nueva.precio_actual = datos['precio_actual']
                nueva.per = datos['per']
                nueva.max_52s = datos['max_52s']
                nueva.min_52s = datos['min_52s']
            if nueva.valor_objetivo and nueva.precio_actual:
                nueva.upside = calcular_upside(nueva.valor_objetivo, nueva.precio_actual)
                nueva.recomendacion = generar_recomendacion(nueva.upside)
            nueva.save()
            return redirect('ver_watchlist')
    else:
        form = WatchlistForm()
    return render(request, 'alpha_quantum/formulario_watchlist.html', {'form': form})

@login_required
def eliminar_accion_watchlist(request, pk):
    accion = get_object_or_404(Watchlist, pk=pk, user=request.user)
    if request.method == 'POST':
        accion.delete()
        messages.success(request, f"🗑️ Acción '{accion.ticker.upper()}' eliminada correctamente.")
        return redirect('ver_watchlist')
    return render(request, 'alpha_quantum/confirmar_eliminar.html', {'accion': accion})

@login_required
def editar_accion_watchlist(request, pk):
    accion = get_object_or_404(Watchlist, pk=pk, user=request.user)
    if request.method == 'POST':
        form = WatchlistForm(request.POST, instance=accion)
        if form.is_valid():
            accion = form.save(commit=False)
            datos = obtener_datos_finnhub(accion.ticker)
            if datos:
                accion.precio_actual = datos['precio_actual']
                accion.per = datos['per']
                accion.max_52s = datos['max_52s']
                accion.min_52s = datos['min_52s']
            accion.upside = calcular_upside(accion.valor_objetivo, accion.precio_actual)
            accion.recomendacion = generar_recomendacion(accion.upside)
            accion.save()
            messages.success(request, f"✅ Acción '{accion.ticker.upper()}' actualizada correctamente.")
            return redirect('ver_watchlist')
    else:
        form = WatchlistForm(instance=accion)
    return render(request, 'alpha_quantum/editar_watchlist.html', {'form': form, 'accion': accion})


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
def fundamental(request):
    return render(request, 'alpha_quantum/fundamental.html')

def analisis_fundamental(request):
    datos = None
    ticker = request.GET.get('ticker')
    if ticker:
        datos = obtener_datos_fundamentales_alpha_vantage(ticker.upper())
        print("DEBUG - Datos parseados:", datos)
    return render(request, 'alpha_quantum/fundamental.html', {'datos': datos, 'ticker': ticker})


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

# --- imports necesarios (si no están ya) ---
def cartera(request):
    """
    Muestra la lista de acciones que forman parte de la cartera.
    """
    acciones = Accion.objects.all()
    return render(request, 'alpha_quantum/cartera.html', {'acciones': acciones})

@login_required
def resumen_cartera(request):
    """
    Página de 'Resumen' (no API). Muestra unos KPIs básicos de la cartera
    del usuario y lista rápida de posiciones.
    """
    acciones = Accion.objects.filter(user=request.user)

    total_invertido = Decimal('0')
    valor_actual = Decimal('0')

    for a in acciones:
        qty = Decimal(str(a.cantidad or 0))
        pc  = Decimal(str(a.precio_compra or 0))
        pa  = Decimal(str(a.precio_actual or 0))
        total_invertido += qty * pc
        valor_actual    += qty * pa

    rentabilidad = valor_actual - total_invertido

    context = {
        "total_invertido": float(total_invertido),
        "valor_actual": float(valor_actual),
        "rentabilidad": float(rentabilidad),
        "acciones": acciones,
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
def watchlist_data(request):
    user = request.user
    watchlist = Watchlist.objects.filter(user=user)

    data = []
    for accion in watchlist:
        data.append({
            "id": accion.id,
            "ticker": accion.ticker,
            "precio_actual": float(accion.precio_actual) if accion.precio_actual else None,
            "precio_max_52": float(accion.precio_max_52) if accion.precio_max_52 else None,
            "precio_min_52": float(accion.precio_min_52) if accion.precio_min_52 else None,
            "precio_objetivo": float(accion.valor_objetivo) if accion.valor_objetivo else None,
            "PER": float(accion.PER) if accion.PER else None,
            "fecha_agregado": accion.fecha_agregado.strftime("%Y-%m-%d") if accion.fecha_agregado else None,
        })

    return JsonResponse({"watchlist": data})
