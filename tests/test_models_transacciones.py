"""
Tests para modelos de transacciones.
"""
import pytest
from datetime import datetime, timezone
from decimal import Decimal

from core.models import (
    TransaccionPayway,
    TransaccionVtex,
    TransaccionCDP,
    TransaccionJanis,
)


class TestTransaccionPayway:
    """Tests para el modelo TransaccionPayway."""

    def test_crear_transaccion_payway(self, reporte_payway, db):
        """Test crear una transaccion de Payway."""
        transaccion = TransaccionPayway.objects.create(
            numero_transaccion="TXN-12345",
            fecha_hora=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
            monto=Decimal("1000.00"),
            estado="Aprobada",
            tarjeta="VISA",
            reporte=reporte_payway
        )
        assert transaccion.id is not None
        assert transaccion.numero_transaccion == "TXN-12345"
        assert transaccion.monto == Decimal("1000.00")

    def test_convertir_en_diccionario(self, transaccion_payway):
        """Test convertir transaccion a diccionario."""
        diccionario = transaccion_payway.convertir_en_diccionario()

        assert diccionario["Transaccion"] == transaccion_payway.numero_transaccion
        assert diccionario["monto"] == transaccion_payway.monto
        assert diccionario["estado"] == transaccion_payway.estado
        assert diccionario["tarjeta"] == transaccion_payway.tarjeta
        assert "fecha" in diccionario

    def test_estado_no_cobrado_preautorizada(self, reporte_payway, db):
        """Test que Pre autorizada es estado no cobrado."""
        transaccion = TransaccionPayway.objects.create(
            numero_transaccion="TXN-001",
            fecha_hora=datetime.now(timezone.utc),
            monto=Decimal("500.00"),
            estado="Pre autorizada",
            tarjeta="MASTERCARD",
            reporte=reporte_payway
        )
        assert transaccion.estado_no_cobrado() is True

    def test_estado_no_cobrado_vencida(self, reporte_payway, db):
        """Test que Vencida es estado no cobrado."""
        transaccion = TransaccionPayway.objects.create(
            numero_transaccion="TXN-002",
            fecha_hora=datetime.now(timezone.utc),
            monto=Decimal("500.00"),
            estado="Vencida",
            tarjeta="VISA",
            reporte=reporte_payway
        )
        assert transaccion.estado_no_cobrado() is True

    def test_estado_cobrado(self, transaccion_payway):
        """Test que Aprobada NO es estado no cobrado."""
        assert transaccion_payway.estado_no_cobrado() is False

    def test_relacion_con_reporte(self, transaccion_payway, reporte_payway):
        """Test relacion transaccion -> reporte."""
        assert transaccion_payway.reporte == reporte_payway
        assert transaccion_payway in reporte_payway.transacciones.all()


