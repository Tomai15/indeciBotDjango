from __future__ import annotations

import asyncio
import csv
import logging
import os
from datetime import datetime
from typing import Any, List

import pandas as pd
from asgiref.sync import sync_to_async
from django.conf import settings
from playwright.async_api import async_playwright

from core.models import TareaCatalogacion
from core.services.CarrefourAuthService import CarrefourAuthService

logger: logging.Logger = logging.getLogger(__name__)


class BusquedaCategoriaService:
    """Busca cantidad de productos por categoria y direccion en carrefour.com.ar."""

    CANTIDAD_WORKERS_DEFAULT = 5
    SELECTOR_TOTAL_PRODUCTOS = (
        "div.valtech-carrefourar-search-result-3-x-totalProducts--layout span"
    )

    def __init__(self) -> None:
        self._auth_service = CarrefourAuthService()

    # ------------------------------------------------------------------
    # Punto de entrada principal
    # ------------------------------------------------------------------
    async def ejecutar(
        self,
        tarea: TareaCatalogacion,
        direcciones: List[str],
        categorias: List[Any],
        tipo_regio: str = "retiro",
        cantidad_workers: int | None = None,
    ) -> None:
        """Ejecuta la busqueda concurrente de categorias para cada direccion."""
        await sync_to_async(self._actualizar_estado)(tarea, TareaCatalogacion.Estado.PROCESANDO)

        try:
            urls_categorias = self._normalizar_categorias(categorias)
            total_trabajos = max(1, len(direcciones) * len(urls_categorias))

            await sync_to_async(self._set_progreso_total)(tarea, total_trabajos)
            await self._log(
                tarea,
                f"Iniciando busqueda en categorias: {len(urls_categorias)} categorias "
                f"x {len(direcciones)} direcciones = {total_trabajos} tareas.",
            )

            auth_state_path = os.path.join(settings.MEDIA_ROOT, "auth_state_categorias.json")
            workers = max(1, min(cantidad_workers or self.CANTIDAD_WORKERS_DEFAULT, 5))

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                contexto_base = await browser.new_context()
                pagina_base = await contexto_base.new_page()

                await self._auth_service.login(pagina_base, tarea)

                resultados: list[dict[str, str]] = []

                for direccion in direcciones:
                    await pagina_base.reload()
                    await self._log(tarea, f"Regionalizando para direccion: {direccion}")
                    await self._auth_service.regionalizar(pagina_base, direccion, tipo_regio, tarea)
                    await contexto_base.storage_state(path=auth_state_path)

                    cola_trabajo: asyncio.Queue[str] = asyncio.Queue()
                    for categoria in urls_categorias:
                        cola_trabajo.put_nowait(categoria)

                    lock = asyncio.Lock()
                    tareas_worker = [
                        asyncio.create_task(
                            self._worker(
                                wid=i + 1,
                                browser=browser,
                                auth_state_path=auth_state_path,
                                cola=cola_trabajo,
                                lock=lock,
                                resultados=resultados,
                                direccion=direccion,
                                tarea=tarea,
                                total_trabajos=total_trabajos,
                            )
                        )
                        for i in range(workers)
                    ]

                    await cola_trabajo.join()

                    for t in tareas_worker:
                        t.cancel()
                    await asyncio.gather(*tareas_worker, return_exceptions=True)

                await contexto_base.close()
                await browser.close()

            # --- Generar archivos de salida ---
            await self._log(tarea, "Generando archivo de salida...")
            ruta_relativa = await self._generar_salida(resultados)

            await self._log(tarea, f"Proceso finalizado, archivo guardado en {ruta_relativa}")
            await sync_to_async(self._guardar_archivo)(tarea, ruta_relativa)
            await sync_to_async(self._actualizar_estado)(tarea, TareaCatalogacion.Estado.COMPLETADO)

        except Exception as e:
            logger.error(f"Error en BusquedaCategoriaService: {e}", exc_info=True)
            await self._log(tarea, f"Error fatal: {e}")
            await sync_to_async(self._actualizar_estado)(tarea, TareaCatalogacion.Estado.ERROR)

    # ------------------------------------------------------------------
    # Worker concurrente
    # ------------------------------------------------------------------
    async def _worker(
        self,
        wid: int,
        browser,
        auth_state_path: str,
        cola: asyncio.Queue[str],
        lock: asyncio.Lock,
        resultados: list[dict[str, str]],
        direccion: str,
        tarea: TareaCatalogacion,
        total_trabajos: int,
    ) -> None:
        contexto = await browser.new_context(storage_state=auth_state_path)
        pagina = await contexto.new_page()
        try:
            while True:
                try:
                    categoria = await asyncio.wait_for(cola.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    break

                try:
                    async with lock:
                        await self._log(tarea, f"[Worker {wid}] Navegando a categoria: {categoria}")

                    await pagina.goto(categoria)
                    await pagina.wait_for_timeout(3000)

                    cantidad = await pagina.locator(
                        self.SELECTOR_TOTAL_PRODUCTOS
                    ).first.inner_text()
                    solo_numero = cantidad.strip().split()[0]

                    async with lock:
                        resultados.append(
                            {
                                "categoria": self._extraer_categoria_url(categoria),
                                "tienda": direccion,
                                "cantidad": solo_numero,
                            }
                        )
                        await self._log(tarea, f"[Worker {wid}] Productos encontrados: {solo_numero}")

                except Exception as e:
                    async with lock:
                        resultados.append(
                            {
                                "categoria": self._extraer_categoria_url(categoria),
                                "tienda": direccion,
                                "cantidad": "Error buscando cantidad",
                            }
                        )
                        msg = f"[Worker {wid}] Error en '{categoria}' para '{direccion}': {e}"
                        await self._log(tarea, msg)

                finally:
                    await self._incrementar_progreso(tarea, total_trabajos)
                    cola.task_done()
        finally:
            await contexto.close()

    # ------------------------------------------------------------------
    # Generacion de archivos CSV + Excel
    # ------------------------------------------------------------------
    async def _generar_salida(self, resultados: list[dict[str, str]]) -> str:
        """Genera CSV y Excel con la matriz categorias x tiendas. Devuelve ruta relativa del Excel."""
        tiendas_ordenadas = sorted({r["tienda"] for r in resultados})
        categorias_ordenadas = sorted({r["categoria"] for r in resultados})
        matriz = {(r["categoria"], r["tienda"]): r["cantidad"] for r in resultados}

        carpeta = os.path.join(settings.MEDIA_ROOT, "catalogacion")
        os.makedirs(carpeta, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_csv = f"resultados_categorias_{timestamp}.csv"
        nombre_excel = f"resultados_categorias_{timestamp}.xlsx"
        ruta_csv = os.path.join(carpeta, nombre_csv)
        ruta_excel = os.path.join(carpeta, nombre_excel)

        with open(ruta_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["categoria"] + tiendas_ordenadas)
            for cat in categorias_ordenadas:
                fila = [cat] + [matriz.get((cat, tienda), "0") for tienda in tiendas_ordenadas]
                writer.writerow(fila)

        pd.read_csv(ruta_csv).to_excel(ruta_excel, index=False)

        return f"catalogacion/{nombre_excel}"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _extraer_categoria_url(url: str) -> str:
        """Devuelve el ultimo segmento de la URL (sin querystring) para usar como etiqueta."""
        url = url.split("?")[0]
        return url.strip("/").split("/")[-1]

    @staticmethod
    def _normalizar_categorias(categorias: List[Any]) -> List[str]:
        """Acepta lista de strings o de dicts con clave 'categoria'. Devuelve lista de URLs."""
        normalizadas: list[str] = []
        for item in categorias:
            if isinstance(item, dict) and "categoria" in item and item["categoria"]:
                normalizadas.append(item["categoria"].strip())
            elif isinstance(item, str) and item.strip():
                normalizadas.append(item.strip())
        return normalizadas

    # ------------------------------------------------------------------
    # Persistencia y logging
    # ------------------------------------------------------------------
    async def _log(self, tarea: TareaCatalogacion, mensaje: str) -> None:
        logger.info(mensaje)
        await sync_to_async(tarea.agregar_log)(mensaje)

    async def _incrementar_progreso(self, tarea: TareaCatalogacion, total_trabajos: int) -> None:
        def _update() -> None:
            tarea.progreso_actual = min(tarea.progreso_actual + 1, total_trabajos)
            tarea.save(update_fields=["progreso_actual"])
        await sync_to_async(_update)()

    @staticmethod
    def _actualizar_estado(tarea: TareaCatalogacion, estado: str) -> None:
        tarea.estado = estado
        tarea.save(update_fields=["estado"])

    @staticmethod
    def _set_progreso_total(tarea: TareaCatalogacion, total: int) -> None:
        tarea.progreso_total = total
        tarea.progreso_actual = 0
        tarea.save(update_fields=["progreso_total", "progreso_actual"])

    @staticmethod
    def _guardar_archivo(tarea: TareaCatalogacion, ruta_relativa: str) -> None:
        tarea.archivo_resultado = ruta_relativa
        tarea.save(update_fields=["archivo_resultado"])
