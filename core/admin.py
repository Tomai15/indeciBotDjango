from django.contrib import admin

from core.models import TransaccionPayway, ReportePayway, UsuarioPayway, UsuarioCDP

# Register your models here.
admin.site.register(TransaccionPayway)
admin.site.register(ReportePayway)
admin.site.register(UsuarioPayway)
admin.site.register(UsuarioCDP)