class TestTransaccionVtex:
    """Tests para el modelo TransaccionVtex."""

    def test_crear_transaccion_vtex(self, reporte_vtex, db):
        """Test crear una transaccion de VTEX."""
        transaccion = TransaccionVtex.objects.create(
            numero_pedido="1234567890123-01",
            numero_transaccion="TXN-VTEX-001",
            fecha_hora=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
            medio_pago="Visa",
            seller="Carrefour Hiper",
            estado="invoiced",
            valor=Decimal("2500.00"),
            reporte=reporte_vtex
        )
        assert transaccion.id is not None
        assert transaccion.numero_pedido == "1234567890123-01"

    def test_convertir_en_diccionario(self, transaccion_vtex):
        """Test convertir transaccion a diccionario."""
        diccionario = transaccion_vtex.convertir_en_diccionario()

        assert diccionario["Pedido"] == transaccion_vtex.numero_pedido
        assert diccionario["Transaccion"] == transaccion_vtex.numero_transaccion
        assert diccionario["medio_pago"] == transaccion_vtex.medio_pago
        assert diccionario["seller"] == transaccion_vtex.seller
        assert diccionario["estado"] == transaccion_vtex.estado
        assert diccionario["valor"] == transaccion_vtex.valor

    def test_pedido_electro(self, reporte_vtex, db):
        """Test identificar pedido de Electro."""
        transaccion = TransaccionVtex.objects.create(
            numero_pedido="1234567890123-01",
            numero_transaccion="TXN-001",
            fecha_hora=datetime.now(timezone.utc),
            medio_pago="Visa",
            seller="Hogar & Electro",
            estado="invoiced",
            reporte=reporte_vtex
        )
        assert transaccion.pedido_electro() is True
        assert transaccion.pedido_food() is False
        assert transaccion.pedido_marketplace() is False

    def test_pedido_food_carrefour(self, reporte_vtex, db):
        """Test identificar pedido Food de Carrefour."""
        transaccion = TransaccionVtex.objects.create(
            numero_pedido="1234567890123-01",
            numero_transaccion="TXN-001",
            fecha_hora=datetime.now(timezone.utc),
            medio_pago="Visa",
            seller="Carrefour Hiper San Martin",
            estado="invoiced",
            reporte=reporte_vtex
        )
        assert transaccion.pedido_food() is True
        assert transaccion.pedido_electro() is False

    def test_pedido_food_maxi(self, reporte_vtex, db):
        """Test identificar pedido Food de Maxi."""
        transaccion = TransaccionVtex.objects.create(
            numero_pedido="1234567890123-01",
            numero_transaccion="TXN-001",
            fecha_hora=datetime.now(timezone.utc),
            medio_pago="Visa",
            seller="Maxi Avellaneda",
            estado="invoiced",
            reporte=reporte_vtex
        )
        assert transaccion.pedido_food() is True

    def test_pedido_food_express(self, reporte_vtex, db):
        """Test identificar pedido Food de Express."""
        transaccion = TransaccionVtex.objects.create(
            numero_pedido="1234567890123-01",
            numero_transaccion="TXN-001",
            fecha_hora=datetime.now(timezone.utc),
            medio_pago="Visa",
            seller="Carrefour Express Centro",
            estado="invoiced",
            reporte=reporte_vtex
        )
        assert transaccion.pedido_food() is True

    def test_pedido_marketplace(self, reporte_vtex, db):
        """Test identificar pedido de Marketplace."""
        transaccion = TransaccionVtex.objects.create(
            numero_pedido="1234567890123-01",
            numero_transaccion="TXN-001",
            fecha_hora=datetime.now(timezone.utc),
            medio_pago="Visa",
            seller="Samsung Official Store",
            estado="invoiced",
            reporte=reporte_vtex
        )
        assert transaccion.pedido_marketplace() is True
        assert transaccion.pedido_food() is False
        assert transaccion.pedido_electro() is False

    def test_valor_nullable(self, reporte_vtex, db):
        """Test que valor puede ser null."""
        transaccion = TransaccionVtex.objects.create(
            numero_pedido="1234567890123-01",
            numero_transaccion="TXN-001",
            fecha_hora=datetime.now(timezone.utc),
            medio_pago="Visa",
            seller="Test",
            estado="invoiced",
            valor=None,
            reporte=reporte_vtex
        )
        assert transaccion.valor is None


