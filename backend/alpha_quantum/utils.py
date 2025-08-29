import datetime
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import Sum

from .models import Accion, PrecioHistorico
from .models.historico import HistoricoCartera
from .models.dividendo import Dividendo
from .models.calendario import EventoFinanciero
from .models.transaccion import Transaccion

# === Claves de API (desde settings.py) ===
TWELVE_DATA_API_KEY = getattr(settings, "TWELVE_DATA_API_KEY", None)
FINNHUB_API_KEY = getattr(settings, "FINNHUB_API_KEY", None)
ALPHA_VANTAGE_API_KEY = getattr(settings, "ALPHA_VANTAGE_API_KEY", None)


# =============================================================================
# Precios e históricos (Twelve Data)
# =============================================================================
def obtener_precio_actual(ticker: str) -> float:
    """Devuelve el precio actual del ticker desde Twelve Data."""
    if not TWELVE_DATA_API_KEY:
        print("API Key de Twelve Data no configurada.")
        return 0.0

    url = f"https://api.twelvedata.com/price?symbol={ticker}&apikey={TWELVE_DATA_API_KEY}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        return float(data.get("price", 0.0))
    except Exception as e:
        print(f"Error al obtener precio actual para {ticker}: {e}")
        return 0.0


def actualizar_historico(accion: Accion, dias: int = 365) -> None:
    """
    Carga/actualiza precios históricos de una acción vía Twelve Data
    y persiste en PrecioHistorico (intervalo diario).
    """
    if not TWELVE_DATA_API_KEY:
        print("API Key de Twelve Data no configurada.")
        return

    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": accion.ticker,
        "interval": "1day",
        "outputsize": dias,
        "apikey": TWELVE_DATA_API_KEY,
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        for punto in data.get("values", []):
            fecha = datetime.datetime.strptime(punto["datetime"], "%Y-%m-%d").date()
            cierre = Decimal(str(punto["close"]))
            PrecioHistorico.objects.update_or_create(
                accion=accion,
                fecha=fecha,
                defaults={"precio_cierre": cierre},
            )
    except Exception as e:
        print(f"Error al actualizar histórico para {accion.ticker}: {e}")


def calcular_resumen(acciones):
    """KPIs básicos de la cartera: total invertido, valor actual y rentabilidad absoluta."""
    total_invertido = Decimal("0")
    valor_actual = Decimal("0")

    for accion in acciones:
        try:
            cantidad = Decimal(str(accion.cantidad))
            precio_compra = Decimal(str(accion.precio_compra or 0))
            precio_actual = Decimal(str(accion.precio_actual or 0))

            total_invertido += precio_compra * cantidad
            valor_actual += precio_actual * cantidad
        except (InvalidOperation, AttributeError, TypeError, ValueError):
            continue

    rentabilidad = valor_actual - total_invertido
    return {
        "total_invertido": float(total_invertido),
        "valor_actual": float(valor_actual),
        "rentabilidad": float(rentabilidad),
    }


# =============================================================================
# Serie de precios (para gráfico) + fundamentales
# =============================================================================
def obtener_serie_precios_diaria(ticker: str, dias: int = 100):
    """
    Devuelve dos listas (fechas ASC, cierres ASC).
    Prefiere Twelve Data. Si no hay clave, intenta Alpha Vantage.
    """
    # 1) Twelve Data
    if TWELVE_DATA_API_KEY:
        try:
            url = "https://api.twelvedata.com/time_series"
            params = {
                "symbol": ticker,
                "interval": "1day",
                "outputsize": dias,
                "order": "ASC",   # fechas en ascendente
                "apikey": TWELVE_DATA_API_KEY,
            }
            r = requests.get(url, params=params, timeout=15)
            r.raise_for_status()
            js = r.json()
            vals = js.get("values", [])
            fechas = [row["datetime"][:10] for row in vals]
            cierres = [float(row["close"]) for row in vals]
            return fechas, cierres
        except Exception as e:
            print(f"[TwelveData] Serie diaria error {ticker}: {e}")

    # 2) Alpha Vantage (fallback)
    if ALPHA_VANTAGE_API_KEY:
        try:
            url = "https://www.alphavantage.co/query"
            params = {
                "function": "TIME_SERIES_DAILY_ADJUSTED",
                "symbol": ticker,
                "outputsize": "compact",  # ~100 días
                "apikey": ALPHA_VANTAGE_API_KEY,
            }
            r = requests.get(url, params=params, timeout=20)
            r.raise_for_status()
            js = r.json()
            ts = js.get("Time Series (Daily)") or {}
            fechas = sorted(ts.keys())
            cierres = []
            for d in fechas:
                item = ts[d]
                c = item.get("5. adjusted close") or item.get("4. close")
                cierres.append(float(c))
            # recorta por si vienen más de 'dias'
            if len(fechas) > dias:
                fechas = fechas[-dias:]
                cierres = cierres[-dias:]
            return fechas, cierres
        except Exception as e:
            print(f"[AlphaVantage] Serie diaria error {ticker}: {e}")

    return [], []


