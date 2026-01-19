"""
Tests para CruceService.
"""
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch

from core.services.CruceService import CruceService
from core.models import (
    Cruce, TransaccionCruce,
    ReporteVtex, ReportePayway, ReporteCDP, ReporteJanis,
    TransaccionVtex, TransaccionPayway, TransaccionCDP, TransaccionJanis
)


class TestConvertirPedidoTransaccionPayway:
    """Tests para el metodo convertir_pedido_transaccion_payway."""

    def setup_method(self):
        """Setup para cada test."""
        self.service = CruceService()

    def test_conversion_formato_estandar(self):
        """Test conversion de pedido VTEX a formato Payway."""
        # Formato: "1234567890123-01" -> "1234567890123-1"
        resultado = self.service.convertir_pedido_transaccion_payway("1234567890123-01")
        assert resultado == "1234567890123-1"

    def test_conversion_sufijo_ceros(self):
        """Test que elimina ceros del sufijo."""
        resultado = self.service.convertir_pedido_transaccion_payway("9876543210123-02")
        assert resultado == "9876543210123-2"

    def test_conversion_sufijo_mayor(self):
        """Test con sufijo de dos digitos."""
        resultado = self.service.convertir_pedido_transaccion_payway("1234567890123-10")
        assert resultado == "1234567890123-10"

    def test_conversion_sufijo_simple(self):
        """Test con sufijo sin ceros iniciales."""
        resultado = self.service.convertir_pedido_transaccion_payway("1234567890123-5")
        assert resultado == "1234567890123-5"


