"""
Configuración y fixtures para pytest.
"""
import pytest
from datetime import date, datetime, timezone
from decimal import Decimal

from core.models import (
    # Usuarios/Credenciales
    UsuarioPayway,
    UsuarioCDP,
    UsuarioVtex,
    UsuarioJanis,
    # Filtros VTEX
    TipoFiltroVtex,
    ValorFiltroVtex,
    # Reportes
    ReportePayway,
    ReporteVtex,
    ReporteCDP,
    ReporteJanis,
    FiltroReporteVtex,
    # Transacciones
    TransaccionPayway,
    TransaccionVtex,
    TransaccionCDP,
    TransaccionJanis,
    # Cruces
    Cruce,
    TransaccionCruce,
)


# =============================================================================
# FIXTURES DE USUARIOS/CREDENCIALES
# =============================================================================

@pytest.fixture
def usuario_payway(db):
    """Crea un usuario de Payway para tests."""
    return UsuarioPayway.objects.create(
        usuario="test_user",
        clave="test_password"
    )


@pytest.fixture
def usuario_cdp(db):
    """Crea un usuario de CDP para tests."""
    return UsuarioCDP.objects.create(
        usuario="test_cdp_user",
        clave="test_cdp_password"
    )


@pytest.fixture
def usuario_vtex(db):
    """Crea un usuario de VTEX para tests."""
    return UsuarioVtex.objects.create(
        app_key="test_app_key",
        app_token="test_app_token",
        account_name="test_account"
    )


@pytest.fixture
def usuario_janis(db):
    """Crea un usuario de Janis para tests."""
    return UsuarioJanis.objects.create(
        api_key="test_api_key",
        api_secret="test_api_secret",
        client_code="test_client"
    )


# =============================================================================
# FIXTURES DE FILTROS VTEX
# =============================================================================

@pytest.fixture
def tipo_filtro_estado(db):
    """Crea un tipo de filtro de estado para VTEX."""
    # Usar get_or_create para evitar conflictos con datos existentes
    tipo, _ = TipoFiltroVtex.objects.get_or_create(
        codigo="test_estado",
        defaults={
            "nombre": "Estado del pedido (Test)",
            "parametro_api": "f_status",
            "activo": True
        }
    )
    return tipo


@pytest.fixture
def valor_filtro_facturado(db, tipo_filtro_estado):
    """Crea un valor de filtro 'facturado' para el tipo estado."""
    valor, _ = ValorFiltroVtex.objects.get_or_create(
        tipo_filtro=tipo_filtro_estado,
        codigo="test_invoiced",
        defaults={
            "nombre": "Facturado (Test)",
            "activo": True
        }
    )
    return valor


@pytest.fixture
def valor_filtro_cancelado(db, tipo_filtro_estado):
    """Crea un valor de filtro 'cancelado' para el tipo estado."""
    valor, _ = ValorFiltroVtex.objects.get_or_create(
        tipo_filtro=tipo_filtro_estado,
        codigo="test_canceled",
        defaults={
            "nombre": "Cancelado (Test)",
            "activo": True
        }
    )
    return valor


# =============================================================================
# FIXTURES DE REPORTES
# =============================================================================

@pytest.fixture
def fecha_inicio():
    """Fecha de inicio para tests."""
    return date(2024, 1, 1)


@pytest.fixture
def fecha_fin():
    """Fecha de fin para tests."""
    return date(2024, 1, 31)


@pytest.fixture
def reporte_payway(db, fecha_inicio, fecha_fin):
    """Crea un reporte de Payway para tests."""
    return ReportePayway.objects.create(
        estado=ReportePayway.Estado.PENDIENTE,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin
    )


@pytest.fixture
def reporte_vtex(db, fecha_inicio, fecha_fin):
    """Crea un reporte de VTEX para tests."""
    return ReporteVtex.objects.create(
        estado=ReporteVtex.Estado.PENDIENTE,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin
    )