def get_prices_and_fundamentals(ticker: str):
    """
    Helper para la vista de Análisis Fundamental:
    - fechas + cierres (ASC, hasta hoy)
    - fundamentales 'normalizados' (campos clave)
    """
    fechas, cierres = obtener_serie_precios_diaria(ticker, dias=100)
    fun = obtener_datos_fundamentales_alpha_vantage(ticker) or {}

    # Normaliza nombres para la UI
    fundamentales = {
        "Name": fun.get("nombre"),
        "Sector": fun.get("sector"),
        "Industry": fun.get("industria"),
        "Country": fun.get("pais"),
        "FullTimeEmployees": fun.get("empleados"),
        "PER": _to_float(fun.get("PER")),
        "ROE": _to_float(fun.get("ROE")),
        "ROIC": None,  # Alpha Vantage OVERVIEW no expone ROIC/ROI
        "DebtToEquity": _to_float(fun.get("deuda_equity")),
        "EPS": _to_float(fun.get("EPS")),
        "DividendPerShare": _to_float(fun.get("dividendo")),
        "MarketCapitalization": _to_float(fun.get("capitalizacion")),
        "NetIncomeTTM": None,  # OVERVIEW no incluye NetIncomeTTM
    }
    return fechas, cierres, fundamentales


def _to_float(v):
    try:
        if v in (None, "", "N/A", "None"):
            return None
        return float(v)
    except Exception:
        return None


# =============================================================================
# Watchlist y fundamentos (Finnhub / Alpha Vantage)
# =============================================================================
def obtener_datos_finnhub(ticker: str):
    """Devuelve precio actual y métricas básicas (PER, 52w high/low) desde Finnhub."""
    if not FINNHUB_API_KEY:
        print("API Key de Finnhub no configurada.")
        return None
    try:
        # Precio actual
        url_quote = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_API_KEY}"
        r_quote = requests.get(url_quote, timeout=10)
        if r_quote.status_code != 200:
            print(f"Error Finnhub (quote): {r_quote.status_code} {r_quote.reason}")
            return None
        precio_actual = r_quote.json().get("c")

        # Métricas
        url_metric = f"https://finnhub.io/api/v1/stock/metric?symbol={ticker}&metric=all&token={FINNHUB_API_KEY}"
        r_metric = requests.get(url_metric, timeout=10)
        if r_metric.status_code != 200:
            print(f"Error Finnhub (metric): {r_metric.status_code} {r_metric.reason}")
            return None
        metric_data = r_metric.json().get("metric", {})

        return {
            "precio_actual": precio_actual,
            "per": metric_data.get("peInclExtraTTM"),
            "max_52s": metric_data.get("52WeekHigh"),
            "min_52s": metric_data.get("52WeekLow"),
        }
    except Exception as e:
        print(f"Error al obtener datos de Finnhub: {e}")
        return None


def obtener_datos_fundamentales_alpha_vantage(ticker: str):
    """Datos fundamentales (resumen) vía Alpha Vantage OVERVIEW."""
    if not ALPHA_VANTAGE_API_KEY:
        print("API Key de Alpha Vantage no configurada.")
        return None

    url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={ALPHA_VANTAGE_API_KEY}"
    try:
        r = requests.get(url, timeout=15)
        data = r.json()

        if "Note" in data:
            return {"error": "Límite de peticiones de Alpha Vantage alcanzado. Intenta más tarde."}
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
            "dividendo": data.get("DividendYield"),
        }
    except Exception as e:
        print(f"Error OVERVIEW Alpha Vantage: {e}")
        return None


