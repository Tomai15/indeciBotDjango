from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime

import pandas as pd
from asgiref.sync import sync_to_async
from django.conf import settings
from playwright.async_api import async_playwright

from core.models import TareaCatalogacion

logger: logging.Logger = logging.getLogger(__name__)


class SellersExternosService:
    """
    Servicio unificado para scraping de sellers externos.

    Contiene dos flujos principales:
    - ejecutar_carrefour: scraping de colecciones en carrefour.com.ar
    - ejecutar_no_carrefour: scraping de sellers en Fravega, Megatone, Oncity, Provincia
    """

    # =========================================================================
    # Utilidades de precio
    # =========================================================================

    @staticmethod
    def _normalizar_precio_texto(texto: str) -> str:
        """Limpia texto de precio eliminando espacios no estándar y duplicados."""
        if not texto:
            return texto
        texto = texto.replace('\u00A0', ' ').replace('\u202F', ' ')
        texto = re.sub(r'\s+', ' ', texto)
        return texto.strip()

    @staticmethod
    def _precio_texto_a_float(precio_texto: str) -> float | None:
        """
        Convierte un precio en formato texto (ej: "$ 184.999") a float.
        Maneja formatos con puntos como separadores de miles.
        """
        if not precio_texto:
            return None
        try:
            limpio = precio_texto.replace('$', '').replace(' ', '').strip()
            if ',' in limpio and '.' in limpio:
                if limpio.rfind(',') > limpio.rfind('.'):
                    limpio = limpio.replace('.', '').replace(',', '.')
                else:
                    limpio = limpio.replace(',', '')
            elif ',' in limpio:
                limpio = limpio.replace(',', '.')
            else:
                if limpio.count('.') > 1:
                    limpio = limpio.replace('.', '')
                elif '.' in limpio:
                    partes = limpio.split('.')
                    if len(partes[-1]) <= 2:
                        pass
                    else:
                        limpio = limpio.replace('.', '')
            return float(limpio)
        except Exception as e:
            logger.warning("Error convirtiendo precio '%s' a float: %s", precio_texto, e)
            return None

    @classmethod
    def _calcular_porcentaje_descuento(cls, precio_original: str, precio_final: str) -> str | None:
        """
        Calcula el porcentaje de descuento entre dos precios.
        Retorna el descuento en formato "XX%" o None si no se puede calcular.
        """
        try:
            original = cls._precio_texto_a_float(precio_original)
            final = cls._precio_texto_a_float(precio_final)
            if original and final and original > final:
                porcentaje = ((original - final) / original) * 100
                return f"{int(round(porcentaje))}%"
            return None
        except Exception as e:
            logger.warning("Error calculando descuento: %s", e)
            return None

    # =========================================================================
    # Helpers internos (log, progreso, archivo)
    # =========================================================================

    async def _log(self, tarea: TareaCatalogacion, mensaje: str) -> None:
        logger.info(mensaje)
        await sync_to_async(tarea.agregar_log)(mensaje)

    async def _incrementar_progreso(self, tarea: TareaCatalogacion, cantidad: int = 1) -> None:
        tarea.progreso_actual += cantidad
        await sync_to_async(tarea.save)(update_fields=['progreso_actual'])

    async def _set_progreso(self, tarea: TareaCatalogacion, actual: int, total: int | None = None) -> None:
        tarea.progreso_actual = actual
        campos = ['progreso_actual']
        if total is not None:
            tarea.progreso_total = total
            campos.append('progreso_total')
        await sync_to_async(tarea.save)(update_fields=campos)

    async def _set_estado(self, tarea: TareaCatalogacion, estado: str) -> None:
        tarea.estado = estado
        await sync_to_async(tarea.save)(update_fields=['estado'])

    async def _guardar_archivo(self, tarea: TareaCatalogacion, ruta_relativa: str) -> None:
        tarea.archivo_resultado.name = ruta_relativa
        await sync_to_async(tarea.save)(update_fields=['archivo_resultado'])

    # =========================================================================
    #  CARREFOUR  -  ejecutar_carrefour
    # =========================================================================

    async def ejecutar_carrefour(self, tarea: TareaCatalogacion, colecciones: list[str], headless: bool = True) -> None:
        """
        Scraping de productos de sellers externos dentro de carrefour.com.ar por coleccion.

        Args:
            tarea: instancia de TareaCatalogacion para trackeo.
            colecciones: lista de IDs de colecciones VTEX.
        """
        await self._set_estado(tarea, TareaCatalogacion.Estado.PROCESANDO)
        await self._set_progreso(tarea, 0, len(colecciones))

        try:
            async with async_playwright() as pw:
                await self._log(tarea, "Iniciando navegador")
                navegador = await pw.chromium.launch(headless=headless)
                contexto = await navegador.new_context()
                pagina = await contexto.new_page()
                lista_productos: list[dict] = []

                # --- Bloqueo de DynamicYield ---
                patrones_bloqueo = [
                    "**/*dynamicyield.com/**",
                    "**/*dy-api.com/**",
                    "**/*dycdn.com/**",
                    "**/*cdn.dynamicyield.com/**",
                    "**/*/dy-*.js*",
                    "**/*/dy/*.js*",
                    "**/*/dynamic*yield*/*",
                ]
                for patron in patrones_bloqueo:
                    await contexto.route(patron, lambda route: route.abort())

                await contexto.add_init_script("""
                (() => {
                  const hideCSS = `
                    .dy-modal-container,
                    .dy_full_width_notifications_container,
                    .dynotifyjs-wrapper,
                    .dy-auto-embedder,
                    [class*=" dy_"], [class^="dy_"],
                    [class*=" dy-"], [class^="dy-"],
                    [id^="dy-"], [id*=" dy-"] { display: none !important; visibility: hidden !important; }
                    html, body { pointer-events: auto !important; }
                  `;
                  const style = document.createElement('style');
                  style.setAttribute('data-anti-dy', '1');
                  style.textContent = hideCSS;
                  document.documentElement.appendChild(style);

                  const purge = () => {
                    const selectors = [
                      '.dy-modal-container',
                      '.dy_full_width_notifications_container',
                      '.dynotifyjs-wrapper',
                      '.dy-auto-embedder',
                      '[data-dy-exp-id]',
                      '[data-dy-var-id]',
                      '[class*=" dy_"]', '[class^="dy_"]',
                      '[class*=" dy-"]', '[class^="dy-"]',
                      '[id^="dy-"]', '[id*=" dy-"]'
                    ];
                    document.querySelectorAll(selectors.join(',')).forEach(n => {
                      try { n.remove(); } catch {}
                    });
                    const html = document.documentElement, body = document.body;
                    if (html) { html.style.removeProperty('overflow'); html.style.removeProperty('pointer-events'); }
                    if (body) { body.style.removeProperty('overflow'); body.style.removeProperty('pointer-events'); }
                  };

                  try { if (window.DY) window.DY = undefined; } catch {}
                  try { if (window.DynamicYield) window.DynamicYield = undefined; } catch {}

                  purge();

                  const mo = new MutationObserver(() => purge());
                  mo.observe(document.documentElement, { childList: true, subtree: true });

                  window.__purgeDY = purge;
                })();
                """)

                await self._log(tarea, "Ingresando a la web")
                await pagina.goto("https://www.carrefour.com.ar")
                try:
                    await pagina.locator("button:has-text('Rechazar todo')").click(timeout=5000)
                    await self._log(tarea, "Se denegaron las cookies")
                except Exception:
                    await self._log(tarea, "No se pudo seleccionar el boton para cerrar cookies")

                # --- Fase 1: recoleccion de productos por coleccion ---
                for coleccion in colecciones:
                    await self._log(tarea, f"Iniciando la busqueda de la coleccion: {coleccion}")
                    await pagina.goto(f"https://www.carrefour.com.ar/{coleccion}?map=productClusterIds")
                    await pagina.wait_for_timeout(5000)

                    # Detectar cantidad de paginas
                    cantidad_paginas = 1
                    try:
                        await pagina.evaluate("window.scrollTo(0, document.scrollingElement.scrollHeight)")
                        contenedor_paginado = pagina.locator(
                            ".valtech-carrefourar-search-result-3-x-paginationContainer"
                        )
                        if await contenedor_paginado.count() > 0:
                            botones_paginas = contenedor_paginado.locator(
                                ".valtech-carrefourar-search-result-3-x-paginationButtonPages button"
                            )
                            n = await botones_paginas.count()
                            if n > 0:
                                posibles = []
                                for j in range(n):
                                    btn = botones_paginas.nth(j)
                                    valor_attr = await btn.get_attribute("value")
                                    if valor_attr and valor_attr.isdigit():
                                        posibles.append(int(valor_attr))
                                    else:
                                        try:
                                            txt = (await btn.inner_text()).strip()
                                            if txt.isdigit():
                                                posibles.append(int(txt))
                                        except Exception:
                                            pass
                                if posibles:
                                    cantidad_paginas = max(posibles)
                    except Exception:
                        pass

                    for i in range(cantidad_paginas):
                        await pagina.goto(
                            f"https://www.carrefour.com.ar/{coleccion}?map=productClusterIds&page={i + 1}"
                        )
                        await pagina.evaluate("window.scrollTo(0, document.scrollingElement.scrollHeight)")
                        await pagina.wait_for_timeout(3000)
                        tarjetas = pagina.locator(
                            ".valtech-carrefourar-search-result-3-x-galleryItem"
                        )
                        await pagina.wait_for_timeout(3000)
                        cantidad = await tarjetas.count()

                        for j in range(cantidad):
                            tarjeta = tarjetas.nth(j)

                            # precio comun
                            try:
                                precio_comun = await tarjeta.locator(
                                    ".valtech-carrefourar-product-price-0-x-sellingPriceValue"
                                ).inner_text(timeout=1000)
                                precio_comun = self._normalizar_precio_texto(precio_comun.split("\n")[0])
                            except Exception:
                                precio_comun = None

                            # precio tachado
                            try:
                                precio_tachado = await tarjeta.locator(
                                    ".valtech-carrefourar-product-price-0-x-listPriceValue"
                                ).inner_text(timeout=1000)
                                precio_tachado = self._normalizar_precio_texto(precio_tachado)
                            except Exception:
                                precio_tachado = None

                            # link al producto
                            try:
                                url_relativa = await tarjeta.locator(
                                    "a.vtex-product-summary-2-x-clearLink"
                                ).get_attribute("href")
                                url_producto = (
                                    f"https://www.carrefour.com.ar{url_relativa}" if url_relativa else None
                                )
                            except Exception:
                                url_producto = None

                            # cucardas (spans de rowCucardas)
                            cucardas: list[str] = []
                            try:
                                contenedor_cucardas = tarjeta.locator(
                                    '.vtex-flex-layout-0-x-flexRow--rowCucardas'
                                )
                                valores_cucardas = contenedor_cucardas.locator(
                                    '[data-specification-group="Cucardas"]'
                                    '[data-specification-name="Cucardas"]'
                                    '.vtex-product-specifications-1-x-specificationValue'
                                )
                                textos = await valores_cucardas.all_inner_texts()
                                cucardas = [t.strip() for t in textos if t and t.strip()]
                            except Exception:
                                cucardas = []

                            # cucardas adicionales (imagenes con class cucarda-coleccion)
                            try:
                                cucardas_img = tarjeta.locator("img.cucarda-coleccion")
                                cant_img = await cucardas_img.count()
                                for k in range(cant_img):
                                    texto_alt = await cucardas_img.nth(k).get_attribute("alt")
                                    if texto_alt:
                                        cucardas.append(texto_alt.strip())
                            except Exception:
                                pass

                            # ribbons (fila rowRibbons)
                            try:
                                contenedor_ribbons = tarjeta.locator(
                                    '.vtex-flex-layout-0-x-flexRow--rowRibbons'
                                )
                                valores_ribbons = contenedor_ribbons.locator(
                                    '[data-specification-group="Ribbons"]'
                                    '.vtex-product-specifications-1-x-specificationValue'
                                )
                                textos_ribbons = await valores_ribbons.all_inner_texts()
                                for t in textos_ribbons:
                                    t = (t or "").strip()
                                    if t:
                                        cucardas.append(t)
                            except Exception:
                                pass

                            # ribbons tooltip (fila rowRibbonsTooltip)
                            try:
                                contenedor_ribbons_tooltip = tarjeta.locator(
                                    '.vtex-flex-layout-0-x-flexRow--rowRibbonsTooltip'
                                )
                                textos_tooltip = await contenedor_ribbons_tooltip.locator(
                                    '.tooltipText span'
                                ).all_inner_texts()
                                for t in textos_tooltip:
                                    t = (t or "").strip()
                                    if t:
                                        cucardas.append(t)
                            except Exception:
                                pass

                            # deduplicar manteniendo orden
                            if cucardas:
                                cucardas = list(dict.fromkeys(cucardas))
                            if not cucardas:
                                cucardas = ["No tiene"]

                            # vendido y entregado por
                            try:
                                contenedor_seller = tarjeta.locator(
                                    ".vtex-flex-layout-0-x-flexRow--rowSeller"
                                )
                                vendido_por = await contenedor_seller.inner_text()
                                vendido_por = vendido_por.split("Vendido y entregado por")[1].strip()
                            except Exception:
                                vendido_por = "No especificado"

                            # nombre del producto
                            try:
                                contenedor_nombre = tarjeta.locator(
                                    ".vtex-flex-layout-0-x-flexRow--rowName"
                                )
                                nombre_producto = await contenedor_nombre.locator(
                                    "h3.vtex-product-summary-2-x-productNameContainer"
                                ).inner_text()
                                nombre_producto = nombre_producto.strip()
                            except Exception:
                                nombre_producto = "Sin nombre"

                            # URL de la imagen
                            try:
                                contenedor_imagen = tarjeta.locator(
                                    ".vtex-flex-layout-0-x-flexRow--infoImage"
                                )
                                url_imagen = await contenedor_imagen.locator(
                                    "img.vtex-product-summary-2-x-imageNormal"
                                ).get_attribute("src")
                                if not url_imagen:
                                    url_imagen = await contenedor_imagen.locator(
                                        "img"
                                    ).first.get_attribute("src")
                            except Exception:
                                url_imagen = None

                            logger.debug(
                                "Producto %d: %s | Precio: %s | Seller: %s",
                                j + 1, nombre_producto, precio_comun, vendido_por,
                            )

                            lista_productos.append({
                                "nombreProducto": nombre_producto,
                                "precioComun": precio_comun,
                                "precioTachado": precio_tachado,
                                "urlProducto": url_producto,
                                "cucardas": cucardas,
                                "vendidoPor": vendido_por,
                                "urlImagen": url_imagen,
                                "arbolCategorias": None,
                                "ean": None,
                            })

                    await self._incrementar_progreso(tarea)

                # --- Fase 2: enriquecimiento individual (EAN + arbol de categorias) ---
                await self._log(
                    tarea,
                    "Finalizada la busqueda de colecciones, iniciando busqueda de EANs individualmente",
                )
                await self._set_progreso(tarea, 0, len(lista_productos))

                for idx, prod in enumerate(lista_productos, start=1):
                    await self._incrementar_progreso(tarea)
                    if not prod["urlProducto"]:
                        continue
                    try:
                        await pagina.goto(prod["urlProducto"])

                        # Arbol de categorias
                        try:
                            textos_breadcrumb = await pagina.locator(
                                '[data-testid="breadcrumb"] a, '
                                '[data-testid="breadcrumb"] .vtex-breadcrumb-1-x-term'
                            ).all_inner_texts()
                            textos_breadcrumb = [t.strip() for t in textos_breadcrumb if t and t.strip()]
                            if textos_breadcrumb:
                                textos_breadcrumb = textos_breadcrumb[:-1]
                            arbol_categorias = "|".join(textos_breadcrumb) if textos_breadcrumb else None
                        except Exception:
                            arbol_categorias = None

                        await pagina.get_by_role("button", name="Especificaciones técnicas").click()

                        # EAN
                        try:
                            fila_ean = pagina.locator(
                                'tr.vtex-store-components-3-x-specificationsTableRow'
                                ':has(td.vtex-store-components-3-x-specificationItemProperty:has-text("EAN"))'
                            ).first
                            ean_valor = await fila_ean.locator(
                                "td.vtex-store-components-3-x-specificationItemSpecifications div"
                            ).inner_text(timeout=1000)
                            ean_valor = ean_valor.strip() if ean_valor else None
                        except Exception:
                            ean_valor = None

                        prod["arbolCategorias"] = arbol_categorias
                        prod["ean"] = ean_valor

                        logger.debug(
                            "[ENRIQUECIDO] Producto %d: categorias=%s, ean=%s",
                            idx, arbol_categorias, ean_valor,
                        )

                    except Exception as e:
                        logger.warning("No se pudo enriquecer %s: %s", prod["urlProducto"], e)

                await navegador.close()

                # --- Generar Excel ---
                carpeta = os.path.join(settings.MEDIA_ROOT, "catalogacion")
                os.makedirs(carpeta, exist_ok=True)
                nombre_archivo = f'ProductosMarketPlace-{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
                ruta_final = os.path.join(carpeta, nombre_archivo)
                df = pd.DataFrame(lista_productos)
                df.to_excel(ruta_final, index=False)

                ruta_relativa = f"catalogacion/{nombre_archivo}"
                await self._guardar_archivo(tarea, ruta_relativa)
                await self._log(tarea, f"Proceso finalizado, archivo guardado en {ruta_final}")
                await self._set_estado(tarea, TareaCatalogacion.Estado.COMPLETADO)

        except Exception as exc:
            logger.exception("Error en ejecutar_carrefour")
            await self._log(tarea, f"ERROR: {exc}")
            await self._set_estado(tarea, TareaCatalogacion.Estado.ERROR)

    # =========================================================================
    #  NO CARREFOUR  -  ejecutar_no_carrefour
    # =========================================================================

    async def ejecutar_no_carrefour(
        self,
        tarea: TareaCatalogacion,
        diccionario_sellers: dict[str, list[str]],
        headless: bool = True,
    ) -> None:
        """
        Ejecuta scraping de sellers no-Carrefour (Fravega, Megatone, Oncity, Provincia).

        Args:
            tarea: instancia de TareaCatalogacion para trackeo.
            diccionario_sellers: dict con claves posibles "Fravega", "Megatone", "Oncity", "Provincia"
                                 y valores lista de sellers/colecciones.
        """
        await self._set_estado(tarea, TareaCatalogacion.Estado.PROCESANDO)
        total = sum(len(lista) for lista in diccionario_sellers.values())
        await self._set_progreso(tarea, 0, total)

        try:
            if "Megatone" in diccionario_sellers:
                await self._buscar_megatone(tarea, diccionario_sellers["Megatone"], headless)
                await self._set_progreso(tarea, 0)

            if "Fravega" in diccionario_sellers:
                await self._buscar_fravega(tarea, diccionario_sellers["Fravega"], headless)
                await self._set_progreso(tarea, 0)

            if "Oncity" in diccionario_sellers:
                await self._buscar_oncity(tarea, diccionario_sellers["Oncity"], headless)
                await self._set_progreso(tarea, 0)

            if "Provincia" in diccionario_sellers:
                await self._buscar_provincia(tarea, diccionario_sellers["Provincia"], headless)
                await self._set_progreso(tarea, 0)

            await self._set_estado(tarea, TareaCatalogacion.Estado.COMPLETADO)

        except Exception as exc:
            logger.exception("Error en ejecutar_no_carrefour")
            await self._log(tarea, f"ERROR: {exc}")
            await self._set_estado(tarea, TareaCatalogacion.Estado.ERROR)

    # -------------------------------------------------------------------------
    #  FRAVEGA
    # -------------------------------------------------------------------------

    async def _buscar_fravega(self, tarea: TareaCatalogacion, lista_colecciones: list[str], headless: bool = True) -> None:
        async with async_playwright() as pw:
            await self._log(tarea, "Iniciando navegador")
            navegador = await pw.chromium.launch(headless=headless)
            contexto = await navegador.new_context()
            pagina = await contexto.new_page()
            lista_productos: list[dict] = []

            await self._log(tarea, "Ingresando a la web")
            await pagina.goto("https://www.fravega.com/", timeout=10000000)

            for coleccion in lista_colecciones:
                await self._log(tarea, f"Iniciando la busqueda de la coleccion: {coleccion}")
                await pagina.goto(
                    f"https://www.fravega.com/l/?vendedor={coleccion}", timeout=100000
                )

                cantidad_paginas = 1
                try:
                    await pagina.evaluate("window.scrollTo(0, document.scrollingElement.scrollHeight)")
                    contenedor_paginado = pagina.locator(".sc-3624d7a8-0.ebdNvu")
                    if await contenedor_paginado.count() > 0:
                        botones_paginas = contenedor_paginado.locator(".sc-3624d7a8-1.kgGNyw")
                        n = await botones_paginas.count()
                        if n > 0:
                            posibles = []
                            for j in range(n):
                                btn = botones_paginas.nth(j)
                                valor_attr = await btn.get_attribute("value")
                                if valor_attr and valor_attr.isdigit():
                                    posibles.append(int(valor_attr))
                                else:
                                    try:
                                        txt = (await btn.inner_text()).strip()
                                        if txt.isdigit():
                                            posibles.append(int(txt))
                                    except Exception:
                                        pass
                            if posibles:
                                cantidad_paginas = max(posibles)
                except Exception:
                    pass

                logger.debug("Fravega: paginas encontradas = %d", cantidad_paginas)

                for i in range(cantidad_paginas):
                    await pagina.goto(
                        f"https://www.fravega.com/l/?vendedor={coleccion}&page={i + 1}",
                        timeout=100000,
                    )
                    await pagina.evaluate("window.scrollTo(0, document.scrollingElement.scrollHeight)")
                    await pagina.wait_for_timeout(3000)
                    tarjetas = pagina.locator("article.sc-87b0945d-1.bwMsmt")
                    await pagina.wait_for_timeout(3000)
                    cantidad = await tarjetas.count()

                    for j in range(cantidad):
                        tarjeta = tarjetas.nth(j)

                        # precio comun
                        try:
                            precio_comun = await tarjeta.locator(
                                "span.sc-1d9b1d9e-0.OZgQ"
                            ).inner_text(timeout=2000)
                            precio_comun = self._normalizar_precio_texto(precio_comun)
                        except Exception:
                            precio_comun = None

                        # precio tachado
                        try:
                            precio_tachado = await tarjeta.locator(
                                "span.sc-e081bce1-0.eudnWN"
                            ).inner_text(timeout=2000)
                            precio_tachado = self._normalizar_precio_texto(precio_tachado)
                        except Exception:
                            precio_tachado = None

                        # descuento
                        descuento = None
                        try:
                            descuento_texto = await tarjeta.locator(
                                "[data-test-id='discount-tag']"
                            ).inner_text(timeout=1000)
                            descuento = ''.join(filter(str.isdigit, descuento_texto))
                            if descuento:
                                descuento = f"{descuento}%"
                            else:
                                descuento = None
                        except Exception:
                            descuento = None

                        # link al producto
                        try:
                            url_relativa = await tarjeta.locator(
                                "a.sc-87b0945d-3.dQujLs"
                            ).first.get_attribute("href", timeout=1000)
                            url_producto = (
                                f"https://www.fravega.com{url_relativa}" if url_relativa else None
                            )
                        except Exception:
                            url_producto = None

                        cucardas = ["No tiene"]

                        # vendido por
                        try:
                            vendido_por_texto = await tarjeta.locator(
                                "p.sc-82405aa0-0.dIXwMc"
                            ).inner_text(timeout=1000)
                            if "Vendido por" in vendido_por_texto:
                                vendido_por = vendido_por_texto.split("Vendido por")[1].strip()
                            else:
                                vendido_por = vendido_por_texto.strip()
                        except Exception:
                            vendido_por = "No especificado"

                        # nombre del producto
                        try:
                            nombre_producto = await tarjeta.locator(
                                "span.sc-1fa74e6c-0.kUaLHc"
                            ).inner_text(timeout=1000)
                            nombre_producto = nombre_producto.strip()
                        except Exception:
                            nombre_producto = "Sin nombre"

                        # URL de la imagen
                        try:
                            url_imagen = await tarjeta.locator(
                                "img.sc-d0e786e3-0.jrZdpk"
                            ).get_attribute("src", timeout=1000)
                        except Exception:
                            url_imagen = None

                        logger.debug(
                            "Fravega Producto %d (Pag %d): %s | Precio: %s",
                            j + 1, i + 1, nombre_producto, precio_comun,
                        )

                        lista_productos.append({
                            "nombreProducto": nombre_producto,
                            "precioComun": precio_comun,
                            "precioTachado": precio_tachado,
                            "descuento": descuento,
                            "urlProducto": url_producto,
                            "cucardas": cucardas,
                            "vendidoPor": vendido_por,
                            "urlImagen": url_imagen,
                            "arbolCategorias": None,
                            "ean": None,
                        })

                await self._incrementar_progreso(tarea)

            # --- Enriquecimiento ---
            await self._log(
                tarea,
                "Finalizada la busqueda de colecciones, iniciando busqueda de EANs individualmente",
            )
            await self._set_progreso(tarea, 0, len(lista_productos))

            for idx, prod in enumerate(lista_productos, start=1):
                await self._incrementar_progreso(tarea)
                if not prod["urlProducto"]:
                    continue

                try:
                    await pagina.goto(prod["urlProducto"], timeout=30000)
                    await pagina.wait_for_load_state("domcontentloaded", timeout=15000)

                    # Arbol de categorias
                    arbol_categorias = None
                    try:
                        elementos_breadcrumb = pagina.locator(
                            "div.sc-8071ec51-0 "
                            "ol[itemtype='https://schema.org/BreadcrumbList'] "
                            "li[itemprop='itemListElement']"
                        )
                        count = await elementos_breadcrumb.count()
                        if count > 1:
                            textos_breadcrumb = []
                            for k in range(1, count):
                                texto = await elementos_breadcrumb.nth(k).locator(
                                    "span[itemprop='name']"
                                ).inner_text(timeout=2000)
                                textos_breadcrumb.append(texto.strip())
                            if textos_breadcrumb:
                                arbol_categorias = "|".join(textos_breadcrumb)
                            else:
                                # Fallback selector movil
                                elementos_breadcrumb = pagina.locator(
                                    "div.sc-bd34a3c8-0 "
                                    "ol[itemtype='https://schema.org/BreadcrumbList'] "
                                    "li[itemprop='itemListElement']"
                                )
                                count = await elementos_breadcrumb.count()
                                textos_breadcrumb = []
                                for k in range(count):
                                    texto = await elementos_breadcrumb.nth(k).locator(
                                        "span[itemprop='name']"
                                    ).inner_text(timeout=2000)
                                    textos_breadcrumb.append(texto.strip())
                                if textos_breadcrumb:
                                    arbol_categorias = "|".join(textos_breadcrumb)
                    except Exception:
                        arbol_categorias = None

                    ean_valor = None

                    prod["arbolCategorias"] = arbol_categorias
                    prod["ean"] = ean_valor

                except Exception as e:
                    logger.warning("No se pudo enriquecer %s: %s", prod.get("urlProducto"), e)
                    prod["arbolCategorias"] = prod.get("arbolCategorias")
                    prod["ean"] = prod.get("ean")

            await navegador.close()

            # --- Generar Excel ---
            carpeta = os.path.join(settings.MEDIA_ROOT, "catalogacion")
            os.makedirs(carpeta, exist_ok=True)
            nombre_archivo = f'ProductosMarketPlace-{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            ruta_final = os.path.join(carpeta, nombre_archivo)
            df = pd.DataFrame(lista_productos)
            df.to_excel(ruta_final, index=False)

            ruta_relativa = f"catalogacion/{nombre_archivo}"
            await self._guardar_archivo(tarea, ruta_relativa)
            await self._log(tarea, f"Proceso finalizado, archivo guardado en {ruta_final}")

    # -------------------------------------------------------------------------
    #  MEGATONE
    # -------------------------------------------------------------------------

    async def _buscar_megatone(self, tarea: TareaCatalogacion, lista_sellers: list[str], headless: bool = True) -> None:
        async with async_playwright() as pw:
            await self._log(tarea, "Iniciando navegador para Megatone")
            navegador = await pw.chromium.launch(headless=headless)
            contexto = await navegador.new_context()
            pagina = await contexto.new_page()
            lista_productos: list[dict] = []

            await self._log(tarea, "Ingresando a Megatone")
            await pagina.goto("https://www.megatone.net/", timeout=10000000)
            await self._set_progreso(tarea, 0, len(lista_sellers))

            for seller in lista_sellers:
                await self._log(tarea, f"Iniciando la busqueda del seller: {seller}")
                await pagina.goto(f"https://www.megatone.net/tiendas/{seller}/", timeout=100000)
                await pagina.wait_for_timeout(3000)

                # Detectar cantidad de paginas
                cantidad_paginas = 1
                try:
                    botones_paginado = await pagina.query_selector_all(".BtnPaginado")
                    if botones_paginado:
                        paginas_numeros = []
                        for btn in botones_paginado:
                            texto = await btn.inner_text()
                            texto = texto.strip()
                            if texto.isdigit():
                                paginas_numeros.append(int(texto))
                        if paginas_numeros:
                            cantidad_paginas = max(paginas_numeros)
                            await self._log(
                                tarea,
                                f"Se detectaron {cantidad_paginas} paginas para {seller}",
                            )
                except Exception as e:
                    logger.debug("No se pudo detectar paginacion: %s", e)
                    cantidad_paginas = 1

                # Iterar por cada pagina
                for num_pagina in range(1, cantidad_paginas + 1):
                    await self._log(
                        tarea,
                        f"Procesando pagina {num_pagina} de {cantidad_paginas} para {seller}",
                    )

                    if num_pagina > 1:
                        try:
                            await pagina.evaluate(f"ObtenerFiltro({num_pagina}, 'Pagina', 'Pagina')")
                            await pagina.wait_for_timeout(3000)
                        except Exception as e:
                            logger.debug("Error al navegar a pagina %d: %s", num_pagina, e)
                            continue

                    try:
                        await self._log(
                            tarea,
                            f"Extrayendo productos de {seller} pagina {num_pagina} desde JSON",
                        )

                        productos_json = await pagina.evaluate("""
                            () => {
                                if (typeof GlobalListado !== 'undefined' && GlobalListado.Productos) {
                                    return GlobalListado.Productos;
                                }
                                return [];
                            }
                        """)

                        await self._log(
                            tarea,
                            f"Se encontraron {len(productos_json)} productos para {seller}",
                        )

                        for idx, prod_json in enumerate(productos_json):
                            if not isinstance(prod_json, dict):
                                continue

                            nombre_producto = prod_json.get("Nombre", "Sin nombre")

                            precio_comun = None
                            precio_tachado = None
                            descuento = None

                            if "Precios" in prod_json and "WEB" in prod_json["Precios"]:
                                precios_web = prod_json["Precios"]["WEB"]
                                precio_comun = f"${precios_web.get('Promocional', 0):,.2f}".replace(",", ".")
                                precio_lista = precios_web.get('Lista', 0)
                                if precio_lista and precio_lista > precios_web.get('Promocional', 0):
                                    precio_tachado = f"${precio_lista:,.2f}".replace(",", ".")
                                porcentaje_off = precios_web.get('PorcentajeOFF', 0)
                                if porcentaje_off > 0:
                                    descuento = f"{int(porcentaje_off)}%"

                            url_relativa = prod_json.get("URL", "")
                            url_producto = (
                                f"https://www.megatone.net{url_relativa}" if url_relativa else None
                            )

                            url_imagen = prod_json.get("Imagen", None)

                            vendido_por = seller
                            if "Marca" in prod_json and isinstance(prod_json["Marca"], dict):
                                vendido_por = prod_json["Marca"].get("Descripcion", seller)

                            cucardas = ["No tiene"]
                            if "Plaquetas" in prod_json and prod_json["Plaquetas"]:
                                try:
                                    plaquetas_obj = prod_json["Plaquetas"]
                                    cucardas_lista = []
                                    if isinstance(plaquetas_obj, dict):
                                        for key, val in plaquetas_obj.items():
                                            if isinstance(val, dict):
                                                nombre = (
                                                    val.get("Nombre")
                                                    or val.get("Descripcion")
                                                    or val.get("Texto")
                                                    or str(key)
                                                )
                                                if nombre:
                                                    cucardas_lista.append(nombre)
                                            elif isinstance(val, str) and val:
                                                cucardas_lista.append(val)
                                    elif isinstance(plaquetas_obj, list):
                                        for p_item in plaquetas_obj:
                                            if isinstance(p_item, dict):
                                                nombre = (
                                                    p_item.get("Nombre")
                                                    or p_item.get("Descripcion")
                                                    or p_item.get("Texto")
                                                )
                                                if nombre:
                                                    cucardas_lista.append(nombre)
                                            elif isinstance(p_item, str) and p_item:
                                                cucardas_lista.append(p_item)
                                    if cucardas_lista:
                                        cucardas = cucardas_lista
                                except Exception:
                                    cucardas = ["No tiene"]

                            logger.debug(
                                "Megatone Producto %d: %s | Precio: %s",
                                idx + 1, nombre_producto, precio_comun,
                            )

                            lista_productos.append({
                                "nombreProducto": nombre_producto,
                                "precioComun": precio_comun,
                                "precioTachado": precio_tachado,
                                "descuento": descuento,
                                "urlProducto": url_producto,
                                "cucardas": cucardas,
                                "vendidoPor": vendido_por,
                                "urlImagen": url_imagen,
                                "arbolCategorias": None,
                                "ean": None,
                            })

                    except Exception as e:
                        await self._log(
                            tarea,
                            f"Error al extraer productos de {seller} pagina {num_pagina}: {e}",
                        )

                await self._incrementar_progreso(tarea)

            # --- Enriquecimiento ---
            await self._log(
                tarea,
                "Finalizada la busqueda de sellers, iniciando enriquecimiento de productos",
            )
            await self._set_progreso(tarea, 0, len(lista_productos))

            for idx, prod in enumerate(lista_productos, start=1):
                await self._incrementar_progreso(tarea)
                if not prod["urlProducto"]:
                    continue

                try:
                    await pagina.goto(prod["urlProducto"], timeout=30000)
                    await pagina.wait_for_load_state("domcontentloaded", timeout=15000)

                    # EAN/SKU desde variable JavaScript
                    ean_valor = None
                    try:
                        ean_valor = await pagina.evaluate("() => window.sku")
                    except Exception:
                        pass

                    # Arbol de categorias
                    arbol_categorias = None
                    try:
                        enlaces_categorias = await pagina.query_selector_all("a[href*='/listado/']")
                        categorias = []
                        for enlace in enlaces_categorias:
                            texto = await enlace.inner_text()
                            href = await enlace.get_attribute("href")
                            if (
                                href
                                and texto
                                and len(texto.strip()) > 0
                                and "volver" not in texto.lower()
                            ):
                                categorias.append(texto.strip())

                        categorias_unicas = []
                        for cat in categorias:
                            if cat not in categorias_unicas:
                                categorias_unicas.append(cat)
                        if categorias_unicas:
                            arbol_categorias = "|".join(categorias_unicas)
                    except Exception:
                        pass

                    prod["arbolCategorias"] = arbol_categorias
                    prod["ean"] = ean_valor

                except Exception as e:
                    logger.warning("No se pudo enriquecer %s: %s", prod.get("urlProducto"), e)
                    prod["arbolCategorias"] = prod.get("arbolCategorias")
                    prod["ean"] = prod.get("ean")

            await navegador.close()

            # --- Generar Excel ---
            carpeta = os.path.join(settings.MEDIA_ROOT, "catalogacion")
            os.makedirs(carpeta, exist_ok=True)
            nombre_archivo = f'ProductosMarketPlace-Megatone-{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            ruta_final = os.path.join(carpeta, nombre_archivo)
            df = pd.DataFrame(lista_productos)
            df.to_excel(ruta_final, index=False)

            ruta_relativa = f"catalogacion/{nombre_archivo}"
            await self._guardar_archivo(tarea, ruta_relativa)
            await self._log(tarea, f"Proceso finalizado, archivo guardado en {ruta_final}")

    # -------------------------------------------------------------------------
    #  ONCITY
    # -------------------------------------------------------------------------

    async def _buscar_oncity(self, tarea: TareaCatalogacion, lista_sellers: list[str], headless: bool = True) -> None:
        async with async_playwright() as pw:
            await self._log(tarea, "Iniciando navegador para Oncity")
            navegador = await pw.chromium.launch(headless=headless)
            contexto = await navegador.new_context()
            pagina = await contexto.new_page()
            lista_productos: list[dict] = []

            await self._log(tarea, "Ingresando a Oncity")
            await pagina.goto("https://www.oncity.com/", timeout=10000000)
            await self._set_progreso(tarea, 0, len(lista_sellers))

            for seller in lista_sellers:
                await self._log(tarea, f"Iniciando la busqueda del seller: {seller}")
                await pagina.goto(
                    f"https://www.oncity.com/{seller}?map=seller", timeout=100000
                )
                await pagina.wait_for_timeout(3000)

                num_pagina = 1
                hay_mas_paginas = True

                while hay_mas_paginas:
                    await self._log(tarea, f"Procesando pagina {num_pagina} para {seller}")

                    await pagina.evaluate("window.scrollTo(0, document.scrollingElement.scrollHeight)")
                    await pagina.wait_for_timeout(3000)

                    try:
                        await self._log(
                            tarea,
                            f"Extrayendo productos de {seller} pagina {num_pagina} desde JSON-LD",
                        )

                        productos_json = await pagina.evaluate("""
                            () => {
                                const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                                for (const script of scripts) {
                                    try {
                                        const data = JSON.parse(script.textContent);
                                        if (data['@type'] === 'ItemList' && data.itemListElement) {
                                            return data.itemListElement;
                                        }
                                    } catch (e) {
                                        console.error('Error parsing JSON-LD:', e);
                                    }
                                }
                                return [];
                            }
                        """)

                        await self._log(
                            tarea,
                            f"Se encontraron {len(productos_json)} productos en JSON-LD para {seller}",
                        )

                        tarjetas_productos = pagina.locator(
                            ".vtex-product-summary-2-x-containerNormal--product-summary-product"
                        )
                        cantidad_tarjetas = await tarjetas_productos.count()

                        for idx, prod_json in enumerate(productos_json):
                            if not isinstance(prod_json, dict):
                                continue

                            item = prod_json.get("item", {})
                            nombre_producto = item.get("name", "Sin nombre")
                            sku = item.get("sku", None)

                            precio_comun = None
                            vendido_por = seller

                            if "offers" in item:
                                offers = item["offers"]
                                if isinstance(offers, dict):
                                    precio_comun = offers.get("lowPrice") or offers.get("price")
                                    if precio_comun:
                                        precio_comun = f"$ {precio_comun:,.0f}".replace(",", ".")
                                    if (
                                        "offers" in offers
                                        and isinstance(offers["offers"], list)
                                        and len(offers["offers"]) > 0
                                    ):
                                        first_offer = offers["offers"][0]
                                        if "seller" in first_offer and isinstance(
                                            first_offer["seller"], dict
                                        ):
                                            vendido_por = first_offer["seller"].get("name", seller)

                            url_producto = item.get("@id", None)
                            url_imagen = item.get("image", None)
                            if isinstance(url_imagen, list) and len(url_imagen) > 0:
                                url_imagen = url_imagen[0]

                            precio_tachado = None
                            descuento = None
                            cucardas = ["No tiene"]

                            try:
                                if idx < cantidad_tarjetas:
                                    tarjeta_producto = tarjetas_productos.nth(idx)

                                    # Precio tachado
                                    try:
                                        precio_tachado_texto = await tarjeta_producto.locator(
                                            ".vtex-product-price-1-x-listPrice--summary"
                                        ).inner_text(timeout=2000)
                                        if precio_tachado_texto and "$" in precio_tachado_texto:
                                            precio_tachado = self._normalizar_precio_texto(
                                                precio_tachado_texto
                                            )
                                    except Exception:
                                        pass

                                    # Descuento
                                    selectores_descuento = [
                                        ".vtex-stack-layout-0-x-stackItem--highlights--topRight",
                                        ".vtex-product-summary-2-x-discount",
                                        ".vtex-search-result-3-x-discount",
                                        "[class*='discount']",
                                        "[class*='Discount']",
                                    ]
                                    descuento_encontrado = False
                                    for sel in selectores_descuento:
                                        try:
                                            descuento_texto = await tarjeta_producto.locator(
                                                sel
                                            ).inner_text(timeout=1000)
                                            if descuento_texto and (
                                                '%' in descuento_texto
                                                or 'off' in descuento_texto.lower()
                                            ):
                                                descuento = ''.join(
                                                    filter(
                                                        lambda c: c.isdigit() or c == '%',
                                                        descuento_texto,
                                                    )
                                                )
                                                if descuento and descuento != '%':
                                                    descuento_encontrado = True
                                                    break
                                        except Exception:
                                            continue

                                    if not descuento_encontrado and precio_tachado and precio_comun:
                                        descuento_calculado = self._calcular_porcentaje_descuento(
                                            precio_tachado, precio_comun
                                        )
                                        if descuento_calculado:
                                            descuento = descuento_calculado

                                    # Cucardas
                                    try:
                                        cucarda_elements = tarjeta_producto.locator(
                                            ".vtex-stack-layout-0-x-stackItem--highlights--cucardas"
                                        )
                                        count_cucardas = await cucarda_elements.count()
                                        if count_cucardas > 0:
                                            cucardas_lista = []
                                            for k in range(count_cucardas):
                                                texto_c = await cucarda_elements.nth(k).inner_text(
                                                    timeout=1000
                                                )
                                                if texto_c and texto_c.strip():
                                                    cucardas_lista.append(texto_c.strip())
                                            if cucardas_lista:
                                                cucardas = cucardas_lista
                                    except Exception:
                                        pass

                            except Exception:
                                pass

                            logger.debug(
                                "Oncity Producto %d: %s | Precio: %s",
                                idx + 1, nombre_producto, precio_comun,
                            )

                            lista_productos.append({
                                "nombreProducto": nombre_producto,
                                "precioComun": precio_comun,
                                "precioTachado": precio_tachado,
                                "descuento": descuento,
                                "urlProducto": url_producto,
                                "cucardas": cucardas,
                                "vendidoPor": vendido_por,
                                "urlImagen": url_imagen,
                                "arbolCategorias": None,
                                "ean": sku,
                            })

                    except Exception as e:
                        await self._log(
                            tarea,
                            f"Error al extraer productos de {seller} pagina {num_pagina}: {e}",
                        )

                    # Verificar boton "Ver mas productos"
                    try:
                        await pagina.evaluate(
                            "window.scrollTo(0, document.scrollingElement.scrollHeight)"
                        )
                        await pagina.wait_for_timeout(2000)

                        boton_ver_mas = await pagina.query_selector(
                            "a:has-text('Ver más productos')"
                        )

                        if boton_ver_mas:
                            href = await boton_ver_mas.get_attribute("href")
                            if href:
                                if href.startswith("http"):
                                    siguiente_url = href
                                elif href.startswith("?"):
                                    siguiente_url = f"https://www.oncity.com/{seller}{href}"
                                else:
                                    siguiente_url = f"https://www.oncity.com/{href}"
                                await pagina.goto(siguiente_url, timeout=100000)
                                await pagina.wait_for_timeout(3000)
                                num_pagina += 1
                            else:
                                hay_mas_paginas = False
                        else:
                            hay_mas_paginas = False
                    except Exception:
                        hay_mas_paginas = False

                await self._incrementar_progreso(tarea)

            # --- Enriquecimiento ---
            await self._log(
                tarea,
                "Finalizada la busqueda de sellers, iniciando enriquecimiento de productos",
            )
            await self._set_progreso(tarea, 0, len(lista_productos))

            for idx, prod in enumerate(lista_productos, start=1):
                await self._incrementar_progreso(tarea)
                if not prod["urlProducto"]:
                    continue

                try:
                    await pagina.goto(prod["urlProducto"], timeout=30000)
                    await pagina.wait_for_load_state("domcontentloaded", timeout=15000)

                    # Arbol de categorias (breadcrumb VTEX)
                    arbol_categorias = None
                    try:
                        elementos_breadcrumb = pagina.locator(
                            ".vtex-breadcrumb-1-x-link--store-breadcrumb"
                        )
                        count = await elementos_breadcrumb.count()
                        if count > 0:
                            textos_breadcrumb = []
                            for k in range(count):
                                texto = await elementos_breadcrumb.nth(k).inner_text(timeout=2000)
                                texto = texto.strip()
                                if texto and texto.lower() not in ["home", "inicio"]:
                                    textos_breadcrumb.append(texto)
                            if textos_breadcrumb:
                                arbol_categorias = "|".join(textos_breadcrumb)
                    except Exception:
                        arbol_categorias = None

                    # EAN desde JSON-LD
                    ean_valor = prod.get("ean", None)
                    try:
                        ean_extraido = await pagina.evaluate("""
                            () => {
                                const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                                for (const script of scripts) {
                                    try {
                                        const data = JSON.parse(script.textContent);
                                        if (data['@type'] === 'Product') {
                                            if (data.gtin13) return data.gtin13;
                                            if (data.gtin) return data.gtin;
                                            if (data.ean) return data.ean;
                                            if (data.mpn) return data.mpn;
                                            if (data.sku) return data.sku;
                                        }
                                    } catch (e) {
                                        console.error('Error parsing JSON-LD:', e);
                                    }
                                }
                                return null;
                            }
                        """)
                        if ean_extraido:
                            ean_valor = ean_extraido
                    except Exception:
                        pass

                    prod["arbolCategorias"] = arbol_categorias
                    prod["ean"] = ean_valor

                except Exception as e:
                    logger.warning("No se pudo enriquecer %s: %s", prod.get("urlProducto"), e)
                    prod["arbolCategorias"] = prod.get("arbolCategorias")
                    prod["ean"] = prod.get("ean")

            await navegador.close()

            # --- Generar Excel ---
            carpeta = os.path.join(settings.MEDIA_ROOT, "catalogacion")
            os.makedirs(carpeta, exist_ok=True)
            nombre_archivo = (
                f'ProductosMarketPlace-Oncity-{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            )
            ruta_final = os.path.join(carpeta, nombre_archivo)
            df = pd.DataFrame(lista_productos)
            df.to_excel(ruta_final, index=False)

            ruta_relativa = f"catalogacion/{nombre_archivo}"
            await self._guardar_archivo(tarea, ruta_relativa)
            await self._log(tarea, f"Proceso finalizado, archivo guardado en {ruta_final}")

    # -------------------------------------------------------------------------
    #  PROVINCIA
    # -------------------------------------------------------------------------

    async def _buscar_provincia(self, tarea: TareaCatalogacion, lista_sellers: list[str], headless: bool = True) -> None:
        async with async_playwright() as pw:
            await self._log(tarea, "Iniciando navegador para Provincia")
            navegador = await pw.chromium.launch(headless=headless)
            contexto = await navegador.new_context()
            pagina = await contexto.new_page()
            lista_productos: list[dict] = []

            await self._log(tarea, "Ingresando a Provincia")
            await pagina.goto("https://www.provinciacompras.com.ar/", timeout=10000000)
            await self._set_progreso(tarea, 0, len(lista_sellers))

            for seller in lista_sellers:
                await self._log(tarea, f"Iniciando la busqueda del seller: {seller}")
                await pagina.goto(
                    f"https://www.provinciacompras.com.ar/{seller}?map=seller", timeout=100000
                )
                await pagina.wait_for_timeout(3000)

                num_pagina = 1
                hay_mas_paginas = True

                while hay_mas_paginas:
                    await self._log(tarea, f"Procesando pagina {num_pagina} para {seller}")

                    await pagina.evaluate("window.scrollTo(0, document.scrollingElement.scrollHeight)")
                    await pagina.wait_for_timeout(3000)

                    try:
                        await self._log(
                            tarea,
                            f"Extrayendo productos de {seller} pagina {num_pagina} desde JSON-LD",
                        )

                        productos_json = await pagina.evaluate("""
                            () => {
                                const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                                for (const script of scripts) {
                                    try {
                                        const data = JSON.parse(script.textContent);
                                        if (data['@type'] === 'ItemList' && data.itemListElement) {
                                            return data.itemListElement;
                                        }
                                    } catch (e) {
                                        console.error('Error parsing JSON-LD:', e);
                                    }
                                }
                                return [];
                            }
                        """)

                        await self._log(
                            tarea,
                            f"Se encontraron {len(productos_json)} productos en JSON-LD para {seller}",
                        )

                        tarjetas_productos = pagina.locator("article")
                        cantidad_tarjetas = await tarjetas_productos.count()

                        for idx, prod_json in enumerate(productos_json):
                            if not isinstance(prod_json, dict):
                                continue

                            item = prod_json.get("item", {})
                            nombre_producto = item.get("name", "Sin nombre")
                            sku = item.get("sku", None)

                            precio_comun = None
                            vendido_por = seller

                            if "offers" in item:
                                offers = item["offers"]
                                if isinstance(offers, dict):
                                    precio_comun = offers.get("lowPrice") or offers.get("price")
                                    if precio_comun:
                                        precio_comun = f"$ {precio_comun:,.0f}".replace(",", ".")
                                    if (
                                        "offers" in offers
                                        and isinstance(offers["offers"], list)
                                        and len(offers["offers"]) > 0
                                    ):
                                        first_offer = offers["offers"][0]
                                        if "seller" in first_offer and isinstance(
                                            first_offer["seller"], dict
                                        ):
                                            vendido_por = first_offer["seller"].get("name", seller)

                            url_producto = item.get("@id", None)
                            url_imagen = item.get("image", None)
                            if isinstance(url_imagen, list) and len(url_imagen) > 0:
                                url_imagen = url_imagen[0]

                            precio_tachado = None
                            descuento = None
                            cucardas = ["No tiene"]

                            try:
                                if idx < cantidad_tarjetas:
                                    tarjeta_producto = tarjetas_productos.nth(idx)

                                    # Precio tachado
                                    try:
                                        precio_tachado_texto = await tarjeta_producto.locator(
                                            ".vtex-product-price-1-x-listPrice"
                                        ).inner_text(timeout=2000)
                                        if precio_tachado_texto and "$" in precio_tachado_texto:
                                            precio_tachado = self._normalizar_precio_texto(
                                                precio_tachado_texto
                                            )
                                    except Exception:
                                        pass

                                    # Descuento
                                    try:
                                        descuento_texto = await tarjeta_producto.locator(
                                            "[class*='tag']"
                                        ).inner_text(timeout=2000)
                                        if descuento_texto and '%' in descuento_texto:
                                            descuento = ''.join(
                                                filter(
                                                    lambda c: c.isdigit() or c == '%',
                                                    descuento_texto,
                                                )
                                            )
                                            if not descuento or descuento == '%':
                                                descuento = None
                                    except Exception:
                                        selectores_descuento_alt = [
                                            ".vtex-stack-layout-0-x-stackItem--highlights",
                                            "[class*='discount']",
                                            "[class*='badge']",
                                        ]
                                        for sel in selectores_descuento_alt:
                                            try:
                                                descuento_texto = await tarjeta_producto.locator(
                                                    sel
                                                ).inner_text(timeout=1000)
                                                if descuento_texto and (
                                                    '%' in descuento_texto
                                                    or 'off' in descuento_texto.lower()
                                                ):
                                                    descuento = ''.join(
                                                        filter(
                                                            lambda c: c.isdigit() or c == '%',
                                                            descuento_texto,
                                                        )
                                                    )
                                                    if descuento and descuento != '%':
                                                        break
                                            except Exception:
                                                continue

                                    # Calcular descuento si no se encontro
                                    if not descuento and precio_tachado and precio_comun:
                                        descuento_calculado = self._calcular_porcentaje_descuento(
                                            precio_tachado, precio_comun
                                        )
                                        if descuento_calculado:
                                            descuento = descuento_calculado

                                    # Cucardas
                                    try:
                                        cucarda_elements = tarjeta_producto.locator(
                                            "[class*='cucarda'], [class*='badge'], [class*='highlight']"
                                        )
                                        count_cucardas = await cucarda_elements.count()
                                        if count_cucardas > 0:
                                            cucardas_lista = []
                                            for k in range(count_cucardas):
                                                texto_c = await cucarda_elements.nth(k).inner_text(
                                                    timeout=1000
                                                )
                                                if texto_c and texto_c.strip():
                                                    cucardas_lista.append(texto_c.strip())
                                            if cucardas_lista:
                                                cucardas = cucardas_lista
                                    except Exception:
                                        pass

                            except Exception:
                                pass

                            logger.debug(
                                "Provincia Producto %d: %s | Precio: %s",
                                idx + 1, nombre_producto, precio_comun,
                            )

                            lista_productos.append({
                                "nombreProducto": nombre_producto,
                                "precioComun": precio_comun,
                                "precioTachado": precio_tachado,
                                "descuento": descuento,
                                "urlProducto": url_producto,
                                "cucardas": cucardas,
                                "vendidoPor": vendido_por,
                                "urlImagen": url_imagen,
                                "arbolCategorias": None,
                                "ean": sku,
                            })

                    except Exception as e:
                        await self._log(
                            tarea,
                            f"Error al extraer productos de {seller} pagina {num_pagina}: {e}",
                        )

                    # Verificar boton "Mostrar mas"
                    try:
                        await pagina.evaluate(
                            "window.scrollTo(0, document.scrollingElement.scrollHeight)"
                        )
                        await pagina.wait_for_timeout(2000)

                        boton_mostrar_mas = await pagina.query_selector(
                            "button:has-text('Mostrar más'), a:has-text('Mostrar más')"
                        )

                        if boton_mostrar_mas:
                            await boton_mostrar_mas.click()
                            await pagina.wait_for_timeout(3000)
                            num_pagina += 1
                        else:
                            hay_mas_paginas = False
                    except Exception:
                        hay_mas_paginas = False

                await self._incrementar_progreso(tarea)

            # --- Enriquecimiento ---
            await self._log(
                tarea,
                "Finalizada la busqueda de sellers, iniciando enriquecimiento de productos",
            )
            await self._set_progreso(tarea, 0, len(lista_productos))

            for idx, prod in enumerate(lista_productos, start=1):
                await self._incrementar_progreso(tarea)
                if not prod["urlProducto"]:
                    continue

                try:
                    await pagina.goto(prod["urlProducto"], timeout=30000)
                    await pagina.wait_for_load_state("domcontentloaded", timeout=15000)

                    # Arbol de categorias (breadcrumb Provincia)
                    arbol_categorias = None
                    try:
                        elementos_breadcrumb = pagina.locator(
                            ".vtex-breadcrumb-1-x-container--product-breadcrumb "
                            ".vtex-breadcrumb-1-x-link"
                        )
                        count = await elementos_breadcrumb.count()
                        if count > 0:
                            textos_breadcrumb = []
                            for k in range(count):
                                texto = await elementos_breadcrumb.nth(k).inner_text(timeout=2000)
                                texto = texto.strip()
                                if texto and texto.lower() not in [
                                    "home",
                                    "inicio",
                                    "provincia compras",
                                ]:
                                    textos_breadcrumb.append(texto)
                            if textos_breadcrumb:
                                arbol_categorias = "|".join(textos_breadcrumb)
                    except Exception:
                        arbol_categorias = None

                    # EAN desde JSON-LD
                    ean_valor = prod.get("ean", None)
                    try:
                        ean_extraido = await pagina.evaluate("""
                            () => {
                                const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                                for (const script of scripts) {
                                    try {
                                        const data = JSON.parse(script.textContent);
                                        if (data['@type'] === 'Product') {
                                            if (data.gtin13) return data.gtin13;
                                            if (data.gtin) return data.gtin;
                                            if (data.ean) return data.ean;
                                            if (data.mpn) return data.mpn;
                                            if (data.sku) return data.sku;
                                        }
                                    } catch (e) {
                                        console.error('Error parsing JSON-LD:', e);
                                    }
                                }
                                return null;
                            }
                        """)
                        if ean_extraido:
                            ean_valor = ean_extraido
                    except Exception:
                        pass

                    prod["arbolCategorias"] = arbol_categorias
                    prod["ean"] = ean_valor

                except Exception as e:
                    logger.warning("No se pudo enriquecer %s: %s", prod.get("urlProducto"), e)
                    prod["arbolCategorias"] = prod.get("arbolCategorias")
                    prod["ean"] = prod.get("ean")

            await navegador.close()

            # --- Generar Excel ---
            carpeta = os.path.join(settings.MEDIA_ROOT, "catalogacion")
            os.makedirs(carpeta, exist_ok=True)
            nombre_archivo = (
                f'ProductosMarketPlace-Provincia-{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            )
            ruta_final = os.path.join(carpeta, nombre_archivo)
            df = pd.DataFrame(lista_productos)
            df.to_excel(ruta_final, index=False)

            ruta_relativa = f"catalogacion/{nombre_archivo}"
            await self._guardar_archivo(tarea, ruta_relativa)
            await self._log(tarea, f"Proceso finalizado, archivo guardado en {ruta_final}")
