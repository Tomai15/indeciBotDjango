"""
Tests para modelos de cruces.
"""
import pytest
from datetime import date, datetime, timezone

from core.models import (
    Cruce,
    TransaccionCruce,
    ReporteVtex,
    ReportePayway,
    ReporteCDP,
    ReporteJanis,
)


class TestCruce:
    """Tests para el modelo Cruce."""

    def test_crear_cruce(self, db):
        """Test crear un cruce basico."""
        cruce = Cruce.objects.create(
            fecha_inicio=date(2024, 1, 1),
            fecha_fin=date(2024, 1, 31)
        )
        assert cruce.id is not None
        assert cruce.estado == Cruce.Estado.PENDIENTE
        assert cruce.fecha_realizado is None

    def test_estados_cruce(self, cruce):
        """Test cambiar estados del cruce."""
        assert cruce.estado == Cruce.Estado.PENDIENTE

        cruce.estado = Cruce.Estado.PROCESANDO
        cruce.save()
        assert cruce.estado == "PROCESANDO"

        cruce.estado = Cruce.Estado.COMPLETADO
        cruce.fecha_realizado = date.today()
        cruce.save()
        assert cruce.estado == "COMPLETADO"
        assert cruce.fecha_realizado is not None

    def test_cruce_con_reportes(self, cruce_con_reportes, reporte_vtex, reporte_payway, reporte_cdp, reporte_janis):
        """Test cruce con reportes asociados."""
        assert cruce_con_reportes.reporte_vtex == reporte_vtex
        assert cruce_con_reportes.reporte_payway == reporte_payway
        assert cruce_con_reportes.reporte_cdp == reporte_cdp
        assert cruce_con_reportes.reporte_janis == reporte_janis

    def test_cruce_sin_reportes(self, cruce):
        """Test cruce sin reportes (todos null)."""
        assert cruce.reporte_vtex is None
        assert cruce.reporte_payway is None
        assert cruce.reporte_cdp is None
        assert cruce.reporte_janis is None

    def test_cruce_reportes_parciales(self, db, reporte_vtex, reporte_payway):
        """Test cruce con solo algunos reportes."""
        cruce = Cruce.objects.create(
            fecha_inicio=date(2024, 1, 1),
            fecha_fin=date(2024, 1, 31),
            reporte_vtex=reporte_vtex,
            reporte_payway=reporte_payway
            # Sin CDP ni Janis
        )
        assert cruce.reporte_vtex == reporte_vtex
        assert cruce.reporte_payway == reporte_payway
        assert cruce.reporte_cdp is None
        assert cruce.reporte_janis is None

    def test_campo_revisar(self, cruce):
        """Test campo revisar del cruce."""
        assert cruce.revisar == ''

        cruce.revisar = "Revisar transacciones duplicadas"
        cruce.save()
        cruce.refresh_from_db()

        assert cruce.revisar == "Revisar transacciones duplicadas"

    def test_relacion_inversa_desde_reportes(self, cruce_con_reportes, reporte_vtex):
        """Test acceder a cruces desde un reporte."""
        assert cruce_con_reportes in reporte_vtex.cruces.all()

    def test_on_delete_set_null(self, db):
        """Test que al eliminar un reporte, el cruce mantiene null."""
        reporte = ReporteVtex.objects.create(
            fecha_inicio=date(2024, 1, 1),
            fecha_fin=date(2024, 1, 31)
        )
        cruce = Cruce.objects.create(
            fecha_inicio=date(2024, 1, 1),
            fecha_fin=date(2024, 1, 31),
            reporte_vtex=reporte
        )

        reporte_id = reporte.id
        reporte.delete()

        cruce.refresh_from_db()
        assert cruce.reporte_vtex is None
        assert not ReporteVtex.objects.filter(id=reporte_id).exists()


