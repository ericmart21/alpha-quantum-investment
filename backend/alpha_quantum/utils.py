import requests, datetime, os
from .models import PrecioHistorico, Accion
from decimal import Decimal, InvalidOperation
from django.conf import settings

FINNHUB_API_KEY = settings.FINNHUB_API_KEY
API_KEY = '7845cebeb98c4b519a6ce293374a2389'

import requests
from django.conf import settings

def obtener_precio_actual(ticker):
    api_key = settings.TWELVE_DATA_API_KEY  # <- aquí está el cambio correcto
    if not api_key:
        print("API Key no configurada.")
        return 0.0

    url = f'https://api.twelvedata.com/price?symbol={ticker}&apikey={api_key}'
    try:
        response = requests.get(url)
        response.raise_for_status()  # lanza error si hay fallo HTTP
        data = response.json()

        price = float(data.get('price', 0.0))
        return price

    except Exception as e:
        print(f"Error al obtener precio actual para {ticker}: {e}")
        return 0.0



def actualizar_historico(accion: Accion, dias=365):
    URL     = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": accion.ticker,
        "interval": "1day",
        "outputsize": dias,
        "apikey": API_KEY,
    }
    r = requests.get(URL, params=params, timeout=10).json()
    for punto in r.get("values", []):
        fecha  = datetime.datetime.strptime(punto["datetime"], "%Y-%m-%d").date()
        cierre = punto["close"]
        PrecioHistorico.objects.update_or_create(
            accion=accion, fecha=fecha,
            defaults={"precio_cierre": cierre}
        )


def calcular_resumen(acciones):
    total_invertido = Decimal('0')
    valor_actual = Decimal('0')

    for accion in acciones:
        try:
            cantidad = Decimal(str(accion.cantidad))
            precio_compra = Decimal(str(accion.precio_compra))
            precio_actual = Decimal(str(accion.precio_actual))

            total_invertido += precio_compra * cantidad
            valor_actual += precio_actual * cantidad
        except (InvalidOperation, AttributeError, TypeError, ValueError):
            continue  # o loguea el error

    rentabilidad = valor_actual - total_invertido

    return {
        "total_invertido": float(total_invertido),
        "valor_actual": float(valor_actual),
        "rentabilidad": float(rentabilidad)
    }



def calcular_upside(valor_objetivo, precio_actual):
    if valor_objetivo is None or precio_actual is None:
        return None
    try:
        return ((Decimal(valor_objetivo) - Decimal(precio_actual)) / Decimal(precio_actual)) * 100
    except Exception as e:
        print(f"Error calculando el upside: {e}")
        return None



def generar_recomendacion(upside):
    """
    Reglas básicas:
    - Upside > 20% -> Comprar
    - Upside entre 5% y 20% -> Mantener
    - Upside < 5% -> Vender
    """
    try:
        upside = Decimal(upside)
        if upside > 20:
            return "Comprar"
        elif upside >= 5:
            return "Mantener"
        else:
            return "Vender"
    except Exception as e:
        print(f"Error generando recomendación: {e}")
        return "Esperar"

API_KEY = "d1vp4b1r01qmbi8pd5e0d1vp4b1r01qmbi8pd5eg"

def obtener_datos_finnhub(ticker):
    try:
        print(f"📡 Consultando datos de Finnhub para {ticker}...")

        # Precio actual
        url_quote = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={API_KEY}"
        r_quote = requests.get(url_quote)
        if r_quote.status_code != 200:
            print(f"❌ Error en respuesta de Finnhub: {r_quote.status_code}, {r_quote.reason}")
            return None
        precio_actual = r_quote.json().get("c")

        # Métricas (incluye PER y 52 semanas)
        url_metric = f"https://finnhub.io/api/v1/stock/metric?symbol={ticker}&metric=all&token={API_KEY}"
        r_metric = requests.get(url_metric)
        if r_metric.status_code != 200:
            print(f"❌ Error en respuesta de Finnhub: {r_metric.status_code}, {r_metric.reason}")
            return None
        metric_data = r_metric.json().get("metric", {})

        # Extraer datos
        per = metric_data.get("peInclExtraTTM")
        max_52s = metric_data.get("52WeekHigh")
        min_52s = metric_data.get("52WeekLow")

        return {
            "precio_actual": precio_actual,
            "per": per,
            "max_52s": max_52s,
            "min_52s": min_52s,
        }

    except Exception as e:
        print(f"❌ Error al obtener datos de Finnhub: {e}")
        return None
    

from .models.calendario import EventoFinanciero

ALPHA_VANTAGE_API_KEY = settings.ALPHA_VANTAGE_API_KEY


def obtener_eventos_financieros_alpha_vantage(ticker, user):
    try:
        # Earnings (resultados)
        url_earnings = f"https://www.alphavantage.co/query?function=EARNINGS&symbol={ticker}&apikey={ALPHA_VANTAGE_API_KEY}"
        r = requests.get(url_earnings)
        if r.status_code != 200:
            print(f"❌ Error al obtener resultados: {r.status_code}")
        else:
            data = r.json()
            for ev in data.get("quarterlyEarnings", []):
                EventoFinanciero.objects.get_or_create(
                    user=user,
                    ticker=ticker.upper(),
                    tipo_evento="resultado",
                    fecha=ev.get("reportedDate"),
                    descripcion=f"EPS real: {ev.get('reportedEPS')}, estimado: {ev.get('estimatedEPS')}"
                )

        # Dividendos
        url_div = f"https://www.alphavantage.co/query?function=DIVIDEND_HISTORY&symbol={ticker}&apikey={ALPHA_VANTAGE_API_KEY}"
        r2 = requests.get(url_div)
        if r2.status_code != 200:
            print(f"❌ Error al obtener dividendos: {r2.status_code}")
        else:
            dividendos = r2.json()
            for d in dividendos.get("data", []):
                EventoFinanciero.objects.get_or_create(
                    user=user,
                    ticker=ticker.upper(),
                    tipo_evento="dividendo",
                    fecha=d.get("payment_date"),
                    descripcion=f"Dividendo de {d.get('dividend')} USD."
                )
    except Exception as e:
        print(f"❌ Error obteniendo eventos financieros: {e}")

import requests
from django.conf import settings


def obtener_datos_fundamentales_alpha_vantage(ticker):
    api_key = settings.ALPHA_VANTAGE_API_KEY
    url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={api_key}"
    
    response = requests.get(url)
    data = response.json()

    print("DEBUG - Respuesta Alpha Vantage:", data)

    if "Note" in data:
        return {"error": "Límite de peticiones alcanzado. Inténtalo más tarde."}

    if not data or "Name" not in data:
        return None

    return {
        "nombre": data.get("Name"),
        "sector": data.get("Sector"),
        "industria": data.get("Industry"),
        "pais": data.get("Country"),
        "capitalizacion": data.get("MarketCapitalization"),
        "empleados": data.get("FullTimeEmployees"),
        "PER": data.get("PERatio"),
        "PEG": data.get("PEGRatio"),
        "ROE": data.get("ReturnOnEquityTTM"),
        "ROA": data.get("ReturnOnAssetsTTM"),
        "EPS": data.get("EPS"),
        "deuda_equity": data.get("DebtEquityRatio"),
        "dividendo": data.get("DividendYield")
    }


from .models.propiedad_alquilada import PropiedadAlquiler

def actualizar_meses_hipoteca():
    propiedades = PropiedadAlquiler.objects.all()
    for p in propiedades:
        if p.meses_restantes_hipoteca > 0:
            p.meses_restantes_hipoteca -= 1
            p.save()
