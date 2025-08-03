# backend/alpha_quantum/urls.py

from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from .views import (
    index, agregar_accion, dashboard,
    DashboardDataView, resumen_cartera,
    grafico_rentabilidad, RentabilidadAPI,
    CarteraAPIView, cartera, editar_accion, watchlist_data, analisis_fundamental, cashflow_dashboard, agregar_propiedad, agregar_prestamo
)

urlpatterns = [
    path('', index, name='index'),
    path('agregar/', agregar_accion, name='agregar_accion'),
    path('dashboard/', dashboard, name='dashboard'),
    path('api/dashboard/', DashboardDataView.as_view(), name='dashboard_data'),
    path('api/rentabilidad/', RentabilidadAPI.as_view(), name='api_rentabilidad'),
    path('api/resumen/', resumen_cartera, name='resumen_cartera'),
    path('grafico/', grafico_rentabilidad, name='grafico_rentabilidad'),
    path('api/cartera/', CarteraAPIView.as_view(), name='api_cartera'),
    path('cartera/', cartera, name='cartera'),
    path('editar-accion/<int:pk>/', editar_accion, name='editar_accion'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('register/', views.user_register, name='register'),
    path('watchlist/', views.ver_watchlist, name='ver_watchlist'),
    path('watchlist/añadir/', views.añadir_watchlist, name='añadir_watchlist'),
    path('watchlist/editar/<int:pk>/', views.editar_accion_watchlist, name='editar_accion_watchlist'),
    path('watchlist/eliminar/<int:id>/', views.eliminar_accion_watchlist, name='eliminar_watchlist'),
    path('watchlist/data/', watchlist_data, name='watchlist_data'),
    path('api/watchlist/precios/', views.precios_watchlist_api, name='api_watchlist_precios'),
    path('noticias/', views.noticias, name='noticias'),
    path('fundamental/', views.analisis_fundamental, name='fundamental'),
    path('calendario/', views.calendario, name='calendario'),
    path("api/eventos/", views.eventos_api, name="eventos_api"),
    path('flujo-de-caja/', views.cashflow_dashboard, name='flujo_de_caja'),
    path('agregar-ingreso/', views.agregar_ingreso, name='agregar_ingreso'),
    path('agregar-gasto/', views.agregar_gasto, name='agregar_gasto'),
    path('editar-registro/<int:pk>/', views.editar_registro, name='editar_registro'),
    path('agregar_propiedad/', views.agregar_propiedad, name='agregar_propiedad'),
    path('agregar_prestamo/', views.agregar_prestamo, name='agregar_prestamo'),

]