class TestCalcularResultadoCruce:
    """Tests para el metodo calcular_resultado_cruce."""

    def setup_method(self):
        """Setup para cada test."""
        self.service = CruceService()

    def _crear_mock_vtex(self, estado="Faturado", medio_pago="Visa", seller="Carrefour Hiper"):
        """Helper para crear mock de TransaccionVtex."""
        mock = MagicMock(spec=TransaccionVtex)
        mock.estado = estado
        mock.medio_pago = medio_pago
        mock.seller = seller
        mock.pedido_electro.return_value = seller == "Hogar & Electro"
        mock.pedido_food.return_value = any(
            kw.lower() in seller.lower()
            for kw in ["carrefour", "hiper", "maxi", "market", "express"]
        )
        mock.pedido_marketplace.return_value = not mock.pedido_electro() and not mock.pedido_food()
        return mock

    def _crear_mock_payway(self, estado="Aprobada"):
        """Helper para crear mock de TransaccionPayway."""
        mock = MagicMock(spec=TransaccionPayway)
        mock.estado = estado
        mock.estado_no_cobrado.return_value = estado in ["Pre autorizada", "Vencida"]
        return mock

    def _crear_mock_cdp(self, estado="Finalizado"):
        """Helper para crear mock de TransaccionCDP."""
        mock = MagicMock(spec=TransaccionCDP)
        mock.estado = estado
        mock.estado_entregado.return_value = estado.lower() in [
            "finalizado", "disponible en drive", "disponible en sucursal"
        ]
        return mock

    def _crear_mock_janis(self, estado="delivered"):
        """Helper para crear mock de TransaccionJanis."""
        mock = MagicMock(spec=TransaccionJanis)
        mock.estado = estado
        mock.estado_entregado.return_value = estado in [
            "delivered", "inDelivery", "readyForDelivery"
        ]
        return mock

    def test_sin_vtex_retorna_vacio(self):
        """Test que sin transaccion VTEX retorna string vacio."""
        resultado = self.service.calcular_resultado_cruce(None, None, None, None)
        assert resultado == ""

    def test_vtex_verificando_factura(self):
        """Test estado Verificando Fatura."""
        vtex = self._crear_mock_vtex(estado="Verificando Fatura")
        resultado = self.service.calcular_resultado_cruce(vtex, None, None, None)
        assert "Verificar" in resultado
        assert "verificando factura" in resultado

    def test_food_entregado_no_facturado_cdp(self):
        """Test pedido Food entregado pero no facturado (CDP)."""
        vtex = self._crear_mock_vtex(estado="Pendiente", seller="Carrefour Hiper")
        cdp = self._crear_mock_cdp(estado="Finalizado")

        resultado = self.service.calcular_resultado_cruce(vtex, None, cdp, None)
        assert "Verificar" in resultado
        assert "no facturado" in resultado

    def test_food_entregado_no_facturado_janis(self):
        """Test pedido Food entregado pero no facturado (Janis)."""
        vtex = self._crear_mock_vtex(estado="Pendiente", seller="Maxi Centro")
        janis = self._crear_mock_janis(estado="delivered")

        resultado = self.service.calcular_resultado_cruce(vtex, None, None, janis)
        assert "Verificar" in resultado
        assert "no facturado" in resultado

    def test_food_facturado_payway_no_cobrado(self):
        """Test pedido Food facturado pero no cobrado en Payway."""
        vtex = self._crear_mock_vtex(estado="Faturado", seller="Carrefour Express")
        payway = self._crear_mock_payway(estado="Pre autorizada")
        cdp = self._crear_mock_cdp(estado="Finalizado")

        resultado = self.service.calcular_resultado_cruce(vtex, payway, cdp, None)
        assert "Verificar" in resultado
        assert "no cobrado" in resultado

    def test_food_todo_ok(self):
        """Test pedido Food con todo OK."""
        vtex = self._crear_mock_vtex(estado="Faturado", seller="Carrefour Hiper")
        payway = self._crear_mock_payway(estado="Aprobada")
        cdp = self._crear_mock_cdp(estado="Finalizado")

        resultado = self.service.calcular_resultado_cruce(vtex, payway, cdp, None)
        assert resultado == ""

    def test_electro_payway_no_cobrado(self):
        """Test pedido Electro no cobrado en Payway."""
        vtex = self._crear_mock_vtex(estado="Faturado", seller="Hogar & Electro")
        payway = self._crear_mock_payway(estado="Vencida")

        resultado = self.service.calcular_resultado_cruce(vtex, payway, None, None)
        assert "Verificar" in resultado
        assert "no cobrado" in resultado

    def test_electro_no_facturado(self):
        """Test pedido Electro no facturado."""
        vtex = self._crear_mock_vtex(estado="Pendiente", seller="Hogar & Electro")
        payway = self._crear_mock_payway(estado="Aprobada")

        resultado = self.service.calcular_resultado_cruce(vtex, payway, None, None)
        assert "Verificar" in resultado
        assert "no facturado" in resultado

    def test_electro_cancelado_es_ok(self):
        """Test que pedido Electro cancelado no genera alerta."""
        vtex = self._crear_mock_vtex(estado="Cancelado", seller="Hogar & Electro")
        resultado = self.service.calcular_resultado_cruce(vtex, None, None, None)
        # Cancelado no deberia generar alerta de "no facturado"
        assert "no facturado" not in resultado

    def test_marketplace_no_facturado(self):
        """Test pedido Marketplace no facturado."""
        vtex = self._crear_mock_vtex(estado="Pendiente", seller="Samsung Store")
        resultado = self.service.calcular_resultado_cruce(vtex, None, None, None)
        assert "Avisar a marketplace" in resultado

    def test_marketplace_facturado(self):
        """Test pedido Marketplace facturado OK."""
        vtex = self._crear_mock_vtex(estado="Faturado", seller="LG Official")
        resultado = self.service.calcular_resultado_cruce(vtex, None, None, None)
        assert resultado == ""

    def test_mercadopago_entregado_no_facturado(self):
        """Test pedido MercadoPago entregado pero no facturado."""
        vtex = self._crear_mock_vtex(
            estado="Pendiente",
            medio_pago="MercadoPagoPro",
            seller="Carrefour Hiper"
        )
        cdp = self._crear_mock_cdp(estado="Finalizado")

        resultado = self.service.calcular_resultado_cruce(vtex, None, cdp, None)
        assert "Verificar" in resultado
        assert "no facturado" in resultado


