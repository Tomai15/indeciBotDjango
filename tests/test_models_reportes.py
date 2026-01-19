"""
Tests para modelos de reportes y filtros VTEX.
"""
import pytest
from datetime import date
from django.core.exceptions import ValidationError

from core.models import (
    ReportePayway,
    ReporteVtex,
    ReporteCDP,
    ReporteJanis,
    TipoFiltroVtex,
    ValorFiltroVtex,
    FiltroReporteVtex,
)


class TestTipoFiltroVtex:
    """Tests para el modelo TipoFiltroVtex."""

    def test_crear_tipo_filtro(self, db):
        """Test crear un tipo de filtro VTEX."""
        import uuid
        codigo_unico = f"test_tipo_{uuid.uuid4().hex[:8]}"
        tipo = TipoFiltroVtex.objects.create(
            codigo=codigo_unico,
            nombre="Estado del pedido",
            parametro_api="f_status",
            activo=True
        )
        assert tipo.id is not None
        assert tipo.codigo == codigo_unico
        assert tipo.parametro_api == "f_status"

    def test_str_tipo_filtro(self, tipo_filtro_estado):
        """Test representacion string del tipo filtro."""
        assert "Estado del pedido" in str(tipo_filtro_estado)

    def test_codigo_unico(self, db):
        """Test que el codigo del tipo filtro es unico."""
        import uuid
        from django.db import IntegrityError
        codigo_unico = f"test_unico_{uuid.uuid4().hex[:8]}"

        TipoFiltroVtex.objects.create(
            codigo=codigo_unico,
            nombre="Tipo 1",
            parametro_api="f_tipo1"
        )

        with pytest.raises(IntegrityError):
            TipoFiltroVtex.objects.create(
                codigo=codigo_unico,  # mismo codigo
                nombre="Tipo 2",
                parametro_api="f_tipo2"
            )

    def test_filtro_inactivo(self, db):
        """Test crear filtro inactivo."""
        import uuid
        tipo = TipoFiltroVtex.objects.create(
            codigo=f"test_inactivo_{uuid.uuid4().hex[:8]}",
            nombre="Metodo de pago",
            parametro_api="f_paymentNames",
            activo=False
        )
        assert tipo.activo is False


class TestValorFiltroVtex:
    """Tests para el modelo ValorFiltroVtex."""

    def test_crear_valor_filtro(self, tipo_filtro_estado, db):
        """Test crear un valor de filtro."""
        valor = ValorFiltroVtex.objects.create(
            tipo_filtro=tipo_filtro_estado,
            codigo="invoiced",
            nombre="Facturado",
            activo=True
        )
        assert valor.id is not None
        assert valor.tipo_filtro == tipo_filtro_estado

    def test_str_valor_filtro(self, valor_filtro_facturado):
        """Test representacion string del valor filtro."""
        # El formato es "TipoFiltro.nombre: ValorFiltro.nombre"
        assert "Estado del pedido" in str(valor_filtro_facturado)
        assert "Facturado" in str(valor_filtro_facturado)

    def test_unique_together(self, tipo_filtro_estado, valor_filtro_facturado, db):
        """Test que no se puede duplicar tipo_filtro + codigo."""
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            ValorFiltroVtex.objects.create(
                tipo_filtro=tipo_filtro_estado,
                codigo="test_invoiced",  # mismo codigo para mismo tipo (del fixture)
                nombre="Otro nombre"
            )

    def test_mismo_codigo_diferente_tipo(self, db):
        """Test que el mismo codigo puede existir en diferentes tipos."""
        import uuid
        suffix = uuid.uuid4().hex[:8]
        tipo1 = TipoFiltroVtex.objects.create(
            codigo=f"tipo1_{suffix}", nombre="Tipo 1", parametro_api="f_tipo1"
        )
        tipo2 = TipoFiltroVtex.objects.create(
            codigo=f"tipo2_{suffix}", nombre="Tipo 2", parametro_api="f_tipo2"
        )

        valor1 = ValorFiltroVtex.objects.create(
            tipo_filtro=tipo1, codigo="valor_comun", nombre="Valor en Tipo 1"
        )
        valor2 = ValorFiltroVtex.objects.create(
            tipo_filtro=tipo2, codigo="valor_comun", nombre="Valor en Tipo 2"
        )

        assert valor1.codigo == valor2.codigo
        assert valor1.tipo_filtro != valor2.tipo_filtro


