"""
Tests para formularios de Django.
"""
import pytest
from datetime import date, timedelta
from django.core.exceptions import ValidationError

from core.forms import (
    GenerarReportePaywayForm,
    GenerarReporteVtexForm,
    GenerarReporteCDPForm,
    GenerarReporteJanisForm,
    GenerarCruceForm,
    CredencialesPaywayForm,
    CredencialesCDPForm,
    RangoFechasFormMixin,
)
from core.models import (
    UsuarioPayway, UsuarioCDP,
    ReporteVtex, ReportePayway, ReporteCDP, ReporteJanis
)


class TestGenerarReportePaywayForm:
    """Tests para GenerarReportePaywayForm."""

    def test_form_valido(self):
        """Test formulario con datos validos."""
        hoy = date.today()
        ayer = hoy - timedelta(days=1)

        form = GenerarReportePaywayForm(data={
            'fecha_inicio': ayer,
            'fecha_fin': hoy
        })

        assert form.is_valid()

    def test_fecha_inicio_posterior_a_fin(self):
        """Test que fecha_inicio no puede ser posterior a fecha_fin."""
        hoy = date.today()
        ayer = hoy - timedelta(days=1)

        form = GenerarReportePaywayForm(data={
            'fecha_inicio': hoy,
            'fecha_fin': ayer  # Fin antes que inicio
        })

        assert not form.is_valid()
        assert 'La fecha de inicio no puede ser posterior' in str(form.errors)

    def test_fecha_inicio_futura(self):
        """Test que fecha_inicio no puede ser futura."""
        manana = date.today() + timedelta(days=1)
        pasado = date.today() + timedelta(days=2)

        form = GenerarReportePaywayForm(data={
            'fecha_inicio': manana,
            'fecha_fin': pasado
        })

        assert not form.is_valid()
        assert 'fecha futura' in str(form.errors).lower()

    def test_fecha_fin_futura(self):
        """Test que fecha_fin no puede ser futura."""
        hoy = date.today()
        manana = hoy + timedelta(days=1)

        form = GenerarReportePaywayForm(data={
            'fecha_inicio': hoy,
            'fecha_fin': manana
        })

        assert not form.is_valid()
        assert 'fecha futura' in str(form.errors).lower()

    def test_campos_requeridos(self):
        """Test que los campos son requeridos."""
        form = GenerarReportePaywayForm(data={})

        assert not form.is_valid()
        assert 'fecha_inicio' in form.errors
        assert 'fecha_fin' in form.errors

    def test_mismo_dia_valido(self):
        """Test que fecha_inicio == fecha_fin es valido."""
        hoy = date.today()

        form = GenerarReportePaywayForm(data={
            'fecha_inicio': hoy,
            'fecha_fin': hoy
        })

        assert form.is_valid()


class TestGenerarReporteVtexForm:
    """Tests para GenerarReporteVtexForm."""

    def test_form_valido_sin_filtros(self, db):
        """Test formulario valido sin filtros de estado."""
        hoy = date.today()
        ayer = hoy - timedelta(days=1)

        form = GenerarReporteVtexForm(data={
            'fecha_inicio': ayer,
            'fecha_fin': hoy,
            'filtros_estado': []  # Sin filtros
        })

        assert form.is_valid()

    def test_filtros_estado_opcional(self, db):
        """Test que filtros_estado no es requerido."""
        hoy = date.today()
        ayer = hoy - timedelta(days=1)

        form = GenerarReporteVtexForm(data={
            'fecha_inicio': ayer,
            'fecha_fin': hoy
            # Sin filtros_estado
        })

        assert form.is_valid()


class TestGenerarReporteCDPForm:
    """Tests para GenerarReporteCDPForm."""

    def test_form_valido(self):
        """Test formulario con datos validos."""
        hoy = date.today()
        ayer = hoy - timedelta(days=1)

        form = GenerarReporteCDPForm(data={
            'fecha_inicio': ayer,
            'fecha_fin': hoy
        })

        assert form.is_valid()

    def test_hereda_validacion_fechas(self):
        """Test que hereda validacion de RangoFechasFormMixin."""
        hoy = date.today()
        ayer = hoy - timedelta(days=1)

        form = GenerarReporteCDPForm(data={
            'fecha_inicio': hoy,
            'fecha_fin': ayer  # Invertidas
        })

        assert not form.is_valid()


class TestGenerarReporteJanisForm:
    """Tests para GenerarReporteJanisForm."""

    def test_form_valido(self):
        """Test formulario con datos validos."""
        hoy = date.today()
        ayer = hoy - timedelta(days=1)

        form = GenerarReporteJanisForm(data={
            'fecha_inicio': ayer,
            'fecha_fin': hoy
        })

        assert form.is_valid()


