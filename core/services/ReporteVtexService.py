from asgiref.sync import sync_to_async

from core.models import ReporteVtex, TransaccionVtex, UsuarioVtex

from django.conf import settings
import logging
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import pandas as pd
import time

logger = logging.getLogger(__name__)


class ReporteVtexService:
    """Servicio para generar reportes de transacciones de VTEX."""

    TIEMPO_DE_ESPERA = 900000  # 900 segundos (15 minutos)

    def __init__(self, ruta_carpeta=None):
        """
        Inicializa el servicio de reportes VTEX.

        Args:
            ruta_carpeta: Ruta donde se guardarán los archivos descargados.
                         Si no se proporciona, usa MEDIA_ROOT de Django.
        """
        # Si no se proporciona ruta, usar MEDIA_ROOT
        if ruta_carpeta is None:
            self.ruta_carpeta = settings.MEDIA_ROOT
        else:
            self.ruta_carpeta = ruta_carpeta

        # Asegurar que el directorio existe
        os.makedirs(self.ruta_carpeta, exist_ok=True)

    async def _obtener_credenciales(self):
        """
        Obtiene credenciales de VTEX desde la base de datos.

        Returns:
            UsuarioVtex: Objeto con credenciales (app_key, app_token, account_name)

        Raises:
            ValueError: Si no hay credenciales configuradas
        """
        credenciales = await sync_to_async(UsuarioVtex.objects.first)()
        if not credenciales:
            raise ValueError(
                "No hay credenciales de VTEX configuradas. "
                "Por favor, configure las credenciales en el Admin de Django (/admin)."
            )
        return credenciales

    async def generar_reporte(self, fecha_inicio, fecha_fin, reporte_id):
        """
        Genera un reporte de VTEX para el rango de fechas especificado.

        Args:
            fecha_inicio: Fecha de inicio en formato DD/MM/YYYY
            fecha_fin: Fecha de fin en formato DD/MM/YYYY
            reporte_id: ID del objeto ReporteVtex en la base de datos

        Returns:
            bool: True si se generó exitosamente, False en caso contrario
        """
        try:
            # Obtener el reporte de la base de datos
            reporte = await sync_to_async(ReporteVtex.objects.get)(id=reporte_id)

            # Actualizar estado a PROCESANDO
            reporte.estado = ReporteVtex.Estado.PROCESANDO
            await sync_to_async(reporte.save)()

            logger.info(f"Generando reporte VTEX desde {fecha_inicio} hasta {fecha_fin}")

            # Obtener credenciales desde la base de datos
            credenciales = await self._obtener_credenciales()

            # Descargar pedidos (envolver método síncrono en sync_to_async)
            pedidos_vtex = await sync_to_async(self.descargarVtex)(
                fecha_inicio,
                fecha_fin,
                credenciales
            )

            # Guardar transacciones en la base de datos
            cantidad = await self.guardar_transacciones(pedidos_vtex, reporte)

            # Actualizar estado a COMPLETADO
            reporte.estado = ReporteVtex.Estado.COMPLETADO
            await sync_to_async(reporte.save)()

            logger.info(
                f"Reporte VTEX #{reporte_id} generado exitosamente. "
                f"{cantidad} transacciones guardadas."
            )
            return True

        except ReporteVtex.DoesNotExist:
            logger.error(f"Reporte VTEX #{reporte_id} no encontrado")
            return False
        except ValueError as e:
            logger.error(f"Error de configuración: {str(e)}")
            try:
                reporte.estado = ReporteVtex.Estado.ERROR
                await sync_to_async(reporte.save)()
            except:
                pass
            return False
        except Exception as e:
            logger.error(f"Error al generar reporte VTEX #{reporte_id}: {str(e)}", exc_info=True)
            try:
                reporte.estado = ReporteVtex.Estado.ERROR
                await sync_to_async(reporte.save)()
            except:
                pass
            return False

    async def guardar_transacciones(self, transacciones_df, reporte):
        """
        Guarda las transacciones en la base de datos.

        Args:
            transacciones_df: DataFrame de pandas con las transacciones
                            Columnas esperadas: orderId, sequence, creationDate,
                                              paymentNames, seller, statusDescription
            reporte: Objeto ReporteVtex

        Returns:
            int: Cantidad de transacciones guardadas
        """
        if transacciones_df.empty:
            logger.warning("DataFrame de transacciones vacío, no hay nada que guardar")
            return 0

        transacciones_objetos = []

        for _, row in transacciones_df.iterrows():
            try:
                # Parsear fecha (puede venir en diferentes formatos)
                fecha_hora = pd.to_datetime(row['creationDate'], utc=True)

                transaccion = TransaccionVtex(
                    numero_pedido=str(row['orderId']),
                    numero_transaccion=str(row['sequence']),
                    fecha_hora=fecha_hora,
                    medio_pago=str(row.get('paymentNames', 'N/A')),
                    seller=str(row.get('seller', 'No encontrado')),
                    estado=str(row.get('statusDescription', 'Desconocido')),
                    reporte=reporte
                )
                transacciones_objetos.append(transaccion)

            except Exception as e:
                logger.warning(f"Error procesando transacción {row.get('orderId', 'N/A')}: {e}")
                continue

        # Inserción en lote (eficiente para grandes volúmenes)
        if transacciones_objetos:
            await sync_to_async(TransaccionVtex.objects.bulk_create)(
                transacciones_objetos,
                batch_size=1000
            )
            logger.info(f"Guardadas {len(transacciones_objetos)} transacciones VTEX")

        return len(transacciones_objetos)

    def formatear(self, fecha):
        """Formatea fecha para la API de VTEX"""
        return fecha.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    def get_pedidos(self, ini, fin, url, headers):
        """
        Hace una request y devuelve los pedidos + cantidad de páginas.

        Args:
            ini: Fecha inicio
            fin: Fecha fin
            url: URL de la API
            headers: Headers con credenciales

        Returns:
            tuple: (lista de pedidos, cantidad de páginas)
        """
        params = {
            "f_creationDate": f"creationDate:[{self.formatear(ini)} TO {self.formatear(fin)}]",
            "page": 1,
            "per_page": 100,
            "orderBy": "creationDate,asc"
        }
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        return data.get("list", []), data.get("paging", {}).get("pages", 0)

    def buscarSeller(self, order_id, url_base, headers, reintentos=3):
        """
        Busca el seller de un pedido específico.

        Args:
            order_id: ID del pedido
            url_base: URL base de la API
            headers: Headers con credenciales
            reintentos: Número de reintentos en caso de error

        Returns:
            tuple: (order_id, nombre del seller)
        """
        url_detalle = f"{url_base}/{order_id}"
        for intento in range(reintentos):
            try:
                response = requests.get(url_detalle, headers=headers, timeout=10)
                data = response.json()
                return order_id, data.get("sellers", [{}])[0].get("name", "No encontrado")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Error al buscar seller para {order_id}: {e}")
                time.sleep(2 ** intento)  # Backoff exponencial
        return order_id, "Error al obtener seller"

    def procesar_lote(self, pedidos_lote, url_base, headers):
        """
        Procesa un lote de pedidos en paralelo para obtener sellers.

        Args:
            pedidos_lote: Lista de pedidos
            url_base: URL base de la API
            headers: Headers con credenciales

        Returns:
            list: Lista de tuplas (order_id, seller)
        """
        resultados = []
        with ThreadPoolExecutor(max_workers=150) as executor:
            futures = [
                executor.submit(self.buscarSeller, pedido["orderId"], url_base, headers)
                for pedido in pedidos_lote
            ]
            for future in as_completed(futures):
                resultados.append(future.result())
        return resultados

    def descargarVtex(self, fecha_inicio_usuario, fecha_fin_usuario, credenciales):
        """
        Descarga pedidos de VTEX usando la API.

        Args:
            fecha_inicio_usuario: Fecha inicio DD/MM/YYYY
            fecha_fin_usuario: Fecha fin DD/MM/YYYY
            credenciales: Objeto UsuarioVtex con app_key, app_token, account_name

        Returns:
            DataFrame: Pedidos de VTEX procesados
        """
        # Configuración API usando credenciales de la base de datos
        url = f"https://{credenciales.account_name}.vtexcommercestable.com.br/api/oms/pvt/orders"
        headers = {
            'Accept': "application/json",
            'Content-Type': "application/json",
            'X-VTEX-API-AppKey': credenciales.app_key,
            'X-VTEX-API-AppToken': credenciales.app_token
        }

        # Fechas de entrada
        fecha_desde = datetime.strptime(fecha_inicio_usuario, "%d/%m/%Y") + timedelta(hours=3)
        fecha_hasta = datetime.strptime(fecha_fin_usuario, "%d/%m/%Y") + timedelta(
            hours=23, minutes=59, seconds=59
        ) + timedelta(hours=3)

        per_page = 100
        todos_los_pedidos = []
        fecha_actual = fecha_desde
        delta = timedelta(days=1)

        # Descargar pedidos por intervalos
        while fecha_actual < fecha_hasta:
            fecha_siguiente = fecha_actual + delta
            if fecha_siguiente > fecha_hasta:
                fecha_siguiente = fecha_hasta

            pedidos, paginas = self.get_pedidos(fecha_actual, fecha_siguiente, url, headers)
            logger.info(f"Probando con {fecha_actual} a {fecha_siguiente} - {paginas} páginas")

            if paginas > 30:
                delta = delta / 2
                logger.info("Demasiadas páginas, achicando intervalo")
                continue

            # Si está bien, descargamos todas las páginas del subintervalo
            for page in range(1, paginas + 1):
                params = {
                    "f_creationDate": f"creationDate:[{self.formatear(fecha_actual)} TO {self.formatear(fecha_siguiente)}]",
                    "page": page,
                    "per_page": per_page,
                    "orderBy": "creationDate,asc"
                }
                response = requests.get(url, headers=headers, params=params)
                data = response.json()
                pedidos = data.get("list", [])
                todos_los_pedidos.extend(pedidos)
                logger.info(f"Página {page}/{paginas} del intervalo - {len(pedidos)} pedidos")

            fecha_actual = fecha_siguiente
            delta = timedelta(days=1)  # restauramos el paso si venía de achicarlo

        logger.info(f"Generando Excel con los pedidos sin seller")

        # Usar self.ruta_carpeta en lugar de os.getcwd()
        ruta_carpeta = os.path.join(self.ruta_carpeta, "vtex")
        os.makedirs(ruta_carpeta, exist_ok=True)

        archivo_sin_seller = os.path.join(
            ruta_carpeta,
            f"pedidos_vtex_{fecha_desde.date()}_a_{fecha_hasta.date()}_SIN_SELLER.xlsx"
        )
        pd.DataFrame(todos_los_pedidos).to_excel(archivo_sin_seller, index=False)
        logger.info(f"Exportado a: {archivo_sin_seller}")

        # Convertir de nuevo a lista
        todos_los_pedidos = pd.read_excel(archivo_sin_seller)
        todos_los_pedidos = todos_los_pedidos.to_dict(orient="records")

        logger.info(f"Eliminando repetidos")

        pedidos_unicos = {}
        for pedido in todos_los_pedidos:
            pedidos_unicos[pedido["orderId"]] = pedido

        logger.info(f"Buscando el seller de cada pedido")

        # Procesar en lotes de 6000 (rate limiting)
        for i in range(0, len(todos_los_pedidos), 6000):
            lote = todos_los_pedidos[i:i + 6000]
            inicio = time.time()

            # Pasar url y headers al procesar_lote
            resultados = self.procesar_lote(lote, url, headers)

            # Asignar seller al pedido correspondiente
            for order_id, seller in resultados:
                for pedido in todos_los_pedidos:
                    if pedido["orderId"] == order_id:
                        pedido["seller"] = seller
                        break

            # Esperar si el lote fue muy rápido (respetar 60 segundos por 6000 requests)
            duracion = time.time() - inicio
            if duracion < 60:
                logger.info(f"Se alcanzaron las transacciones maximas, durmiendo {60 - duracion} segundos")
                time.sleep(60 - duracion)
            logger.info(f"Se descargaron {i} pedidos")

        logger.info(f"Descargas finalizadas. Convirtiendo a Excel")

        # Exportar a Excel final
        archivo_final = os.path.join(
            ruta_carpeta,
            f"pedidos_vtex_{fecha_desde.date()}_a_{fecha_hasta.date()}.xlsx"
        )
        pedidos_vtex = pd.DataFrame(todos_los_pedidos)

        # Seleccionar solo las columnas necesarias
        pedidos_vtex = pedidos_vtex[
            ["orderId", "sequence", "creationDate", "paymentNames", "seller", "statusDescription"]
        ]

        # Exportar archivo final
        pedidos_vtex.to_excel(archivo_final, index=False)
        logger.info(f"Archivo final exportado a: {archivo_final}")

        return pedidos_vtex
