import os.path

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
import pandas as pd


# Create your models here.

class UsuarioPayway(models.Model):
    usuario = models.CharField(max_length=100)
    clave = models.CharField(max_length=100)

    def __str__(self):
        return f"Credenciales Payway - {self.usuario}"


class UsuarioCDP(models.Model):
    usuario = models.CharField(max_length=100)
    clave = models.CharField(max_length=100)

    def __str__(self):
        return f"Credenciales CDP - {self.usuario}"


class ReportePayway(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', _('Pendiente')
        PROCESANDO = 'PROCESANDO', _('Procesando')
        COMPLETADO = 'COMPLETADO', _('Completado')
        ERROR = 'ERROR', _('Error')

    estado = models.CharField(
        max_length=15,
        choices=Estado.choices,
        default=Estado.PENDIENTE
    )

    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()

    def generar_reporter_excel(self):
        ruta_final = os.path.join(settings.MEDIA_ROOT, f'reporte_{self.fecha_inicio}_to_{self.fecha_fin}.xlsx')
        transacciones = self.transacciones.all()
        transacciones_convertidas = list(map(lambda transaccion: transaccion.convertir_en_diccionario(), transacciones))
        data_frame_transacciones = pd.DataFrame(transacciones_convertidas)
        if not data_frame_transacciones.empty and 'fecha' in data_frame_transacciones.columns:
            # .dt accedde a las propiedades de fecha de la serie
            # .tz_localize(None) elimina la información de zona horaria (lo hace "naive")
            data_frame_transacciones['fecha'] = data_frame_transacciones['fecha'].dt.tz_localize(None)
        data_frame_transacciones.to_excel(ruta_final,index=False)
        return


class TransaccionPayway(models.Model):
    numero_transaccion = models.CharField(max_length=100)
    fecha_hora = models.DateTimeField()
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=100)
    tarjeta = models.CharField(max_length=100)
    reporte = models.ForeignKey(ReportePayway, on_delete=models.CASCADE, related_name='transacciones')

    def convertir_en_diccionario(self):
        return {'Transaccion': self.numero_transaccion, 'fecha': self.fecha_hora,
                'monto': self.monto, 'estado': self.estado, 'tarjeta': self.tarjeta}