class TestReportePayway:
    """Tests para el modelo ReportePayway."""

    def test_crear_reporte_payway(self, db):
        """Test crear un reporte de Payway."""
        reporte = ReportePayway.objects.create(
            fecha_inicio=date(2024, 1, 1),
            fecha_fin=date(2024, 1, 31)
        )
        assert reporte.id is not None
        assert reporte.estado == ReportePayway.Estado.PENDIENTE

    def test_estados_reporte(self, reporte_payway):
        """Test cambiar estados del reporte."""
        assert reporte_payway.estado == ReportePayway.Estado.PENDIENTE

        reporte_payway.estado = ReportePayway.Estado.PROCESANDO
        reporte_payway.save()
        assert reporte_payway.estado == "PROCESANDO"

        reporte_payway.estado = ReportePayway.Estado.COMPLETADO
        reporte_payway.save()
        assert reporte_payway.estado == "COMPLETADO"

        reporte_payway.estado = ReportePayway.Estado.ERROR
        reporte_payway.save()
        assert reporte_payway.estado == "ERROR"

    def test_choices_estado(self):
        """Test que los choices de estado estan definidos."""
        estados = [choice[0] for choice in ReportePayway.Estado.choices]
        assert "PENDIENTE" in estados
        assert "PROCESANDO" in estados
        assert "COMPLETADO" in estados
        assert "ERROR" in estados


class TestReporteVtex:
    """Tests para el modelo ReporteVtex."""

    def test_crear_reporte_vtex(self, db):
        """Test crear un reporte de VTEX."""
        reporte = ReporteVtex.objects.create(
            fecha_inicio=date(2024, 1, 1),
            fecha_fin=date(2024, 1, 31)
        )
        assert reporte.id is not None
        assert reporte.estado == ReporteVtex.Estado.PENDIENTE

    def test_str_reporte_vtex(self, reporte_vtex):
        """Test representacion string del reporte VTEX."""
        assert "Reporte VTEX" in str(reporte_vtex)
        assert str(reporte_vtex.id) in str(reporte_vtex)

    def test_filtros_json_legacy(self, db):
        """Test campo filtros JSON legacy."""
        reporte = ReporteVtex.objects.create(
            fecha_inicio=date(2024, 1, 1),
            fecha_fin=date(2024, 1, 31),
            filtros={"estado": ["invoiced", "canceled"]}
        )
        assert reporte.filtros == {"estado": ["invoiced", "canceled"]}

    def test_obtener_filtros_para_api(self, reporte_vtex, tipo_filtro_estado, valor_filtro_facturado, valor_filtro_cancelado, db):
        """Test obtener filtros formateados para la API."""
        # Agregar filtros al reporte
        FiltroReporteVtex.objects.create(
            reporte=reporte_vtex,
            tipo_filtro=tipo_filtro_estado,
            valor_filtro=valor_filtro_facturado
        )
        FiltroReporteVtex.objects.create(
            reporte=reporte_vtex,
            tipo_filtro=tipo_filtro_estado,
            valor_filtro=valor_filtro_cancelado
        )

        filtros_api = reporte_vtex.obtener_filtros_para_api()

        assert "f_status" in filtros_api
        # Los codigos de los fixtures son test_invoiced y test_canceled
        assert "test_invoiced" in filtros_api["f_status"]
        assert "test_canceled" in filtros_api["f_status"]

    def test_obtener_filtros_por_tipo(self, reporte_vtex, tipo_filtro_estado, valor_filtro_facturado, db):
        """Test obtener valores de filtro por tipo."""
        FiltroReporteVtex.objects.create(
            reporte=reporte_vtex,
            tipo_filtro=tipo_filtro_estado,
            valor_filtro=valor_filtro_facturado
        )

        # El codigo del tipo filtro en el fixture es "test_estado"
        valores = reporte_vtex.obtener_filtros_por_tipo("test_estado")
        assert valor_filtro_facturado in valores


