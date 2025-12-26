from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView
from django.views.generic.detail import SingleObjectMixin
from django.http import FileResponse, Http404
from django.contrib import messages
from django.db.models import Sum, Count, Q
import os

from django_q.tasks import async_task

from core.models import ReportePayway, ReporteVtex, ReporteCDP, UsuarioPayway, UsuarioCDP
from core.forms import (
    GenerarReportePaywayForm,
    GenerarReporteVtexForm,
    GenerarReporteCDPForm,
    CredencialesPaywayForm,
    CredencialesCDPForm
)


# Create your views here.
def home(request):
    return render(request, 'core/home.html')

class reportePaywayListView(ListView):
    model = ReportePayway
    paginate_by = 50
    template_name = 'core/Payway/vistaReportes.html'
    ordering = ['-id']


class reportePaywayDetailView(SingleObjectMixin, ListView):
    """
    Vista de detalle de reporte con paginación server-side de transacciones.

    Combina SingleObjectMixin (para obtener el reporte) con ListView (para paginar transacciones).
    Esto permite manejar eficientemente reportes con miles de transacciones.
    """
    template_name = 'core/Payway/detalleReporte.html'
    paginate_by = 20  # Transacciones por página
    context_object_name = 'transacciones'

    def get(self, request, *args, **kwargs):
        # Obtener el reporte (SingleObjectMixin)
        self.object = self.get_object(queryset=ReportePayway.objects.all())
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        # Obtener transacciones del reporte actual, ordenadas por fecha descendente
        return self.object.transacciones.all().order_by('-fecha_hora')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Agregar el reporte al contexto
        context['reporte'] = self.object
        return context


