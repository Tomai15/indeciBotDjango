from django.contrib import admin

from core.models import (
    TransaccionPayway,
    ReportePayway,
    TransaccionVtex,
    ReporteVtex,
    UsuarioPayway,
    UsuarioCDP,
    UsuarioVtex, TransaccionCDP, ReporteCDP, Cruce, TransaccionCruce
)

# Register your models here.
# Payway
admin.site.register(TransaccionPayway)
admin.site.register(ReportePayway)

# VTEX
admin.site.register(TransaccionVtex)
admin.site.register(ReporteVtex)

admin.site.register(TransaccionCDP)
admin.site.register(ReporteCDP)

admin.site.register(Cruce)
admin.site.register(TransaccionCruce)

# Credenciales
admin.site.register(UsuarioPayway)
admin.site.register(UsuarioCDP)
admin.site.register(UsuarioVtex)