class TestTransaccionCruce:
    """Tests para el modelo TransaccionCruce."""

    def test_crear_transaccion_cruce(self, cruce, db):
        """Test crear una transaccion de cruce."""
        transaccion = TransaccionCruce.objects.create(
            numero_pedido="1234567890123-01",
            fecha_hora=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
            medio_pago="Visa",
            seller="Carrefour",
            estado_vtex="invoiced",
            estado_payway="Aprobada",
            estado_cdp="Finalizado",
            estado_janis="delivered",
            cruce=cruce
        )
        assert transaccion.id is not None
        assert transaccion.numero_pedido == "1234567890123-01"

    def test_campos_opcionales_vacios(self, cruce, db):
        """Test que los campos opcionales pueden estar vacios."""
        transaccion = TransaccionCruce.objects.create(
            numero_pedido="1234567890123-01",
            cruce=cruce
            # Todos los demas campos usan defaults
        )
        assert transaccion.medio_pago == ''
        assert transaccion.seller == ''
        assert transaccion.estado_vtex == ''
        assert transaccion.estado_payway == ''
        assert transaccion.estado_payway_2 == ''
        assert transaccion.estado_cdp == ''
        assert transaccion.estado_janis == ''
        assert transaccion.resultado_cruce == ''

    def test_convertir_en_diccionario(self, transaccion_cruce):
        """Test convertir transaccion cruce a diccionario."""
        diccionario = transaccion_cruce.convertir_en_diccionario()

        assert diccionario["Pedido"] == transaccion_cruce.numero_pedido
        assert diccionario["medio_pago"] == transaccion_cruce.medio_pago
        assert diccionario["seller"] == transaccion_cruce.seller
        assert diccionario["estado_vtex"] == transaccion_cruce.estado_vtex
        assert diccionario["estado_payway"] == transaccion_cruce.estado_payway
        assert diccionario["estado_payway_2"] == transaccion_cruce.estado_payway_2
        assert diccionario["estado_cdp"] == transaccion_cruce.estado_cdp
        assert diccionario["estado_janis"] == transaccion_cruce.estado_janis
        assert diccionario["resultado_cruce"] == transaccion_cruce.resultado_cruce

    def test_estado_payway_doble(self, cruce, db):
        """Test transaccion con doble estado de Payway."""
        transaccion = TransaccionCruce.objects.create(
            numero_pedido="1234567890123-01",
            estado_payway="Aprobada",
            estado_payway_2="Aprobada",
            cruce=cruce
        )
        assert transaccion.estado_payway == "Aprobada"
        assert transaccion.estado_payway_2 == "Aprobada"

    def test_resultado_cruce(self, cruce, db):
        """Test campo resultado_cruce."""
        transaccion = TransaccionCruce.objects.create(
            numero_pedido="1234567890123-01",
            estado_vtex="invoiced",
            estado_payway="",
            resultado_cruce="Falta en Payway",
            cruce=cruce
        )
        assert transaccion.resultado_cruce == "Falta en Payway"

    def test_relacion_con_cruce(self, transaccion_cruce, cruce):
        """Test relacion transaccion -> cruce."""
        assert transaccion_cruce.cruce == cruce
        assert transaccion_cruce in cruce.transacciones.all()

    def test_multiples_transacciones_por_cruce(self, cruce, db):
        """Test crear multiples transacciones para un cruce."""
        for i in range(5):
            TransaccionCruce.objects.create(
                numero_pedido=f"PEDIDO-{i:03d}",
                cruce=cruce
            )

        assert cruce.transacciones.count() == 5

    def test_eliminar_cruce_elimina_transacciones(self, cruce, db):
        """Test que al eliminar un cruce se eliminan sus transacciones (CASCADE)."""
        for i in range(3):
            TransaccionCruce.objects.create(
                numero_pedido=f"PEDIDO-{i:03d}",
                cruce=cruce
            )

        assert TransaccionCruce.objects.count() == 3

        cruce.delete()

        assert TransaccionCruce.objects.count() == 0

    def test_fecha_hora_nullable(self, cruce, db):
        """Test que fecha_hora puede ser null."""
        transaccion = TransaccionCruce.objects.create(
            numero_pedido="1234567890123-01",
            fecha_hora=None,
            cruce=cruce
        )
        assert transaccion.fecha_hora is None
