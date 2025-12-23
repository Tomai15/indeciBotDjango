"""
Tareas asíncronas para Django-Q.

Este archivo contiene todas las funciones que Django-Q puede ejecutar.
Separadas del servicio principal para mantener separación de responsabilidades.
"""
from asgiref.sync import async_to_sync

from core.services.ReportePaywayService import ReportePaywayService
from core.models import ReportePayway
from django.conf import settings
import logging
import os

logger = logging.getLogger(__name__)


# ============================================================================
# TAREA PRINCIPAL: Generar reporte de forma asíncrona
# ============================================================================

def generar_reporte_payway_async(fecha_inicio, fecha_fin, reporte_id, ruta_carpeta=None):
    """
    Genera un reporte de Payway de forma asíncrona.

    Esta función está diseñada para ser ejecutada por Django-Q workers.

    Args:
        fecha_inicio (str): Fecha de inicio en formato DD/MM/YYYY
        fecha_fin (str): Fecha de fin en formato DD/MM/YYYY
        reporte_id (int): ID del reporte creado en la base de datos
        ruta_carpeta (str, optional): Ruta donde guardar archivos.
                                      Si es None, usa MEDIA_ROOT/reportes_payway

    Returns:
        int: ID del reporte generado

    Raises:
        ValueError: Si las fechas son inválidas o faltan credenciales
        Exception: Si ocurre algún error durante la generación

    Ejemplo de uso desde view:
        from django_q.tasks import async_task

        task_id = async_task(
            'core.tasks.generar_reporte_payway_async',
            '01/12/2024',
            '10/12/2024',
            reporte_id,
            hook='core.tasks.notificar_reporte_completado'
        )
    """
    logger.info(f"[Django-Q] Iniciando generación asíncrona: {fecha_inicio} - {fecha_fin}")

    try:
        # Obtener el reporte de la base de datos
        nuevo_reporte = ReportePayway.objects.get(id=reporte_id)

        # Configurar ruta si no se proporcionó
        if ruta_carpeta is None:
            ruta_carpeta = os.path.join(settings.MEDIA_ROOT, 'reportes_payway')

        # Instanciar el servicio
        servicio = ReportePaywayService(ruta_carpeta=ruta_carpeta)
        reporte_id = async_to_sync(servicio.generar_reporte)(
            fecha_inicio,
            fecha_fin,
            nuevo_reporte
        )
        # Ejecutar la generación (puede tardar minutos u horas)

        logger.info(f"[Django-Q] Reporte {reporte_id} generado exitosamente")
        return reporte_id

    except Exception as e:
        logger.error(f"[Django-Q] Error al generar reporte: {e}", exc_info=True)
        raise


