"""
Tests para las vistas de Django.
"""
import pytest
from datetime import date, timedelta
from django.test import Client
from django.urls import reverse
from unittest.mock import patch, MagicMock

from core.models import (
    ReportePayway, ReporteVtex, ReporteCDP, ReporteJanis, Cruce,
    TransaccionPayway, TransaccionVtex, TransaccionCDP, TransaccionJanis,
    TransaccionCruce, UsuarioPayway, UsuarioCDP
)


@pytest.fixture
def client():
    """Cliente de Django para tests."""
    return Client()


class TestHomeView:
    """Tests para la vista home."""

    def test_home_status_code(self, client, db):
        """Test que home retorna 200."""
        response = client.get(reverse('home'))
        assert response.status_code == 200

    def test_home_template(self, client, db):
        """Test que home usa el template correcto."""
        response = client.get(reverse('home'))
        assert 'core/home.html' in [t.name for t in response.templates]


class TestReportePaywayViews:
    """Tests para vistas de Payway."""

    def test_lista_reportes_vacia(self, client, db):
        """Test lista de reportes vacia."""
        response = client.get(reverse('lista_reportes'))
        assert response.status_code == 200

    def test_lista_reportes_con_datos(self, client, reporte_payway):
        """Test lista de reportes con datos."""
        response = client.get(reverse('lista_reportes'))
        assert response.status_code == 200
        assert reporte_payway in response.context['object_list']

    def test_detalle_reporte(self, client, reporte_payway):
        """Test detalle de reporte."""
        response = client.get(
            reverse('detalle_reporte', kwargs={'pk': reporte_payway.pk})
        )
        assert response.status_code == 200
        assert response.context['reporte'] == reporte_payway

    def test_detalle_reporte_no_existe(self, client, db):
        """Test detalle de reporte inexistente."""
        response = client.get(
            reverse('detalle_reporte', kwargs={'pk': 99999})
        )
        assert response.status_code == 404

    def test_generar_reporte_get(self, client, db):
        """Test formulario de generar reporte (GET)."""
        response = client.get(reverse('generar_reporte'))
        assert response.status_code == 200
        assert 'form' in response.context

    def test_generar_reporte_sin_credenciales(self, client, db):
        """Test generar reporte sin credenciales configuradas."""
        hoy = date.today()
        ayer = hoy - timedelta(days=1)

        response = client.post(reverse('generar_reporte'), {
            'fecha_inicio': ayer.strftime('%Y-%m-%d'),
            'fecha_fin': hoy.strftime('%Y-%m-%d')
        })

        # Debe mostrar error de credenciales
        assert response.status_code == 200
        assert 'credenciales' in response.content.decode().lower()

    @patch('core.views.async_task')
    def test_generar_reporte_con_credenciales(self, mock_async_task, client, usuario_payway):
        """Test generar reporte con credenciales configuradas."""
        mock_async_task.return_value = 'task-123'

        hoy = date.today()
        ayer = hoy - timedelta(days=1)

        response = client.post(reverse('generar_reporte'), {
            'fecha_inicio': ayer.strftime('%Y-%m-%d'),
            'fecha_fin': hoy.strftime('%Y-%m-%d')
        })

        # Debe redirigir a lista de reportes
        assert response.status_code == 302
        assert ReportePayway.objects.count() == 1
        mock_async_task.assert_called_once()

    def test_eliminar_reporte(self, client, reporte_payway):
        """Test eliminar reporte."""
        pk = reporte_payway.pk
        response = client.post(
            reverse('eliminar_reporte_payway', kwargs={'pk': pk})
        )
        assert response.status_code == 302
        assert not ReportePayway.objects.filter(pk=pk).exists()


class TestReporteVtexViews:
    """Tests para vistas de VTEX."""

    def test_lista_reportes_vtex(self, client, db):
        """Test lista de reportes VTEX."""
        response = client.get(reverse('lista_reportes_vtex'))
        assert response.status_code == 200

    def test_detalle_reporte_vtex(self, client, reporte_vtex):
        """Test detalle de reporte VTEX."""
        response = client.get(
            reverse('detalle_reporte_vtex', kwargs={'pk': reporte_vtex.pk})
        )
        assert response.status_code == 200

    def test_generar_reporte_vtex_get(self, client, db):
        """Test formulario de generar reporte VTEX (GET)."""
        response = client.get(reverse('generar_reporte_vtex'))
        assert response.status_code == 200
        assert 'form' in response.context


class TestReporteCDPViews:
    """Tests para vistas de CDP."""

    def test_lista_reportes_cdp(self, client, db):
        """Test lista de reportes CDP."""
        response = client.get(reverse('lista_reportes_cdp'))
        assert response.status_code == 200

    def test_detalle_reporte_cdp(self, client, reporte_cdp):
        """Test detalle de reporte CDP."""
        response = client.get(
            reverse('detalle_reporte_cdp', kwargs={'pk': reporte_cdp.pk})
        )
        assert response.status_code == 200

    def test_generar_reporte_cdp_get(self, client, db):
        """Test formulario de generar reporte CDP (GET)."""
        response = client.get(reverse('generar_reporte_cdp'))
        assert response.status_code == 200


class TestReporteJanisViews:
    """Tests para vistas de Janis."""

    def test_lista_reportes_janis(self, client, db):
        """Test lista de reportes Janis."""
        response = client.get(reverse('lista_reportes_janis'))
        assert response.status_code == 200

    def test_detalle_reporte_janis(self, client, reporte_janis):
        """Test detalle de reporte Janis."""
        response = client.get(
            reverse('detalle_reporte_janis', kwargs={'pk': reporte_janis.pk})
        )
        assert response.status_code == 200


