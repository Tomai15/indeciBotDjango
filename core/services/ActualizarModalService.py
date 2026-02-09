from __future__ import annotations

import os
import logging

import requests
import pandas as pd
from datetime import datetime
from django.conf import settings
from asgiref.sync import sync_to_async

from core.models import TareaCatalogacion, UsuarioVtex

logger: logging.Logger = logging.getLogger(__name__)


class ActualizarModalService:

    async def ejecutar(self, tarea: TareaCatalogacion, lista_skus: list[dict]) -> None:
        """
        Para cada SKU: GET datos actuales, modifica ModalType, PUT datos actualizados.
        Genera un Excel con los resultados.
        """
        await sync_to_async(self._actualizar_estado)(tarea, TareaCatalogacion.Estado.PROCESANDO)

        try:
            credenciales = await sync_to_async(UsuarioVtex.objects.first)()
            if not credenciales:
                await self._log(tarea, "Error: No hay credenciales VTEX configuradas en Ajustes.")
                await sync_to_async(self._actualizar_estado)(tarea, TareaCatalogacion.Estado.ERROR)
                return

            base_url = f"https://{credenciales.account_name}.vtexcommercestable.com.br/api/catalog/pvt/stockkeepingunit"
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'X-VTEX-API-AppKey': credenciales.app_key,
                'X-VTEX-API-AppToken': credenciales.app_token,
            }

            resultados = []

            for item in lista_skus:
                sku_id = item['skuid']
                modal_nuevo = item['modal']
                await self._log(tarea, f"Procesando SKU {sku_id} - Modal deseado: {modal_nuevo}")

                # GET datos actuales
                try:
                    resp_get = requests.get(f"{base_url}/{sku_id}", headers=headers, timeout=30)
                    if resp_get.status_code != 200:
                        await self._log(tarea, f"Error GET SKU {sku_id}: HTTP {resp_get.status_code}")
                        resultados.append({
                            'skuid': sku_id, 'modal_anterior': 'ERROR',
                            'modal_nuevo': modal_nuevo, 'estado': f'Error GET: HTTP {resp_get.status_code}'
                        })
                        await self._incrementar_progreso(tarea)
                        continue

                    datos_sku = resp_get.json()
                    modal_anterior = datos_sku.get('ModalType', None)
                    await self._log(tarea, f"SKU {sku_id} - Modal actual: {modal_anterior}")

                except Exception as e:
                    await self._log(tarea, f"Excepcion GET SKU {sku_id}: {e}")
                    resultados.append({
                        'skuid': sku_id, 'modal_anterior': 'ERROR',
                        'modal_nuevo': modal_nuevo, 'estado': f'Excepcion GET: {str(e)[:100]}'
                    })
                    await self._incrementar_progreso(tarea)
                    continue

                # Modificar ModalType y PUT
                datos_sku['ModalType'] = modal_nuevo
                try:
                    resp_put = requests.put(f"{base_url}/{sku_id}", headers=headers, json=datos_sku, timeout=30)
                    if resp_put.status_code == 200:
                        await self._log(tarea, f"SKU {sku_id} actualizado: {modal_anterior} -> {modal_nuevo}")
                        resultados.append({
                            'skuid': sku_id, 'modal_anterior': modal_anterior,
                            'modal_nuevo': modal_nuevo, 'estado': 'OK'
                        })
                    else:
                        await self._log(tarea, f"Error PUT SKU {sku_id}: HTTP {resp_put.status_code}")
                        resultados.append({
                            'skuid': sku_id, 'modal_anterior': modal_anterior,
                            'modal_nuevo': modal_nuevo, 'estado': f'Error PUT: HTTP {resp_put.status_code}'
                        })
                except Exception as e:
                    await self._log(tarea, f"Excepcion PUT SKU {sku_id}: {e}")
                    resultados.append({
                        'skuid': sku_id, 'modal_anterior': modal_anterior,
                        'modal_nuevo': modal_nuevo, 'estado': f'Excepcion PUT: {str(e)[:100]}'
                    })

                await self._incrementar_progreso(tarea)

            # Generar Excel de resultados
            carpeta = os.path.join(settings.MEDIA_ROOT, 'catalogacion')
            os.makedirs(carpeta, exist_ok=True)
            nombre_archivo = f'ResultadosModal-{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            ruta_final = os.path.join(carpeta, nombre_archivo)
            pd.DataFrame(resultados).to_excel(ruta_final, index=False)

            exitosos = sum(1 for r in resultados if r['estado'] == 'OK')
            fallidos = len(resultados) - exitosos
            await self._log(tarea, f"Proceso finalizado: {exitosos} exitosos, {fallidos} con error.")

            await sync_to_async(self._guardar_archivo)(tarea, f'catalogacion/{nombre_archivo}')
            await sync_to_async(self._actualizar_estado)(tarea, TareaCatalogacion.Estado.COMPLETADO)

        except Exception as e:
            logger.error(f"Error en ActualizarModalService: {e}", exc_info=True)
            await self._log(tarea, f"Error fatal: {e}")
            await sync_to_async(self._actualizar_estado)(tarea, TareaCatalogacion.Estado.ERROR)

    async def _log(self, tarea: TareaCatalogacion, mensaje: str) -> None:
        logger.info(mensaje)
        await sync_to_async(tarea.agregar_log)(mensaje)

    async def _incrementar_progreso(self, tarea: TareaCatalogacion) -> None:
        def _update():
            tarea.progreso_actual += 1
            tarea.save(update_fields=['progreso_actual'])
        await sync_to_async(_update)()

    @staticmethod
    def _actualizar_estado(tarea: TareaCatalogacion, estado: str) -> None:
        tarea.estado = estado
        tarea.save(update_fields=['estado'])

    @staticmethod
    def _guardar_archivo(tarea: TareaCatalogacion, ruta_relativa: str) -> None:
        tarea.archivo_resultado = ruta_relativa
        tarea.save(update_fields=['archivo_resultado'])
