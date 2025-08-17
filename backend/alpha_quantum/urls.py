# backend/alpha_quantum/urls.py

from django.urls import path
from . import views
from .views import (
    index, agregar_accion, dashboard, precios_watchlist_api, editar_accion,
    DashboardDataView, resumen_cartera, cartera,
    grafico_rentabilidad, RentabilidadAPI,
    CarteraAPIView, analisis_fundamental, cashflow_dashboard, agregar_propiedad,
    agregar_prestamo, dividendos_api, cashflow_dashboard, agregar_propiedad, agregar_prestamo, dividendos_api,
    transaccion_crear, transacciones_export_csv, HistoricoCarteraAPI, eventos_api, watchlist_data
)

urlpatterns = [
    # Home / Acciones
    path('', index, name='index'),
    path('agregar/', agregar_accion, name='agregar_accion'),

    # Dashboard
    path('dashboard/', dashboard, name='dashboard'),
    path('editar-accion/<int:pk>/', editar_accion, name='editar_accion'),
    path('cartera/', cartera, name='cartera'),

    # APIs usadas por el dashboard
    path('api/historico/', HistoricoCarteraAPI.as_view(), name='api_historico'),
    path('api/cartera/', CarteraAPIView.as_view(), name='api_cartera'),
    path('api/dividendos/', dividendos_api, name='api_dividendos'),

    # Auth
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('register/', views.user_register, name='register'),

    #Resumen
    path("resumen/", views.resumen_cartera, name="resumen_cartera"),
    
    # Watchlist
    path('watchlist/', views.ver_watchlist, name='ver_watchlist'),
    path('watchlist/añadir/', views.añadir_watchlist, name='añadir_watchlist'),
    path('watchlist/editar/<int:pk>/', views.editar_accion_watchlist, name='editar_accion_watchlist'),
    path('watchlist/eliminar/<int:pk>/', views.eliminar_accion_watchlist, name='eliminar_watchlist'),
    path('watchlist/data/', watchlist_data, name='watchlist_data'),
    path('api/watchlist/precios/', views.precios_watchlist_api, name='api_watchlist_precios'),

    # Noticias / Fundamental / Calendario
    path('noticias/', views.noticias, name='noticias'),
    path('fundamental/', views.analisis_fundamental, name='fundamental'),
    path('calendario/', views.calendario, name='calendario'),
    path('api/eventos/', views.eventos_api, name='eventos_api'),

    # Cashflow
    path('flujo-de-caja/', cashflow_dashboard, name='flujo_de_caja'),
    path('agregar-ingreso/', views.agregar_ingreso, name='agregar_ingreso'),
    path('agregar-gasto/', views.agregar_gasto, name='agregar_gasto'),
    path('editar-registro/<int:pk>/', views.editar_registro, name='editar_registro'),
    path('agregar_propiedad/', agregar_propiedad, name='agregar_propiedad'),
    path('cashflow/agregar_prestamo/', agregar_prestamo, name='agregar_prestamo'),
    path('cashflow/registro/<int:pk>/eliminar/', views.eliminar_registro, name='eliminar_registro'),
    path('cashflow/propiedad/<int:pk>/editar/', views.editar_propiedad, name='editar_propiedad'),
    path('cashflow/propiedad/<int:pk>/eliminar/', views.eliminar_propiedad, name='eliminar_propiedad'),
    path('cashflow/prestamo/<int:pk>/editar/', views.editar_prestamo, name='editar_prestamo'),
    path('cashflow/prestamo/<int:pk>/eliminar/', views.eliminar_prestamo, name='eliminar_prestamo'),

    # Dividendos (formularios modal)
    path('dividendos/crear/', views.dividendo_crear, name='dividendo_crear'),
    path('dividendos/<int:pk>/editar/', views.dividendo_editar, name='dividendo_editar'),
    path('dividendos/<int:pk>/borrar/', views.dividendo_borrar, name='dividendo_borrar'),

    # Transacciones (formularios modal) + CSV
    path('transacciones/crear/', views.transaccion_crear, name='transaccion_crear'),
    path('transacciones/<int:pk>/editar/', views.transaccion_editar, name='transaccion_editar'),
    path('transacciones/<int:pk>/borrar/', views.transaccion_borrar, name='transaccion_borrar'),
    path('transacciones/export/csv/', views.transacciones_export_csv, name='transacciones_export_csv'),
]