class TestGenerarCruceForm:
    """Tests para GenerarCruceForm."""

    @pytest.fixture
    def reportes_completados(self, db):
        """Crea reportes completados para tests."""
        hoy = date.today()
        ayer = hoy - timedelta(days=1)

        vtex = ReporteVtex.objects.create(
            fecha_inicio=ayer, fecha_fin=hoy, estado='COMPLETADO'
        )
        payway = ReportePayway.objects.create(
            fecha_inicio=ayer, fecha_fin=hoy, estado='COMPLETADO'
        )
        cdp = ReporteCDP.objects.create(
            fecha_inicio=ayer, fecha_fin=hoy, estado='COMPLETADO'
        )
        janis = ReporteJanis.objects.create(
            fecha_inicio=ayer, fecha_fin=hoy, estado='COMPLETADO'
        )

        return {'vtex': vtex, 'payway': payway, 'cdp': cdp, 'janis': janis}

    def test_form_valido_dos_reportes(self, reportes_completados):
        """Test formulario valido con 2 reportes."""
        form = GenerarCruceForm(data={
            'reporte_vtex': reportes_completados['vtex'].id,
            'reporte_payway': reportes_completados['payway'].id
        })

        assert form.is_valid()

    def test_form_valido_tres_reportes(self, reportes_completados):
        """Test formulario valido con 3 reportes."""
        form = GenerarCruceForm(data={
            'reporte_vtex': reportes_completados['vtex'].id,
            'reporte_payway': reportes_completados['payway'].id,
            'reporte_cdp': reportes_completados['cdp'].id
        })

        assert form.is_valid()

    def test_form_valido_cuatro_reportes(self, reportes_completados):
        """Test formulario valido con 4 reportes."""
        form = GenerarCruceForm(data={
            'reporte_vtex': reportes_completados['vtex'].id,
            'reporte_payway': reportes_completados['payway'].id,
            'reporte_cdp': reportes_completados['cdp'].id,
            'reporte_janis': reportes_completados['janis'].id
        })

        assert form.is_valid()

    def test_form_invalido_un_reporte(self, reportes_completados):
        """Test que falla con solo 1 reporte."""
        form = GenerarCruceForm(data={
            'reporte_vtex': reportes_completados['vtex'].id
        })

        assert not form.is_valid()
        assert 'al menos 2 reportes' in str(form.errors).lower()

    def test_form_invalido_sin_reportes(self, db):
        """Test que falla sin reportes."""
        form = GenerarCruceForm(data={})

        assert not form.is_valid()
        assert 'al menos 2 reportes' in str(form.errors).lower()

    def test_solo_muestra_reportes_completados(self, db):
        """Test que solo muestra reportes con estado COMPLETADO."""
        hoy = date.today()

        # Crear reportes con diferentes estados
        ReporteVtex.objects.create(
            fecha_inicio=hoy, fecha_fin=hoy, estado='PENDIENTE'
        )
        ReporteVtex.objects.create(
            fecha_inicio=hoy, fecha_fin=hoy, estado='PROCESANDO'
        )
        completado = ReporteVtex.objects.create(
            fecha_inicio=hoy, fecha_fin=hoy, estado='COMPLETADO'
        )

        form = GenerarCruceForm()

        queryset = form.fields['reporte_vtex'].queryset
        assert completado in queryset
        assert queryset.count() == 1  # Solo el completado


class TestCredencialesPaywayForm:
    """Tests para CredencialesPaywayForm."""

    def test_form_valido(self, db):
        """Test formulario con datos validos."""
        form = CredencialesPaywayForm(data={
            'usuario': 'mi_usuario',
            'clave': 'mi_clave'
        })

        assert form.is_valid()

    def test_crear_usuario(self, db):
        """Test crear usuario desde formulario."""
        form = CredencialesPaywayForm(data={
            'usuario': 'nuevo_usuario',
            'clave': 'nueva_clave'
        })

        assert form.is_valid()
        usuario = form.save()

        assert usuario.id is not None
        assert usuario.usuario == 'nuevo_usuario'

    def test_campos_requeridos(self, db):
        """Test que los campos son requeridos."""
        form = CredencialesPaywayForm(data={})

        assert not form.is_valid()
        assert 'usuario' in form.errors
        assert 'clave' in form.errors

    def test_placeholder_payway(self, db):
        """Test que el placeholder menciona Payway."""
        form = CredencialesPaywayForm()

        assert 'Payway' in form.fields['usuario'].widget.attrs.get('placeholder', '')


class TestCredencialesCDPForm:
    """Tests para CredencialesCDPForm."""

    def test_form_valido(self, db):
        """Test formulario con datos validos."""
        form = CredencialesCDPForm(data={
            'usuario': 'mi_usuario_cdp',
            'clave': 'mi_clave_cdp'
        })

        assert form.is_valid()

    def test_placeholder_cdp(self, db):
        """Test que el placeholder menciona CDP."""
        form = CredencialesCDPForm()

        assert 'CDP' in form.fields['usuario'].widget.attrs.get('placeholder', '')

    def test_crear_usuario_cdp(self, db):
        """Test crear usuario CDP desde formulario."""
        form = CredencialesCDPForm(data={
            'usuario': 'usuario_cdp',
            'clave': 'clave_cdp'
        })

        assert form.is_valid()
        usuario = form.save()

        assert isinstance(usuario, UsuarioCDP)
        assert usuario.usuario == 'usuario_cdp'