class TestCruceViews:
    """Tests para vistas de Cruces."""

    def test_lista_cruces(self, client, db):
        """Test lista de cruces."""
        response = client.get(reverse('lista_cruces'))
        assert response.status_code == 200

    def test_lista_cruces_con_datos(self, client, cruce):
        """Test lista de cruces con datos."""
        response = client.get(reverse('lista_cruces'))
        assert response.status_code == 200
        assert cruce in response.context['object_list']

    def test_detalle_cruce(self, client, cruce):
        """Test detalle de cruce."""
        response = client.get(
            reverse('detalle_cruce', kwargs={'pk': cruce.pk})
        )
        assert response.status_code == 200

    def test_generar_cruce_get(self, client, db):
        """Test formulario de generar cruce (GET)."""
        response = client.get(reverse('generar_cruce'))
        assert response.status_code == 200
        assert 'form' in response.context

    def test_generar_cruce_sin_reportes(self, client, db):
        """Test generar cruce sin seleccionar reportes suficientes."""
        response = client.post(reverse('generar_cruce'), {})
        assert response.status_code == 200
        # Debe mostrar error de formulario

    @patch('core.views.async_task')
    def test_generar_cruce_con_reportes(self, mock_async_task, client, db):
        """Test generar cruce con reportes validos."""
        mock_async_task.return_value = 'task-456'

        hoy = date.today()
        # Crear reportes completados
        vtex = ReporteVtex.objects.create(
            fecha_inicio=hoy, fecha_fin=hoy, estado='COMPLETADO'
        )
        payway = ReportePayway.objects.create(
            fecha_inicio=hoy, fecha_fin=hoy, estado='COMPLETADO'
        )

        response = client.post(reverse('generar_cruce'), {
            'reporte_vtex': vtex.id,
            'reporte_payway': payway.id
        })

        # Debe redirigir
        assert response.status_code == 302
        assert Cruce.objects.count() == 1
        mock_async_task.assert_called_once()

    def test_eliminar_cruce(self, client, cruce):
        """Test eliminar cruce."""
        pk = cruce.pk
        response = client.post(
            reverse('eliminar_cruce', kwargs={'pk': pk})
        )
        assert response.status_code == 302
        assert not Cruce.objects.filter(pk=pk).exists()


class TestAjustesView:
    """Tests para la vista de ajustes."""

    def test_ajustes_get(self, client, db):
        """Test vista de ajustes (GET)."""
        response = client.get(reverse('ajustes'))
        assert response.status_code == 200

    def test_ajustes_muestra_formularios(self, client, db):
        """Test que ajustes muestra formularios de credenciales."""
        response = client.get(reverse('ajustes'))
        assert 'form_payway' in response.context
        assert 'form_cdp' in response.context


class TestPaginacion:
    """Tests para verificar paginacion."""

    def test_paginacion_reportes_payway(self, client, db):
        """Test paginacion de reportes Payway."""
        # Crear 60 reportes (mas que paginate_by=50)
        hoy = date.today()
        for i in range(60):
            ReportePayway.objects.create(
                fecha_inicio=hoy, fecha_fin=hoy, estado='COMPLETADO'
            )

        response = client.get(reverse('lista_reportes'))
        assert response.status_code == 200
        assert response.context['is_paginated'] is True
        assert len(response.context['object_list']) == 50

    def test_paginacion_segunda_pagina(self, client, db):
        """Test acceder a segunda pagina."""
        hoy = date.today()
        for i in range(60):
            ReportePayway.objects.create(
                fecha_inicio=hoy, fecha_fin=hoy, estado='COMPLETADO'
            )

        response = client.get(reverse('lista_reportes') + '?page=2')
        assert response.status_code == 200
        assert len(response.context['object_list']) == 10  # 60 - 50


class TestRetryViews:
    """Tests para vistas de reintentar reportes."""

    @patch('core.views.async_task')
    def test_reintentar_reporte_payway(self, mock_async_task, client, db, usuario_payway):
        """Test reintentar reporte Payway con error."""
        mock_async_task.return_value = 'task-789'

        hoy = date.today()
        reporte = ReportePayway.objects.create(
            fecha_inicio=hoy, fecha_fin=hoy, estado='ERROR'
        )

        response = client.post(
            reverse('reintentar_reporte_payway', kwargs={'pk': reporte.pk})
        )

        assert response.status_code == 302
        reporte.refresh_from_db()
        assert reporte.estado == 'PENDIENTE'
        mock_async_task.assert_called_once()

    @patch('core.views.async_task')
    def test_reintentar_reporte_vtex(self, mock_async_task, client, db):
        """Test reintentar reporte VTEX con error."""
        mock_async_task.return_value = 'task-789'

        hoy = date.today()
        reporte = ReporteVtex.objects.create(
            fecha_inicio=hoy, fecha_fin=hoy, estado='ERROR'
        )

        response = client.post(
            reverse('reintentar_reporte_vtex', kwargs={'pk': reporte.pk})
        )

        assert response.status_code == 302

    @patch('core.views.async_task')
    def test_reintentar_cruce(self, mock_async_task, client, db):
        """Test reintentar cruce con error."""
        mock_async_task.return_value = 'task-999'

        hoy = date.today()
        # Crear reportes completados
        vtex = ReporteVtex.objects.create(
            fecha_inicio=hoy, fecha_fin=hoy, estado='COMPLETADO'
        )
        payway = ReportePayway.objects.create(
            fecha_inicio=hoy, fecha_fin=hoy, estado='COMPLETADO'
        )

        cruce = Cruce.objects.create(
            fecha_inicio=hoy, fecha_fin=hoy, estado='ERROR',
            reporte_vtex=vtex, reporte_payway=payway
        )

        response = client.post(
            reverse('reintentar_cruce', kwargs={'pk': cruce.pk})
        )

        assert response.status_code == 302