@pytest.fixture
def reporte_cdp(db, fecha_inicio, fecha_fin):
    """Crea un reporte de CDP para tests."""
    return ReporteCDP.objects.create(
        estado=ReporteCDP.Estado.PENDIENTE,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin
    )


@pytest.fixture
def reporte_janis(db, fecha_inicio, fecha_fin):
    """Crea un reporte de Janis para tests."""
    return ReporteJanis.objects.create(
        estado=ReporteJanis.Estado.PENDIENTE,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin
    )


# =============================================================================
# FIXTURES DE TRANSACCIONES
# =============================================================================

@pytest.fixture
def fecha_hora_transaccion():
    """Fecha y hora para transacciones de test."""
    return datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)


@pytest.fixture
def transaccion_payway(db, reporte_payway, fecha_hora_transaccion):
    """Crea una transaccion de Payway para tests."""
    return TransaccionPayway.objects.create(
        numero_transaccion="TXN-001",
        fecha_hora=fecha_hora_transaccion,
        monto=Decimal("1500.50"),
        estado="Aprobada",
        tarjeta="VISA",
        reporte=reporte_payway
    )


@pytest.fixture
def transaccion_vtex(db, reporte_vtex, fecha_hora_transaccion):
    """Crea una transaccion de VTEX para tests."""
    return TransaccionVtex.objects.create(
        numero_pedido="1234567890123-01",
        numero_transaccion="TXN-VTEX-001",
        fecha_hora=fecha_hora_transaccion,
        medio_pago="Visa",
        seller="Carrefour Hiper",
        estado="invoiced",
        valor=Decimal("2500.00"),
        reporte=reporte_vtex
    )


@pytest.fixture
def transaccion_cdp(db, reporte_cdp, fecha_hora_transaccion):
    """Crea una transaccion de CDP para tests."""
    return TransaccionCDP.objects.create(
        numero_pedido="1234567890123-01",
        fecha_hora=fecha_hora_transaccion,
        numero_tienda=Decimal("101"),
        estado="Finalizado",
        reporte=reporte_cdp
    )


@pytest.fixture
def transaccion_janis(db, reporte_janis, fecha_hora_transaccion):
    """Crea una transaccion de Janis para tests."""
    return TransaccionJanis.objects.create(
        numero_pedido="1234567890123-01",
        numero_transaccion="TXN-JANIS-001",
        fecha_hora=fecha_hora_transaccion,
        medio_pago="Visa",
        seller="Carrefour",
        estado="delivered",
        reporte=reporte_janis
    )


# =============================================================================
# FIXTURES DE CRUCES
# =============================================================================

@pytest.fixture
def cruce(db, fecha_inicio, fecha_fin):
    """Crea un cruce para tests."""
    return Cruce.objects.create(
        estado=Cruce.Estado.PENDIENTE,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin
    )


@pytest.fixture
def cruce_con_reportes(db, fecha_inicio, fecha_fin, reporte_vtex, reporte_payway, reporte_cdp, reporte_janis):
    """Crea un cruce con todos los reportes asociados."""
    return Cruce.objects.create(
        estado=Cruce.Estado.PENDIENTE,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        reporte_vtex=reporte_vtex,
        reporte_payway=reporte_payway,
        reporte_cdp=reporte_cdp,
        reporte_janis=reporte_janis
    )


@pytest.fixture
def transaccion_cruce(db, cruce, fecha_hora_transaccion):
    """Crea una transaccion de cruce para tests."""
    return TransaccionCruce.objects.create(
        numero_pedido="1234567890123-01",
        fecha_hora=fecha_hora_transaccion,
        medio_pago="Visa",
        seller="Carrefour",
        estado_vtex="invoiced",
        estado_payway="Aprobada",
        estado_payway_2="",
        estado_cdp="Finalizado",
        estado_janis="delivered",
        resultado_cruce="",
        cruce=cruce
    )