class TestTransaccionCDP:
    """Tests para el modelo TransaccionCDP."""

    def test_crear_transaccion_cdp(self, reporte_cdp, db):
        """Test crear una transaccion de CDP."""
        transaccion = TransaccionCDP.objects.create(
            numero_pedido="1234567890123-01",
            fecha_hora=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
            numero_tienda=Decimal("101"),
            estado="Finalizado",
            reporte=reporte_cdp
        )
        assert transaccion.id is not None
        assert transaccion.numero_pedido == "1234567890123-01"

    def test_convertir_en_diccionario(self, transaccion_cdp):
        """Test convertir transaccion a diccionario."""
        diccionario = transaccion_cdp.convertir_en_diccionario()

        assert diccionario["Pedido"] == transaccion_cdp.numero_pedido
        assert diccionario["numero_tienda"] == transaccion_cdp.numero_tienda
        assert diccionario["estado"] == transaccion_cdp.estado

    def test_estado_entregado_finalizado(self, transaccion_cdp):
        """Test que Finalizado es estado entregado."""
        assert transaccion_cdp.estado_entregado() is True

    def test_estado_entregado_disponible_drive(self, reporte_cdp, db):
        """Test que disponible en drive es estado entregado."""
        transaccion = TransaccionCDP.objects.create(
            numero_pedido="1234567890123-01",
            fecha_hora=datetime.now(timezone.utc),
            numero_tienda=Decimal("101"),
            estado="Disponible en Drive",
            reporte=reporte_cdp
        )
        assert transaccion.estado_entregado() is True

    def test_estado_entregado_pendiente_despacho(self, reporte_cdp, db):
        """Test que pendiente de despacho es estado entregado."""
        transaccion = TransaccionCDP.objects.create(
            numero_pedido="1234567890123-01",
            fecha_hora=datetime.now(timezone.utc),
            numero_tienda=Decimal("101"),
            estado="Pendiente de Despacho",
            reporte=reporte_cdp
        )
        assert transaccion.estado_entregado() is True

    def test_estado_no_entregado(self, reporte_cdp, db):
        """Test que un estado no listado NO es entregado."""
        transaccion = TransaccionCDP.objects.create(
            numero_pedido="1234567890123-01",
            fecha_hora=datetime.now(timezone.utc),
            numero_tienda=Decimal("101"),
            estado="Cancelado",
            reporte=reporte_cdp
        )
        assert transaccion.estado_entregado() is False


class TestTransaccionJanis:
    """Tests para el modelo TransaccionJanis."""

    def test_crear_transaccion_janis(self, reporte_janis, db):
        """Test crear una transaccion de Janis."""
        transaccion = TransaccionJanis.objects.create(
            numero_pedido="1234567890123-01",
            numero_transaccion="TXN-JANIS-001",
            fecha_hora=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
            medio_pago="Visa",
            seller="Carrefour",
            estado="delivered",
            reporte=reporte_janis
        )
        assert transaccion.id is not None

    def test_convertir_en_diccionario(self, transaccion_janis):
        """Test convertir transaccion a diccionario."""
        diccionario = transaccion_janis.convertir_en_diccionario()

        assert diccionario["Pedido"] == transaccion_janis.numero_pedido
        assert diccionario["Transaccion"] == transaccion_janis.numero_transaccion
        assert diccionario["medio_pago"] == transaccion_janis.medio_pago
        assert diccionario["seller"] == transaccion_janis.seller
        assert diccionario["estado"] == transaccion_janis.estado

    def test_estado_entregado_delivered(self, transaccion_janis):
        """Test que delivered es estado entregado."""
        assert transaccion_janis.estado_entregado() is True

    def test_estado_entregado_in_delivery(self, reporte_janis, db):
        """Test que inDelivery es estado entregado."""
        transaccion = TransaccionJanis.objects.create(
            numero_pedido="1234567890123-01",
            numero_transaccion="TXN-001",
            fecha_hora=datetime.now(timezone.utc),
            medio_pago="Visa",
            seller="Test",
            estado="inDelivery",
            reporte=reporte_janis
        )
        assert transaccion.estado_entregado() is True

    def test_estado_entregado_ready_for_delivery(self, reporte_janis, db):
        """Test que readyForDelivery es estado entregado."""
        transaccion = TransaccionJanis.objects.create(
            numero_pedido="1234567890123-01",
            numero_transaccion="TXN-001",
            fecha_hora=datetime.now(timezone.utc),
            medio_pago="Visa",
            seller="Test",
            estado="readyForDelivery",
            reporte=reporte_janis
        )
        assert transaccion.estado_entregado() is True

    def test_estado_no_entregado(self, reporte_janis, db):
        """Test que un estado no listado NO es entregado."""
        transaccion = TransaccionJanis.objects.create(
            numero_pedido="1234567890123-01",
            numero_transaccion="TXN-001",
            fecha_hora=datetime.now(timezone.utc),
            medio_pago="Visa",
            seller="Test",
            estado="canceled",
            reporte=reporte_janis
        )
        assert transaccion.estado_entregado() is False