class TestFiltroReporteVtex:
    """Tests para el modelo FiltroReporteVtex."""

    def test_crear_filtro_reporte(self, reporte_vtex, tipo_filtro_estado, valor_filtro_facturado, db):
        """Test crear un filtro de reporte."""
        filtro = FiltroReporteVtex.objects.create(
            reporte=reporte_vtex,
            tipo_filtro=tipo_filtro_estado,
            valor_filtro=valor_filtro_facturado
        )
        assert filtro.id is not None
        assert filtro.reporte == reporte_vtex

    def test_str_filtro_reporte(self, reporte_vtex, tipo_filtro_estado, valor_filtro_facturado, db):
        """Test representacion string del filtro reporte."""
        filtro = FiltroReporteVtex.objects.create(
            reporte=reporte_vtex,
            tipo_filtro=tipo_filtro_estado,
            valor_filtro=valor_filtro_facturado
        )
        assert f"Reporte #{reporte_vtex.id}" in str(filtro)

    def test_clean_valor_tipo_incorrecto(self, reporte_vtex, db):
        """Test que clean valida que el valor pertenezca al tipo correcto."""
        import uuid
        suffix = uuid.uuid4().hex[:8]
        tipo1 = TipoFiltroVtex.objects.create(
            codigo=f"tipo1_clean_{suffix}", nombre="Tipo 1", parametro_api="f_tipo1"
        )
        tipo2 = TipoFiltroVtex.objects.create(
            codigo=f"tipo2_clean_{suffix}", nombre="Tipo 2", parametro_api="f_tipo2"
        )
        valor_tipo2 = ValorFiltroVtex.objects.create(
            tipo_filtro=tipo2, codigo="valor2", nombre="Valor de Tipo 2"
        )

        filtro = FiltroReporteVtex(
            reporte=reporte_vtex,
            tipo_filtro=tipo1,  # tipo diferente
            valor_filtro=valor_tipo2  # valor de otro tipo
        )

        with pytest.raises(ValidationError):
            filtro.clean()

    def test_unique_together_filtro(self, reporte_vtex, tipo_filtro_estado, valor_filtro_facturado, db):
        """Test que no se puede duplicar reporte + tipo + valor."""
        from django.db import IntegrityError

        FiltroReporteVtex.objects.create(
            reporte=reporte_vtex,
            tipo_filtro=tipo_filtro_estado,
            valor_filtro=valor_filtro_facturado
        )

        with pytest.raises(IntegrityError):
            FiltroReporteVtex.objects.create(
                reporte=reporte_vtex,
                tipo_filtro=tipo_filtro_estado,
                valor_filtro=valor_filtro_facturado  # duplicado
            )


class TestReporteCDP:
    """Tests para el modelo ReporteCDP."""

    def test_crear_reporte_cdp(self, db):
        """Test crear un reporte de CDP."""
        reporte = ReporteCDP.objects.create(
            fecha_inicio=date(2024, 1, 1),
            fecha_fin=date(2024, 1, 31)
        )
        assert reporte.id is not None
        assert reporte.estado == ReporteCDP.Estado.PENDIENTE

    def test_estados_reporte_cdp(self, reporte_cdp):
        """Test estados del reporte CDP."""
        assert reporte_cdp.estado == ReporteCDP.Estado.PENDIENTE


class TestReporteJanis:
    """Tests para el modelo ReporteJanis."""

    def test_crear_reporte_janis(self, db):
        """Test crear un reporte de Janis."""
        reporte = ReporteJanis.objects.create(
            fecha_inicio=date(2024, 1, 1),
            fecha_fin=date(2024, 1, 31)
        )
        assert reporte.id is not None
        assert reporte.estado == ReporteJanis.Estado.PENDIENTE
