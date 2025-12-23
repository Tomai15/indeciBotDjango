from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("ajustes", views.ajustes_view, name="ajustes"),
    path("reportesPayway", views.reportePaywayListView.as_view(), name="lista_reportes"),
    path("reportesPayway/generar", views.generar_reporte_payway_view, name="generar_reporte"),
    path("reportesPayway/<int:pk>/", views.reportePaywayDetailView.as_view(), name="detalle_reporte"),
    path("reportesPayway/<int:pk>/reporteExcel/", views.exportar_reporte_excel, name="exportar_reporte"),
]