@pytest.mark.asyncio
class TestCruzarTransacciones:
    """Tests para el metodo cruzar_transacciones (async)."""

    def setup_method(self):
        """Setup para cada test."""
        self.service = CruceService()

    def _crear_transaccion_vtex(self, numero_pedido, numero_transaccion, estado="invoiced", seller="Carrefour"):
        """Helper para crear TransaccionVtex mock."""
        mock = MagicMock(spec=TransaccionVtex)
        mock.numero_pedido = numero_pedido
        mock.numero_transaccion = numero_transaccion
        mock.fecha_hora = datetime.now(timezone.utc)
        mock.medio_pago = "Visa"
        mock.seller = seller
        mock.estado = estado
        return mock

    def _crear_transaccion_payway(self, numero_transaccion, estado="Aprobada"):
        """Helper para crear TransaccionPayway mock."""
        mock = MagicMock(spec=TransaccionPayway)
        mock.numero_transaccion = numero_transaccion
        mock.estado = estado
        mock.estado_no_cobrado.return_value = estado in ["Pre autorizada", "Vencida"]
        return mock

    def _crear_transaccion_cdp(self, numero_pedido, estado="Finalizado"):
        """Helper para crear TransaccionCDP mock."""
        mock = MagicMock(spec=TransaccionCDP)
        mock.numero_pedido = numero_pedido
        mock.estado = estado
        mock.estado_entregado.return_value = True
        return mock

    async def test_cruce_basico_vtex_payway(self):
        """Test cruce basico entre VTEX y Payway."""
        vtex = [self._crear_transaccion_vtex("1234567890123-01", "TXN-001")]
        payway = [self._crear_transaccion_payway("1234567890123-1")]

        resultado = await self.service.cruzar_transacciones(vtex, payway, [], [])

        assert len(resultado) == 1
        assert resultado[0]['numero_pedido'] == "1234567890123-01"
        assert resultado[0]['estado_vtex'] == "invoiced"
        assert resultado[0]['estado_payway'] == "Aprobada"

    async def test_cruce_vtex_cdp(self):
        """Test cruce entre VTEX y CDP."""
        vtex = [self._crear_transaccion_vtex("1234567890123-01", "TXN-001")]
        cdp = [self._crear_transaccion_cdp("1234567890123")]  # Sin sufijo

        resultado = await self.service.cruzar_transacciones(vtex, [], cdp, [])

        assert len(resultado) == 1
        assert resultado[0]['estado_cdp'] == "Finalizado"

    async def test_cruce_sin_match_payway(self):
        """Test cruce cuando no hay match con Payway."""
        vtex = [self._crear_transaccion_vtex("1234567890123-01", "TXN-001")]
        payway = [self._crear_transaccion_payway("9999999999999-1")]  # No coincide

        resultado = await self.service.cruzar_transacciones(vtex, payway, [], [])

        assert len(resultado) == 1
        assert resultado[0]['estado_payway'] == "N/A"

    async def test_cruce_lista_vacia(self):
        """Test cruce con listas vacias."""
        resultado = await self.service.cruzar_transacciones([], [], [], [])
        assert len(resultado) == 0

    async def test_cruce_multiples_transacciones(self):
        """Test cruce con multiples transacciones."""
        vtex = [
            self._crear_transaccion_vtex("1111111111111-01", "TXN-001"),
            self._crear_transaccion_vtex("2222222222222-01", "TXN-002"),
            self._crear_transaccion_vtex("3333333333333-01", "TXN-003"),
        ]
        payway = [
            self._crear_transaccion_payway("1111111111111-1"),
            self._crear_transaccion_payway("2222222222222-1"),
        ]

        resultado = await self.service.cruzar_transacciones(vtex, payway, [], [])

        assert len(resultado) == 3
        pedidos_con_payway = [r for r in resultado if r['estado_payway'] != "N/A"]
        assert len(pedidos_con_payway) == 2


@pytest.mark.asyncio
class TestGuardarTransaccionesCruce:
    """Tests para el metodo guardar_transacciones_cruce (async)."""

    def setup_method(self):
        """Setup para cada test."""
        self.service = CruceService()

    @pytest.mark.django_db(transaction=True)
    async def test_guardar_transacciones(self, cruce):
        """Test guardar transacciones cruzadas en BD."""
        transacciones = [
            {
                'numero_pedido': '1234567890123-01',
                'fecha_hora': datetime.now(timezone.utc),
                'medio_pago': 'Visa',
                'seller': 'Carrefour',
                'estado_vtex': 'invoiced',
                'estado_payway': 'Aprobada',
                'estado_payway_2': '',
                'estado_cdp': 'Finalizado',
                'estado_janis': 'N/A',
                'resultado_cruce': ''
            }
        ]

        cantidad = await self.service.guardar_transacciones_cruce(transacciones, cruce)

        assert cantidad == 1

    @pytest.mark.django_db(transaction=True)
    async def test_guardar_lista_vacia(self, cruce):
        """Test guardar lista vacia."""
        cantidad = await self.service.guardar_transacciones_cruce([], cruce)
        assert cantidad == 0

    @pytest.mark.django_db(transaction=True)
    async def test_guardar_multiples_transacciones(self, cruce):
        """Test guardar multiples transacciones."""
        transacciones = [
            {'numero_pedido': f'PEDIDO-{i}', 'estado_vtex': 'invoiced'}
            for i in range(50)
        ]

        cantidad = await self.service.guardar_transacciones_cruce(transacciones, cruce)

        assert cantidad == 50
