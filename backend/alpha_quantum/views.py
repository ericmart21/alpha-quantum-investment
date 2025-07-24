# alpha_quantum/views.py

from django.shortcuts import render, redirect
from .forms import AccionForm
from .serializers import AccionSerializer
from .utils import obtener_precio_actual, calcular_resumen, calcular_upside, generar_recomendacion
from .models.cartera import Cartera
from .models.dividendo import Dividendo
from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings
from decimal import Decimal, InvalidOperation
import requests
from rest_framework.views import APIView
from rest_framework.decorators import api_view
from decimal import Decimal
from datetime import date, datetime
from .models import Accion, Cartera
from alpha_quantum.utils import actualizar_historico
import json
from datetime import datetime


def index(request):
    acciones = Accion.objects.all()
    acciones_json = json.dumps([{'nombre': a.nombre, 'cantidad': a.cantidad} for a in acciones])
    return render(request, 'alpha_quantum/index.html', {'acciones': acciones, 'acciones_json': acciones_json})


def agregar_accion(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        ticker = request.POST.get('ticker')
        cantidad = request.POST.get('cantidad')
        precio_compra = request.POST.get('precio_compra')
        fecha_str = request.POST.get('fecha')

        try:
            # Convertir string a objeto date
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return render(request, 'alpha_quantum/agregar.html', {
                'error': 'Fecha inválida. Usa el formato correcto YYYY-MM-DD.'
            })

        cartera = Cartera.objects.first()
        if not cartera:
            return render(request, 'alpha_quantum/agregar.html', {
                'error': 'No hay ninguna cartera creada.'
            })

        Accion.objects.create(
            nombre=nombre,
            ticker=ticker,
            cantidad=cantidad,
            precio_compra=precio_compra,
            fecha=fecha,
            cartera=cartera
        )
        return redirect('index')
        
    return render(request, 'alpha_quantum/agregar.html')


def dashboard(request):
    carteras = Cartera.objects.all()
    dividendos = Dividendo.objects.all()
    return render(request, "alpha_quantum/dashboard.html", {
        "carteras": carteras,
        "dividendos": dividendos
    })


class DashboardDataView(APIView):
    def get(self, request):
        acciones = Accion.objects.all()
        resumen = calcular_resumen(acciones)

        # Historial de valor de la cartera (sumando el valor total por día)
        historico = {}
        historicos = PrecioHistorico.objects.all().order_by("fecha")
        for h in historicos:
            fecha = h.fecha.strftime("%Y-%m-%d")
            if fecha not in historico:
                historico[fecha] = Decimal('0')
            historico[fecha] += Decimal(h.precio_cierre) * h.accion.cantidad

        historico_ordenado = [{"fecha": fecha, "valor": float(valor)} for fecha, valor in sorted(historico.items())]

        # Rentabilidad por acción
        acciones_rentabilidad = []
        for a in acciones:
            try:
                ganancia = float(a.precio_actual) - float(a.precio_compra)
                acciones_rentabilidad.append({
                    "nombre": a.nombre,
                    "ganancia": round(ganancia * float(a.cantidad), 2)
                })
            except (TypeError, ValueError):
                continue

        data = {
            "valor_total_cartera": resumen["valor_actual"],
            "rentabilidad_total": resumen["rentabilidad"],
            "acciones_rentabilidad": acciones_rentabilidad,
            "historico_valor": historico_ordenado,
        }

        return Response(data)

    def obtener_precio_actual(self, ticker):
        api_key = getattr(settings, "TWELVE_DATA_API_KEY", None)
        if not api_key:
            print("Error: API KEY no definida en settings.")
            return None

        url = f"https://api.twelvedata.com/price?symbol={ticker}&apikey={api_key}"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "error":
                    print("Error en respuesta de API:", data)
                    return None
                return float(data["price"])
            else:
                print("Error al obtener precio actual:", response.text)
                return None
        except Exception as e:
            print("Excepción al obtener precio actual:", e)
            return None

from .models import PrecioHistorico
from django.shortcuts import render
from alpha_quantum.utils import actualizar_historico
from datetime import date, timedelta


def grafico_rentabilidad(request):
    hoy = date.today()

    # Actualiza el histórico si hace falta
    for acc in Accion.objects.all():
        try:
            actualizar_historico(acc, dias=365)
        except Exception as e:
            print("⚠️ No se pudo actualizar", acc.ticker, e)

    # Diccionario con los puntos de rentabilidad por fecha
    puntos = {}
    for ph in PrecioHistorico.objects.select_related('accion'):
        valor = float(ph.precio_cierre) * ph.accion.cantidad
        invertido = float(ph.accion.precio_compra) * ph.accion.cantidad
        if ph.fecha not in puntos:
            puntos[ph.fecha] = {'valor': 0, 'invertido': 0}
        puntos[ph.fecha]['valor'] += valor
        puntos[ph.fecha]['invertido'] += invertido

    # Ordenamos por fecha y preparamos las series
    etiquetas, serieGanancia, serieRentab = [], [], []
    for fecha in sorted(puntos):
        etiquetas.append(fecha.strftime("%Y-%m-%d"))
        v = puntos[fecha]['valor']
        inv = puntos[fecha]['invertido']
        ganancia = round(v - inv, 2)
        rentabilidad = round(((v - inv) / inv) * 100, 2) if inv > 0 else 0
        serieGanancia.append(ganancia)
        serieRentab.append(rentabilidad)

    contexto = {
        "etiquetas": json.dumps(etiquetas),
        "serieGanancia": json.dumps(serieGanancia),
        "serieRentab": json.dumps(serieRentab),
        "ganancia_total": serieGanancia[-1] if serieGanancia else 0,
        "rentabilidad_total": serieRentab[-1] if serieRentab else 0
    }

    return render(request, "alpha_quantum/grafico.html", contexto)


class RentabilidadAPI(APIView):
    def get(self, request):
        hoy = date.today()

        # Parámetro opcional para limitar por días
        dias = int(request.GET.get('dias', 365))

        for acc in Accion.objects.all():
            try:
                actualizar_historico(acc, dias=dias)
            except Exception as e:
                print(f"❌ Error al actualizar {acc.ticker}: {e}")

        puntos = {}
        for ph in PrecioHistorico.objects.select_related('accion'):
            if (hoy - ph.fecha).days > dias:
                continue

            valor = float(ph.precio_cierre) * ph.accion.cantidad
            invertido = float(ph.accion.precio_compra) * ph.accion.cantidad

            if ph.fecha not in puntos:
                puntos[ph.fecha] = {'valor': 0, 'invertido': 0}
            puntos[ph.fecha]['valor'] += valor
            puntos[ph.fecha]['invertido'] += invertido

        etiquetas, serieGanancia, serieRentab = [], [], []
        for fecha in sorted(puntos):
            etiquetas.append(fecha.strftime("%Y-%m-%d"))
            v = puntos[fecha]['valor']
            inv = puntos[fecha]['invertido']
            ganancia = round(v - inv, 2)
            rentabilidad = round(((v - inv) / inv) * 100, 2) if inv > 0 else 0
            serieGanancia.append(ganancia)
            serieRentab.append(rentabilidad)

        return Response({
            "etiquetas": etiquetas,
            "serieGanancia": serieGanancia,
            "serieRentab": serieRentab,
            "ganancia_total": serieGanancia[-1] if serieGanancia else 0,
            "rentabilidad_total": serieRentab[-1] if serieRentab else 0
        })
    
class PosicionesAPI(APIView):
    def get(self, request):
        acciones = Accion.objects.all()
        for acc in acciones:
            new_price = obtener_precio_actual(acc.ticker)
            if new_price:
                acc.precio_actual = new_price
                acc.save()
        return Response(AccionSerializer(acciones, many=True).data)

class ResumenAPI(APIView):
    def get(self, request):
        acciones = Accion.objects.all()
        valor_total = sum((a.precio_actual or 0) * a.cantidad for a in acciones)
        invertido = sum(a.precio_compra * a.cantidad for a in acciones)
        rentabilidad_pct = round(((valor_total - invertido) / invertido) * 100, 2) if invertido else 0
        return Response({
            "valor_total": round(valor_total, 2),
            "invertido": round(invertido, 2),
            "rentabilidad_pct": rentabilidad_pct,
        })

class RentabilidadHistoricaAPI(APIView):
    def get(self, request):
        dias = int(request.GET.get("dias", 365))
        hoy = date.today()
        for acc in Accion.objects.all():
            actualizar_historico(acc, dias=dias)
        puntos = {}
        for ph in PrecioHistorico.objects.select_related("accion"):
            if (hoy - ph.fecha).days > dias:
                continue
            valor = float(ph.precio_cierre) * ph.accion.cantidad
            invertido = float(ph.accion.precio_compra) * ph.accion.cantidad
            if ph.fecha not in puntos:
                puntos[ph.fecha] = {"valor": 0, "invertido": 0}
            puntos[ph.fecha]["valor"] += valor
            puntos[ph.fecha]["invertido"] += invertido
        fechas = sorted(puntos)
        series_ganancia = [round(puntos[f]["valor"] - puntos[f]["invertido"], 2) for f in fechas]
        series_rentab = [
            round(((puntos[f]["valor"] - puntos[f]["invertido"]) / puntos[f]["invertido"]) * 100, 2)
            if puntos[f]["invertido"] != 0 else 0
            for f in fechas
        ]
        return Response({
            "fechas": fechas,
            "ganancia": series_ganancia,
            "rentabilidad_pct": series_rentab,
        })


from .models import Accion
from django.http import JsonResponse


@api_view(['GET'])
def resumen_cartera(request):
    acciones = Accion.objects.all()
    total_invertido = sum(a.precio_compra * a.cantidad for a in acciones)
    valor_actual = sum((a.precio_actual or 0) * a.cantidad for a in acciones)
    rentabilidad = valor_actual - total_invertido

    return Response({
        'total_invertido': round(total_invertido, 2),
        'valor_actual': round(valor_actual, 2),
        'rentabilidad': round(rentabilidad, 2),
    })


class CarteraAPIView(APIView):
    def get(self, request):
        acciones = Accion.objects.all()

        for a in acciones:
            nuevo_precio = obtener_precio_actual(a.ticker)
            if nuevo_precio is not None:
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
            except Exception as e:
                print(f"Error con acción {a.ticker}: {e}")
                continue

        return Response({
            "total_cartera": f"{total_cartera:.2f}",
            "acciones": data,
        })

    
def cartera(request):
    acciones = Accion.objects.all()
    return render(request, "alpha_quantum/cartera.html")

def cartera_view(request):
    acciones = Accion.objects.all()
    datos = []
    total_actual = 0

    for a in acciones:
        nuevo_precio = obtener_precio_actual(a.ticker)
        if nuevo_precio:
            a.precio_actual = nuevo_precio
            a.save(update_fields=["precio_actual"])
        if a.precio_actual:
            total_actual += a.precio_actual * a.cantidad

    for a in acciones:
        if a.precio_actual is None:
            continue
        valor = a.precio_actual * a.cantidad
        rentabilidad = (a.precio_actual - a.precio_compra) * a.cantidad
        rentabilidad_pct = ((a.precio_actual - a.precio_compra) / a.precio_compra) * 100 if a.precio_compra else 0
        porcentaje_total = (valor / total_actual) * 100 if total_actual else 0

        datos.append({
            "nombre": a.nombre,
            "ticker": a.ticker,
            "precio_compra": a.precio_compra,
            "precio_actual": a.precio_actual,
            "cantidad": a.cantidad,
            "valor_total": valor,
            "rentabilidad_eur": rentabilidad,
            "rentabilidad_pct": rentabilidad_pct,
            "porcentaje_total": porcentaje_total,
        })

    return render(request, "alpha_quantum/cartera.html", {"acciones": datos})


from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required

@login_required
def editar_accion(request, pk):
    accion = get_object_or_404(Accion, pk=pk, cartera__usuario=request.user)

    if request.method == 'POST':
        form = AccionForm(request.POST, instance=accion, usuario=request.user)
        if form.is_valid():
            form.save()
            return redirect('index')  # o la vista principal
    else:
        form = AccionForm(instance=accion, usuario=request.user)

    return render(request, 'alpha_quantum/editar_accion.html', {'form': form, 'accion': accion})

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, logout
from .forms import LoginForm, CustomUserCreationForm

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


from .models.watchlist import Watchlist
from .forms import WatchlistForm
from django.shortcuts import get_object_or_404
from django.contrib import messages
from .utils import obtener_datos_finnhub
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from decimal import Decimal, InvalidOperation

@login_required
def ver_watchlist(request):
    acciones = Watchlist.objects.filter(user=request.user)
    acciones_context = []

    for accion in acciones:
        acciones_context.append({
            "id": accion.id,
            "nombre": accion.nombre,
            "ticker": accion.ticker.upper(),
            "precio_actual": float(accion.precio_actual or 0),
            "valor_objetivo": float(accion.valor_objetivo or 0),
            "upside": float(accion.upside or 0),
            "recomendacion": accion.recomendacion or "N/A",
            "max_52s": accion.max_52s,
            "min_52s": accion.min_52s,
            "per": accion.per,
        })

    return render(request, 'alpha_quantum/watchlist.html', { "acciones": acciones_context })


@login_required
def añadir_watchlist(request):
    if request.method == 'POST':
        form = WatchlistForm(request.POST)
        if form.is_valid():
            nueva_accion = form.save(commit=False)
            nueva_accion.user = request.user

            # Obtener datos de Finnhub
            datos = obtener_datos_finnhub(nueva_accion.ticker)
            if datos:
                nueva_accion.precio_actual = datos['precio_actual']
                nueva_accion.per = datos['per']
                nueva_accion.max_52s = datos['max_52s']
                nueva_accion.min_52s = datos['min_52s']

            # Calcular upside y recomendación si hay valor_objetivo
            if nueva_accion.valor_objetivo and nueva_accion.precio_actual:
                nueva_accion.upside = calcular_upside(nueva_accion.valor_objetivo, nueva_accion.precio_actual)
                nueva_accion.recomendacion = generar_recomendacion(nueva_accion.upside)

            nueva_accion.save()
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

@login_required
def precios_watchlist_api(request):
    acciones = Watchlist.objects.filter(user=request.user)
    data = []

    for accion in acciones:
        precio = obtener_precio_actual(accion.ticker)
        if precio is not None:
            accion.precio_actual = precio
            accion.save(update_fields=["precio_actual"])
        data.append({
            'id': accion.id,
            'nombre': accion.nombre,
            'ticker': accion.ticker,
            'precio_actual': round(accion.precio_actual, 2)
        })

    return JsonResponse({'acciones': data})


@login_required
def watchlist_data(request):
    acciones = Watchlist.objects.filter(user=request.user)

    data = []
    for accion in acciones:
        data.append({
            'id': accion.id,
            'nombre': accion.nombre,
            'ticker': accion.ticker,
            'precio_actual': float(accion.precio_actual or 0),
            'valor_objetivo': float(accion.valor_objetivo or 0),
            'upside': float(accion.upside or 0),
            'señal': accion.recomendacion,
            'max_52s': float(accion.max_52s or 0),
            'min_52s': float(accion.min_52s or 0),
            'per': float(accion.per or 0),
        })

    return JsonResponse({'acciones': data})


def noticias(request):
    return render(request, 'alpha_quantum/noticias.html')

def fundamental(request):
    return render(request, 'alpha_quantum/fundamental.html')


from .models.calendario import EventoFinanciero
from .utils import obtener_eventos_financieros_alpha_vantage
from datetime import timedelta

@login_required
def calendario(request):
    user = request.user
    tipo_evento = request.GET.get("tipo_evento")
    filtro_tiempo = request.GET.get("tiempo")
    filtro_ticker = request.GET.get("ticker")

    eventos = EventoFinanciero.objects.filter(user=user)

    # Filtro por tipo de evento
    if tipo_evento and tipo_evento != "todos":
        eventos = eventos.filter(tipo_evento=tipo_evento)

    # Filtro por ticker
    if filtro_ticker:
        eventos = eventos.filter(ticker__icontains=filtro_ticker)

    # Filtro por tiempo
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

@login_required
def eventos_api(request):
    usuario = request.user
    eventos = obtener_eventos_financieros_alpha_vantage(usuario)

    # Añadimos eventos manuales (como compras/ventas) si están en base de datos
    transacciones = EventoFinanciero.objects.filter(usuario=usuario)
    for t in transacciones:
        eventos.append({
            "ticker": t.ticker,
            "tipo": t.tipo,
            "fecha": t.fecha.strftime('%Y-%m-%d'),
            "descripcion": t.descripcion
        })

    return JsonResponse({"eventos": eventos})