def exportar_reporte_excel(request, pk):
    """Vista para exportar un reporte de Payway a Excel."""
    reporte = get_object_or_404(ReportePayway, pk=pk)

    # El modelo es responsable de generar el archivo y retornar su ruta
    ruta_archivo = reporte.generar_reporter_excel()

    if not os.path.exists(ruta_archivo):
        raise Http404("El archivo no se generó correctamente")

    nombre_archivo = os.path.basename(ruta_archivo)

    response = FileResponse(
        open(ruta_archivo, 'rb'),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'

    return response


def generar_reporte_payway_view(request):
    """
    Vista para generar un nuevo reporte de Payway.

    Muestra un formulario para ingresar fechas y encola la generación del reporte.
    """
    if request.method == 'POST':
        form = GenerarReportePaywayForm(request.POST)

        if form.is_valid():
            # Verificar que existan credenciales configuradas
            credenciales = UsuarioPayway.objects.first()

            if not credenciales:
                messages.error(
                    request,
                    'No hay credenciales de Payway configuradas. '
                    'Por favor, configure las credenciales en Ajustes antes de generar un reporte.'
                )
                return render(request, 'core/Payway/generarReporte.html', {'form': form})

            # Obtener fechas del formulario
            fecha_inicio = form.cleaned_data['fecha_inicio']
            fecha_fin = form.cleaned_data['fecha_fin']

            # Formatear fechas para el servicio (DD/MM/YYYY)
            fecha_inicio_str = fecha_inicio.strftime("%d/%m/%Y")
            fecha_fin_str = fecha_fin.strftime("%d/%m/%Y")

            # Crear el reporte en estado PENDIENTE
            nuevo_reporte = ReportePayway.objects.create(
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                estado=ReportePayway.Estado.PENDIENTE
            )

            # Encolar tarea en Django-Q
            try:
                task_id = async_task(
                    'core.tasks.generar_reporte_payway_async',
                    fecha_inicio_str,
                    fecha_fin_str,
                    nuevo_reporte.id  # Pasar solo el ID, no el objeto completo
                )

                messages.success(
                    request,
                    f'Reporte encolado exitosamente. Puede visualizarlo en Reportes Generados.'
                )

                return redirect('lista_reportes')

            except Exception as e:
                messages.error(
                    request,
                    f'Error al crear el reporte: {str(e)}'
                )

    else:
        form = GenerarReportePaywayForm()

    return render(request, 'core/Payway/generarReporte.html', {'form': form})


# ==================== VISTAS VTEX ====================

class reporteVtexListView(ListView):
    """Vista de lista de reportes de VTEX con paginación."""
    model = ReporteVtex
    paginate_by = 50
    template_name = 'core/Vtex/vistaReportes.html'
    ordering = ['-id']


class reporteVtexDetailView(SingleObjectMixin, ListView):
    """
    Vista de detalle de reporte VTEX con paginación server-side de transacciones.

    Combina SingleObjectMixin (para obtener el reporte) con ListView (para paginar transacciones).
    Esto permite manejar eficientemente reportes con miles de transacciones.
    """
    template_name = 'core/Vtex/detalleReporte.html'
    paginate_by = 20  # Transacciones por página
    context_object_name = 'transacciones'

    def get(self, request, *args, **kwargs):
        # Obtener el reporte (SingleObjectMixin)
        self.object = self.get_object(queryset=ReporteVtex.objects.all())
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        # Obtener transacciones del reporte actual, ordenadas por fecha descendente
        return self.object.transacciones.all().order_by('-fecha_hora')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Agregar el reporte al contexto
        context['reporte'] = self.object
        return context


def exportar_reporte_vtex_excel(request, pk):
    """Vista para exportar un reporte de VTEX a Excel."""
    reporte = get_object_or_404(ReporteVtex, pk=pk)

    # El modelo es responsable de generar el archivo y retornar su ruta
    ruta_archivo = reporte.generar_reporter_excel()

    if not os.path.exists(ruta_archivo):
        raise Http404("El archivo no se generó correctamente")

    nombre_archivo = os.path.basename(ruta_archivo)

    response = FileResponse(
        open(ruta_archivo, 'rb'),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'

    return response


def generar_reporte_vtex_view(request):
    """
    Vista para generar un nuevo reporte de VTEX.

    Muestra un formulario para ingresar fechas y encola la generación del reporte.
    """
    if request.method == 'POST':
        form = GenerarReporteVtexForm(request.POST)

        if form.is_valid():
            # Obtener fechas del formulario
            fecha_inicio = form.cleaned_data['fecha_inicio']
            fecha_fin = form.cleaned_data['fecha_fin']

            # Formatear fechas para el servicio (DD/MM/YYYY)
            fecha_inicio_str = fecha_inicio.strftime("%d/%m/%Y")
            fecha_fin_str = fecha_fin.strftime("%d/%m/%Y")

            # Crear el reporte en estado PENDIENTE
            nuevo_reporte = ReporteVtex.objects.create(
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                estado=ReporteVtex.Estado.PENDIENTE
            )

            # Encolar tarea en Django-Q
            try:
                task_id = async_task(
                    'core.tasks.generar_reporte_vtex_async',
                    fecha_inicio_str,
                    fecha_fin_str,
                    nuevo_reporte.id  # Pasar solo el ID, no el objeto completo
                )

                messages.success(
                    request,
                    f'Reporte de VTEX encolado exitosamente. Puede visualizarlo en Reportes Generados.'
                )

                return redirect('lista_reportes_vtex')

            except Exception as e:
                messages.error(
                    request,
                    f'Error al crear el reporte de VTEX: {str(e)}'
                )

    else:
        form = GenerarReporteVtexForm()

    return render(request, 'core/Vtex/generarReporte.html', {'form': form})


# ==================== VISTA DE AJUSTES ====================

def ajustes_view(request):
    """
    Vista para gestionar credenciales de Payway y CDP.

    Permite ver y editar las credenciales de ambas plataformas.
    """
    # Obtener o crear instancias de credenciales
    credenciales_payway = UsuarioPayway.objects.first()
    credenciales_cdp = UsuarioCDP.objects.first()

    if request.method == 'POST':
        # Determinar qué formulario se envió
        if 'payway_submit' in request.POST:
            form_payway = CredencialesPaywayForm(request.POST, instance=credenciales_payway)

            if form_payway.is_valid():
                form_payway.save()
                messages.success(request, 'Credenciales de Payway actualizadas exitosamente.')
                return redirect('ajustes')

            # Si hay errores, mantener el otro formulario sin cambios
            form_cdp = CredencialesCDPForm(instance=credenciales_cdp)

        elif 'cdp_submit' in request.POST:
            form_cdp = CredencialesCDPForm(request.POST, instance=credenciales_cdp)

            if form_cdp.is_valid():
                form_cdp.save()
                messages.success(request, 'Credenciales de CDP actualizadas exitosamente.')
                return redirect('ajustes')

            # Si hay errores, mantener el otro formulario sin cambios
            form_payway = CredencialesPaywayForm(instance=credenciales_payway)

        else:
            # No debería llegar aquí, pero por seguridad
            form_payway = CredencialesPaywayForm(instance=credenciales_payway)
            form_cdp = CredencialesCDPForm(instance=credenciales_cdp)

    else:
        # GET request - mostrar formularios
        form_payway = CredencialesPaywayForm(instance=credenciales_payway)
        form_cdp = CredencialesCDPForm(instance=credenciales_cdp)

    context = {
        'form_payway': form_payway,
        'form_cdp': form_cdp,
        'tiene_payway': credenciales_payway is not None,
        'tiene_cdp': credenciales_cdp is not None,
    }

    return render(request, 'core/ajustes.html', context)


# ==================== VISTAS CDP ====================

class reporteCDPListView(ListView):
    """Vista de lista de reportes de CDP con paginación."""
    model = ReporteCDP
    paginate_by = 50
    template_name = 'core/CDP/vistaReportes.html'
    ordering = ['-id']


class reporteCDPDetailView(SingleObjectMixin, ListView):
    """
    Vista de detalle de reporte CDP con paginación server-side de transacciones.

    Combina SingleObjectMixin (para obtener el reporte) con ListView (para paginar transacciones).
    Esto permite manejar eficientemente reportes con miles de transacciones.
    """
    template_name = 'core/CDP/detalleReporte.html'
    paginate_by = 20  # Transacciones por página
    context_object_name = 'transacciones'

    def get(self, request, *args, **kwargs):
        # Obtener el reporte (SingleObjectMixin)
        self.object = self.get_object(queryset=ReporteCDP.objects.all())
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        # Obtener transacciones del reporte actual, ordenadas por fecha descendente
        return self.object.transacciones.all().order_by('-fecha_hora')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Agregar el reporte al contexto
        context['reporte'] = self.object
        return context


def exportar_reporte_cdp_excel(request, pk):
    """Vista para exportar un reporte de CDP a Excel."""
    reporte = get_object_or_404(ReporteCDP, pk=pk)

    # El modelo es responsable de generar el archivo y retornar su ruta
    ruta_archivo = reporte.generar_reporter_excel()

    if not os.path.exists(ruta_archivo):
        raise Http404("El archivo no se generó correctamente")

    nombre_archivo = os.path.basename(ruta_archivo)

    response = FileResponse(
        open(ruta_archivo, 'rb'),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'

    return response


def generar_reporte_cdp_view(request):
    """
    Vista para generar un nuevo reporte de CDP.

    Muestra un formulario para ingresar fechas y encola la generación del reporte.
    """
    if request.method == 'POST':
        form = GenerarReporteCDPForm(request.POST)

        if form.is_valid():
            # Verificar que existan credenciales configuradas
            credenciales = UsuarioCDP.objects.first()

            if not credenciales:
                messages.error(
                    request,
                    'No hay credenciales de CDP configuradas. '
                    'Por favor, configure las credenciales en Ajustes antes de generar un reporte.'
                )
                return render(request, 'core/CDP/generarReporte.html', {'form': form})

            # Obtener fechas del formulario
            fecha_inicio = form.cleaned_data['fecha_inicio']
            fecha_fin = form.cleaned_data['fecha_fin']

            # Formatear fechas para el servicio (DD/MM/YYYY)
            fecha_inicio_str = fecha_inicio.strftime("%d/%m/%Y")
            fecha_fin_str = fecha_fin.strftime("%d/%m/%Y")

            # Crear el reporte en estado PENDIENTE
            nuevo_reporte = ReporteCDP.objects.create(
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                estado=ReporteCDP.Estado.PENDIENTE
            )

            # Encolar tarea en Django-Q
            try:
                task_id = async_task(
                    'core.tasks.generar_reporte_cdp_async',
                    fecha_inicio_str,
                    fecha_fin_str,
                    nuevo_reporte.id  # Pasar solo el ID, no el objeto completo
                )

                messages.success(
                    request,
                    f'Reporte de CDP encolado exitosamente. Puede visualizarlo en Reportes Generados.'
                )

                return redirect('lista_reportes_cdp')

            except Exception as e:
                messages.error(
                    request,
                    f'Error al crear el reporte de CDP: {str(e)}'
                )

    else:
        form = GenerarReporteCDPForm()

    return render(request, 'core/CDP/generarReporte.html', {'form': form})