def obtener_eventos_financieros_alpha_vantage(ticker: str, user):
    """
    Guarda eventos de Resultados y Dividendos en tu modelo EventoFinanciero.
    (Útil para el calendario)
    """
    if not ALPHA_VANTAGE_API_KEY:
        print("API Key de Alpha Vantage no configurada.")
        return

    try:
        # Earnings
        url_earnings = f"https://www.alphavantage.co/query?function=EARNINGS&symbol={ticker}&apikey={ALPHA_VANTAGE_API_KEY}"
        r = requests.get(url_earnings, timeout=15)
        if r.status_code == 200:
            data = r.json()
            for ev in data.get("quarterlyEarnings", []):
                EventoFinanciero.objects.get_or_create(
                    user=user,
                    ticker=ticker.upper(),
                    tipo_evento="resultado",
                    fecha=ev.get("reportedDate"),
                    descripcion=f"EPS real: {ev.get('reportedEPS')} / estimado: {ev.get('estimatedEPS')}",
                )

        # Dividendos (histórico)
        url_div = f"https://www.alphavantage.co/query?function=DIVIDEND_HISTORY&symbol={ticker}&apikey={ALPHA_VANTAGE_API_KEY}"
        r2 = requests.get(url_div, timeout=15)
        if r2.status_code == 200:
            dividendos = r2.json()
            for d in dividendos.get("data", []):
                EventoFinanciero.objects.get_or_create(
                    user=user,
                    ticker=ticker.upper(),
                    tipo_evento="dividendo",
                    fecha=d.get("payment_date"),
                    descripcion=f"Dividendo de {d.get('dividend')} USD.",
                )
    except Exception as e:
        print(f"Error obteniendo eventos financieros: {e}")


# =============================================================================
# Reglas simples de valoración (watchlist)
# =============================================================================
def calcular_upside(valor_objetivo, precio_actual):
    if valor_objetivo is None or precio_actual is None:
        return None
    try:
        return ((Decimal(valor_objetivo) - Decimal(precio_actual)) / Decimal(precio_actual)) * 100
    except Exception as e:
        print(f"Error calculando upside: {e}")
        return None


def generar_recomendacion(upside):
    """
    Regla solicitada:
      > 10%  -> COMPRAR
      0–10%  -> REVISAR
      < 0%   -> ESPERAR
    """
    if upside is None:
        return None
    try:
        up = Decimal(upside)
    except Exception:
        return None

    if up > Decimal("10"):
        return "COMPRAR"
    elif up < Decimal("0"):
        return "ESPERAR"
    else:
        return "REVISAR"


# =============================================================================
# Cashflow/propiedades (utilidad)
# =============================================================================
from .models.propiedad_alquilada import PropiedadAlquiler  # noqa: E402


def actualizar_meses_hipoteca():
    """Resta 1 mes a todas las hipotecas (si > 0)."""
    for p in PropiedadAlquiler.objects.all():
        if p.meses_restantes_hipoteca > 0:
            p.meses_restantes_hipoteca -= 1
            p.save()


# =============================================================================
# Snapshots de cartera (gráfica histórica)
# =============================================================================
def snapshot_cartera_diario(user):
    """
    Guarda/actualiza el snapshot de HOY (valor e invertido) para el usuario.
    Idempotente por unique_together(user, fecha).
    """
    hoy = date.today()
    acciones = Accion.objects.filter(user=user)

    valor = Decimal("0")
    invertido = Decimal("0")
    for a in acciones:
        qty = Decimal(str(a.cantidad or 0))
        pa = Decimal(str(a.precio_actual or 0))
        pc = Decimal(str(a.precio_compra or 0))
        valor += qty * pa
        invertido += qty * pc

    with transaction.atomic():
        HistoricoCartera.objects.update_or_create(
            user=user,
            fecha=hoy,
            defaults={"valor": valor, "invertido": invertido},
        )


def backfill_snapshots(user, days: int = 90):
    """
    Rellena snapshots aproximados para los últimos 'days' días
    usando el precio actual (si no tienes PrecioHistorico diario).
    """
    acciones = Accion.objects.filter(user=user)
    hoy = date.today()
    for i in range(days, -1, -1):
        d = hoy - timedelta(days=i)
        valor = Decimal("0")
        invertido = Decimal("0")
        for a in acciones:
            qty = Decimal(str(a.cantidad or 0))
            pa = Decimal(str(a.precio_actual or 0))  # aproximación
            pc = Decimal(str(a.precio_compra or 0))
            valor += qty * pa
            invertido += qty * pc
        with transaction.atomic():
            HistoricoCartera.objects.update_or_create(
                user=user,
                fecha=d,
                defaults={"valor": valor, "invertido": invertido},
            )


def shares_on_date(user, ticker: str, fecha: date) -> Decimal:
    """
    Número de acciones del ticker que el usuario tenía en 'fecha'
    (suma BUY - SELL de transacciones <= fecha).
    """
    qs = (
        Transaccion.objects.filter(user=user, ticker__iexact=ticker, fecha__lte=fecha)
        .order_by("fecha", "id")
    )
    pos = Decimal("0")
    for t in qs:
        qty = Decimal(str(t.cantidad or 0))
        if t.tipo in ("BUY", "buy", "Compra", "compra"):
            pos += qty
        elif t.tipo in ("SELL", "sell", "Venta", "venta"):
            pos -= qty
        # DIV no cambia posición
    return pos if pos > 0 else Decimal("0")
