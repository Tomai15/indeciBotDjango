# CruceBotSupremo - Contexto del Proyecto

## Descripción
Sistema de reportes y cruces de transacciones para e-commerce. Permite generar reportes de diferentes plataformas (Payway, VTEX, CDP) y cruzarlos para encontrar discrepancias.

## Stack Técnico
- **Framework**: Django 4.2
- **Tareas async**: Django-Q2 (usa ORM como broker)
- **Base de datos**: SQLite
- **Web scraping**: Playwright (para Payway y CDP)
- **API**: VTEX usa API REST
- **Excel**: pandas + openpyxl

## Estructura de Servicios
- `core/services/ReportePaywayService.py` - Scraping de Payway
- `core/services/ReporteVtexService.py` - API de VTEX
- `core/services/ReporteCDPService.py` - Scraping de CDP
- `core/services/CruceService.py` - Cruce de transacciones

## Modelos Principales
- `ReportePayway`, `ReporteVtex`, `ReporteCDP` - Reportes con estado (PENDIENTE, PROCESANDO, COMPLETADO, ERROR)
- `TransaccionPayway`, `TransaccionVtex`, `TransaccionCDP` - Transacciones de cada sistema
- `Cruce` - Cruce de reportes
- `TransaccionCruce` - Resultado del cruce con campos: estado_vtex, estado_payway, estado_payway_2, estado_cdp, estado_janis
- `UsuarioPayway`, `UsuarioCDP`, `UsuarioVtex` - Credenciales

## Tareas Async (core/tasks.py)
- `generar_reporte_payway_async`
- `generar_reporte_vtex_async`
- `generar_reporte_cdp_async`
- `generar_cruce_async`

## Launcher
- `launcher.py` - Inicia Django + Django-Q, instala dependencias automáticamente
- `Iniciar CruceBotSupremo.bat` - Doble clic para ejecutar
- Django-Q se abre en ventana separada (Windows) para evitar bloqueos

## Notas Importantes
- Payway tiene transacciones dobles (-1 y -2), se guardan en columnas separadas (estado_payway y estado_payway_2)
- CDP usa numero_pedido sin el sufijo después del guión (ej: "1585717962669-01" -> "1585717962669")
- Los datos de Payway vienen con espacios al inicio, se hace .strip() al guardar
- El estado debe cambiar a PROCESANDO al inicio de cada servicio
