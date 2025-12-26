import pandas as pd
from asgiref.sync import sync_to_async
from playwright.sync_api import sync_playwright

from core.models import ReporteCDP, TransaccionCDP, UsuarioCDP

from django.conf import settings
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ReporteCDPService:
    """Servicio para generar reportes de transacciones de CDP."""

    def __init__(self, ruta_carpeta=None):
        """
        Inicializa el servicio de reportes CDP.

        Args:
            ruta_carpeta: Ruta donde se guardaran los archivos descargados.
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
        Obtiene credenciales de CDP desde la base de datos.

        Returns:
            UsuarioCDP: Objeto con credenciales (usuario, clave)

        Raises:
            ValueError: Si no hay credenciales configuradas
        """
        credenciales = await sync_to_async(UsuarioCDP.objects.first)()
        if not credenciales:
            raise ValueError(
                "No hay credenciales de CDP configuradas. "
                "Por favor, configure las credenciales en Ajustes."
            )
        return credenciales

    async def generar_reporte(self, fecha_inicio, fecha_fin, reporte_id):
        """
        Genera un reporte de CDP para el rango de fechas especificado.

        Args:
            fecha_inicio: Fecha de inicio en formato DD/MM/YYYY
            fecha_fin: Fecha de fin en formato DD/MM/YYYY
            reporte_id: ID del objeto ReporteCDP en la base de datos

        Returns:
            bool: True si se genero exitosamente, False en caso contrario
        """
        try:
            # Obtener el reporte de la base de datos
            reporte = await sync_to_async(ReporteCDP.objects.get)(id=reporte_id)

            # Actualizar estado a PROCESANDO
            reporte.estado = ReporteCDP.Estado.PROCESANDO
            await sync_to_async(reporte.save)()

            logger.info(f"Generando reporte CDP desde {fecha_inicio} hasta {fecha_fin}")

            # Obtener credenciales desde la base de datos
            credenciales = await self._obtener_credenciales()

            # TODO: Implementar la logica de descarga de CDP
            # Aqui deberas implementar la conexion con la API/sistema de CDP
            # y obtener las transacciones correspondientes al rango de fechas
            transacciones_cdp = await self.descargar_transacciones_cdp(
                fecha_inicio,
                fecha_fin,
                credenciales
            )

            # Guardar transacciones en la base de datos
            cantidad = await self.guardar_transacciones(transacciones_cdp, reporte)

            # Actualizar estado a COMPLETADO
            reporte.estado = ReporteCDP.Estado.COMPLETADO
            await sync_to_async(reporte.save)()

            logger.info(
                f"Reporte CDP #{reporte_id} generado exitosamente. "
                f"{cantidad} transacciones guardadas."
            )
            return True

        except ReporteCDP.DoesNotExist:
            logger.error(f"Reporte CDP #{reporte_id} no encontrado")
            return False
        except ValueError as e:
            logger.error(f"Error de configuracion: {str(e)}")
            try:
                reporte.estado = ReporteCDP.Estado.ERROR
                await sync_to_async(reporte.save)()
            except:
                pass
            return False
        except Exception as e:
            logger.error(f"Error al generar reporte CDP #{reporte_id}: {str(e)}", exc_info=True)
            try:
                reporte.estado = ReporteCDP.Estado.ERROR
                await sync_to_async(reporte.save)()
            except:
                pass
            return False

    async def descargar_transacciones_cdp(self, fecha_inicio, fecha_fin, credenciales):
        """
        Descarga las transacciones de CDP usando Playwright.

        Args:
            fecha_inicio: Fecha de inicio en formato DD/MM/YYYY
            fecha_fin: Fecha de fin en formato DD/MM/YYYY
            credenciales: Objeto UsuarioCDP con usuario y clave

        Returns:
            list: Lista de diccionarios con las transacciones
        """
        # Ejecutar la descarga síncrona en un thread separado para no bloquear el event loop
        return await sync_to_async(self._descargar_transacciones_cdp_sync)(
            fecha_inicio, fecha_fin, credenciales
        )

    def _descargar_transacciones_cdp_sync(self, fecha_inicio, fecha_fin, credenciales):
        """
        Método síncrono interno que realiza la descarga con Playwright.
        """
        with sync_playwright() as navegador:
            tiempo_de_espera = 900000  # 15 minutos en ms
            fecha_inicio_parseada = datetime.strptime(fecha_inicio, "%d/%m/%Y")
            fecha_fin_parseada = datetime.strptime(fecha_fin, "%d/%m/%Y")

            navegador_web = navegador.chromium.launch(headless=False)
            pagina = navegador_web.new_page()

            usuario = credenciales.usuario
            contrasena = credenciales.clave

            logger.info("Pasando a descargar en CDP")
            logger.info("Ingresando a: http://10.94.164.155:16000/ConcentradorDePedidos/puntoAdm")
            pagina.goto("http://10.94.164.155:16000/ConcentradorDePedidos/puntoAdm")

            pagina.wait_for_load_state("load", timeout=tiempo_de_espera)
            pagina.fill("input[name='username']", usuario)
            pagina.fill("input[name='password']", contrasena)

            pagina.click("input[type='submit']")
            pagina.wait_for_load_state("load", timeout=tiempo_de_espera)
            pagina.wait_for_selector('select#mySelect')
            pagina.select_option('select#mySelect', value="14")
            pagina.click("input[type='button']")
            pagina.wait_for_load_state("load", timeout=tiempo_de_espera)
            logger.info("Ingreso correcto a CDP")
            logger.info("Ingresando a reportes")
            pagina.goto("http://10.94.164.155:16000/ConcentradorDePedidos/secciones/listadoVentas")
            pagina.wait_for_load_state("load", timeout=tiempo_de_espera)

            pagina.click("text=FILTRAR")
            pagina.fill("input[name='fechaMin']", fecha_inicio)
            pagina.keyboard.press("Escape")  # Cerrar ventana emergente
            pagina.fill("input[name='ctrl.fechaMax']", fecha_fin)
            pagina.keyboard.press("Escape")  # Cerrar ventana emergente
            pagina.click("text=BUSCAR")
            logger.info("Fechas filtradas correctamente. Exportando")
            pagina.wait_for_selector("table tbody tr", timeout=tiempo_de_espera)
            pagina.click("text=EXPORTAR")

            with pagina.expect_download(timeout=tiempo_de_espera) as informacion_descarga:
                pagina.click("text=Sólo Cabecera", timeout=90000)

            # Usar self.ruta_carpeta en lugar de os.getcwd()
            ruta_carpeta = os.path.join(self.ruta_carpeta, "descargas_CDP")
            os.makedirs(ruta_carpeta, exist_ok=True)

            archivo_descargado = informacion_descarga.value
            # Usar las fechas parseadas para el nombre del archivo
            nombre_archivo = f"transacciones_CDP_{fecha_inicio_parseada.strftime('%Y-%m-%d')}_{fecha_fin_parseada.strftime('%Y-%m-%d')}.xlsx"
            logger.info(f"Descarga realizada en {nombre_archivo}")
            ruta_excel = os.path.join(ruta_carpeta, nombre_archivo)
            archivo_descargado.save_as(ruta_excel)

            # Cerrar el navegador
            navegador_web.close()

            # Leer el Excel descargado como DataFrame
            datos_cdp = pd.read_excel(ruta_excel)

            # Elegir solo las columnas que necesitamos
            columnas_a_conservar = ["NUMERO PEDIDO", "NUMERO DE PUNTO", "FECHA PEDIDO", "ESTADO"]
            datos_cdp = datos_cdp[columnas_a_conservar]

            # Renombrar columnas para que coincidan con lo que espera guardar_transacciones
            datos_cdp = datos_cdp.rename(columns={
                "NUMERO PEDIDO": "numero_pedido",
                "NUMERO DE PUNTO": "numero_tienda",
                "FECHA PEDIDO": "fecha_hora",
                "ESTADO": "estado"
            })

            # Sobrescribir el archivo con las columnas filtradas
            datos_cdp.to_excel(ruta_excel, index=False)
            logger.info("Archivo filtrado correctamente con solo las columnas necesarias.")

            # Convertir DataFrame a lista de diccionarios para retornar
            transacciones = datos_cdp.to_dict(orient='records')
            logger.info(f"Se descargaron {len(transacciones)} transacciones de CDP")

            return transacciones

    async def guardar_transacciones(self, transacciones, reporte):
        """
        Guarda las transacciones en la base de datos.

        Args:
            transacciones: Lista de diccionarios con las transacciones
                          Keys esperadas: numero_pedido, fecha_hora, numero_tienda, estado
            reporte: Objeto ReporteCDP

        Returns:
            int: Cantidad de transacciones guardadas
        """
        if not transacciones:
            logger.warning("Lista de transacciones vacia, no hay nada que guardar")
            return 0

        transacciones_objetos = []

        for row in transacciones:
            try:
                # Parsear la fecha del formato DD/MM/YYYY HH:MM:SS a datetime
                fecha_hora_raw = row['fecha_hora']
                if isinstance(fecha_hora_raw, str):
                    fecha_hora = datetime.strptime(fecha_hora_raw, "%d/%m/%Y %H:%M:%S")
                else:
                    # Si ya es datetime (por ejemplo, pandas lo convirtió), usarlo directamente
                    fecha_hora = fecha_hora_raw

                transaccion = TransaccionCDP(
                    numero_pedido=str(row['numero_pedido']),
                    fecha_hora=fecha_hora,
                    numero_tienda=row['numero_tienda'],
                    estado=str(row.get('estado', 'Desconocido')),
                    reporte=reporte
                )
                transacciones_objetos.append(transaccion)

            except Exception as e:
                logger.warning(f"Error procesando transaccion {row.get('numero_pedido', 'N/A')}: {e}")
                continue

        # Insercion en lote (eficiente para grandes volumenes)
        if transacciones_objetos:
            await sync_to_async(TransaccionCDP.objects.bulk_create)(
                transacciones_objetos,
                batch_size=1000
            )
            logger.info(f"Guardadas {len(transacciones_objetos)} transacciones CDP")

        return len(transacciones_objetos)
