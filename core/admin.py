from django.contrib import admin

from core.models import (
    TransaccionPayway,
    ReportePayway,
    TransaccionVtex,
    ReporteVtex,
    UsuarioPayway,
    UsuarioCDP,
    UsuarioVtex
)

# Register your models here.
# Payway
admin.site.register(TransaccionPayway)
admin.site.register(ReportePayway)

# VTEX
admin.site.register(TransaccionVtex)
admin.site.register(ReporteVtex)

# Credenciales
admin.site.register(UsuarioPayway)
admin.site.register(UsuarioCDP)
admin.site.register(UsuarioVtex)