# backend/alpha_quantum/urls.py

from django.urls import path
from . import views
from .views import (
    index, agregar_accion, dashboard, precios_watchlist_api, editar_accion, grafico_rentabilidad, RentabilidadAPI, DashboardDataView, resumen_cartera, cartera,
    CarteraAPIView, analisis_fundamental, cashflow_dashboard, agregar_propiedad, crear_watchlist, autocompletar_ticker, eliminar_watchlist,
    agregar_prestamo, dividendos_api, cashflow_dashboard, agregar_propiedad, agregar_prestamo, dividendos_api, refrescar_watchlist, exportar_watchlist_csv,
    transaccion_crear, transacciones_export_csv, HistoricoCarteraAPI, eventos_api, cashflow_series_api, cashflow_export_csv, refrescar_watchlist_item, eliminar_watchlist_lista
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
    path("api/rentabilidad/", views.RentabilidadAPI, name="rentabilidad_api"),
    path("api/sparkline/", views.SparklineAPI.as_view(), name="api_sparkline"),

    # Auth
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('register/', views.user_register, name='register'),

    #Resumen
    path("resumen/", views.resumen_cartera, name="resumen_cartera"),
    
    # Watchlist
    path('watchlists/', views.ver_watchlists, name='ver_watchlists'),

    # CRUD de listas / items
    path('watchlist/create/', views.crear_watchlist, name='crear_watchlist'),
    path('watchlist/<int:lista_id>/add/', views.añadir_watchlist, name='añadir_watchlist'),

    # Refrescos y export
    path('watchlist/<int:lista_id>/refresh/', views.refrescar_watchlist, name='refrescar_watchlist'),
    path('watchlist/<int:lista_id>/export/', views.exportar_watchlist_csv, name='exportar_watchlist_csv'),
    path('watchlist/<int:lista_id>/<int:item_id>/refresh/', views.refrescar_watchlist_item, name='refrescar_watchlist_item'),

    # Editar / eliminar item
    path('watchlist/<int:lista_id>/<int:item_id>/edit/', views.editar_accion_watchlist, name='editar_accion_watchlist'),
    path('watchlist/<int:lista_id>/<int:item_id>/delete/', views.eliminar_watchlist, name='eliminar_watchlist'),

    # Autocompletar (puede ir aquí o más abajo; lo dejo arriba por legibilidad)
    path('watchlist/autocomplete/', views.autocompletar_ticker, name='autocompletar_ticker'),

    # Compat: redirigen al overview
    path('watchlist/', views.ver_watchlist, name='ver_watchlist'),
    path('watchlist/<int:lista_id>/', views.ver_watchlist, name='ver_watchlist_detalle'),
    path('watchlist/<int:lista_id>/delete/', views.eliminar_watchlist_lista, name='eliminar_watchlist_lista'),


    # Noticias / Fundamental / Calendario
       # Módulos adicionales: Indicadores, Bots, Macroeconomía y Foro
    path('alpha-indicators/', views.alpha_indicators, name='alpha_indicators'),
    path('alpha-bots/', views.alpha_bots, name='alpha_bots'),
    path('macroeconomia/', views.macroeconomia, name='macroeconomia'),
    path('foro/', views.foro, name='foro'),

    # Risk Lab
    path('alpha-risk/', views.alpha_risk_lab, name='alpha_risk_lab'),
 path('noticias/', views.noticias, name='noticias'),
    path('fundamental/', views.analisis_fundamental, name='fundamental'),
    path('calendario/', views.calendario, name='calendario'),
    path('api/eventos/', views.eventos_api, name='eventos_api'),

    # Cashflow
    path('flujo-de-caja/', cashflow_dashboard, name='flujo_de_caja'),
    path("api/cashflow/series", views.cashflow_series_api, name="cashflow_series_api"),
    path("cashflow/export.csv", views.cashflow_export_csv, name="cashflow_export_csv"),
    path('agregar-ingreso/', views.agregar_ingreso, name='agregar_ingreso'),
    path('agregar-gasto/', views.agregar_gasto, name='agregar_gasto'),
    path('editar-registro/<int:pk>/', views.editar_registro, name='editar_registro'),
    path('cashflow/agregar_propiedad/', agregar_propiedad, name='agregar_propiedad'),
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
