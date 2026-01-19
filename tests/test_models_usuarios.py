"""
Tests para modelos de usuarios/credenciales.
"""
import pytest
from core.models import UsuarioPayway, UsuarioCDP, UsuarioVtex, UsuarioJanis


class TestUsuarioPayway:
    """Tests para el modelo UsuarioPayway."""

    def test_crear_usuario_payway(self, db):
        """Test crear un usuario de Payway."""
        usuario = UsuarioPayway.objects.create(
            usuario="mi_usuario",
            clave="mi_clave_secreta"
        )
        assert usuario.id is not None
        assert usuario.usuario == "mi_usuario"
        assert usuario.clave == "mi_clave_secreta"

    def test_str_usuario_payway(self, usuario_payway):
        """Test representacion string del usuario Payway."""
        assert "Credenciales Payway" in str(usuario_payway)
        assert usuario_payway.usuario in str(usuario_payway)

    def test_multiples_usuarios_payway(self, db):
        """Test crear multiples usuarios Payway."""
        usuario1 = UsuarioPayway.objects.create(usuario="user1", clave="pass1")
        usuario2 = UsuarioPayway.objects.create(usuario="user2", clave="pass2")

        assert UsuarioPayway.objects.count() == 2
        assert usuario1.id != usuario2.id


class TestUsuarioCDP:
    """Tests para el modelo UsuarioCDP."""

    def test_crear_usuario_cdp(self, db):
        """Test crear un usuario de CDP."""
        usuario = UsuarioCDP.objects.create(
            usuario="cdp_user",
            clave="cdp_password"
        )
        assert usuario.id is not None
        assert usuario.usuario == "cdp_user"
        assert usuario.clave == "cdp_password"

    def test_str_usuario_cdp(self, usuario_cdp):
        """Test representacion string del usuario CDP."""
        assert "Credenciales CDP" in str(usuario_cdp)
        assert usuario_cdp.usuario in str(usuario_cdp)


class TestUsuarioVtex:
    """Tests para el modelo UsuarioVtex."""

    def test_crear_usuario_vtex(self, db):
        """Test crear un usuario de VTEX."""
        usuario = UsuarioVtex.objects.create(
            app_key="my_app_key",
            app_token="my_app_token",
            account_name="my_account"
        )
        assert usuario.id is not None
        assert usuario.app_key == "my_app_key"
        assert usuario.app_token == "my_app_token"
        assert usuario.account_name == "my_account"

    def test_str_usuario_vtex(self, usuario_vtex):
        """Test representacion string del usuario VTEX."""
        assert "Credenciales VTEX" in str(usuario_vtex)
        assert usuario_vtex.account_name in str(usuario_vtex)

    def test_account_name_default(self, db):
        """Test que account_name tiene valor por defecto."""
        usuario = UsuarioVtex.objects.create(
            app_key="key",
            app_token="token"
        )
        assert usuario.account_name == "carrefourar"


class TestUsuarioJanis:
    """Tests para el modelo UsuarioJanis."""

    def test_crear_usuario_janis(self, db):
        """Test crear un usuario de Janis."""
        usuario = UsuarioJanis.objects.create(
            api_key="janis_key",
            api_secret="janis_secret",
            client_code="janis_client"
        )
        assert usuario.id is not None
        assert usuario.api_key == "janis_key"
        assert usuario.api_secret == "janis_secret"
        assert usuario.client_code == "janis_client"

    def test_str_usuario_janis(self, usuario_janis):
        """Test representacion string del usuario Janis."""
        assert "Credenciales Janis" in str(usuario_janis)
        assert usuario_janis.client_code in str(usuario_janis)

    def test_meta_verbose_name(self):
        """Test que el verbose_name esta correctamente configurado."""
        assert UsuarioJanis._meta.verbose_name == "Usuario Janis"
        assert UsuarioJanis._meta.verbose_name_plural == "Usuarios Janis"
