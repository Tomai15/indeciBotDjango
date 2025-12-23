# 🚀 Cómo Iniciar el Proyecto

## ✅ OPCIÓN 1: Comando Django (RECOMENDADO) ⭐

**La forma más "Django-native":**

```bash
python manage.py rundev_simple
```

**Qué hace:**
- ✅ Abre Django-Q Worker en ventana separada (CMD)
- ✅ Inicia servidor Django en la ventana actual
- ✅ Un solo comando
- ✅ Funciona en Windows, Linux y Mac

**Cuándo usar:**
- Desarrollo diario
- Testing
- Cuando querés simplicidad

---

## ✅ OPCIÓN 2: Script Batch (Alternativa Windows)

```bash
.\start_dev.bat
```

**Qué hace:**
- Similar a `rundev_simple`
- Abre dos ventanas CMD
- Usa scripts del sistema operativo

---

## ✅ OPCIÓN 3: Manual (Dos Terminales)

### Terminal 1: Worker
```bash
python manage.py qcluster
```

### Terminal 2: Servidor
```bash
python manage.py runserver
```

**Cuándo usar:**
- Debugging avanzado
- Querés ver logs separados

---

## ✅ OPCIÓN 4: Comando Avanzado (En desarrollo)

```bash
python manage.py rundev
```

**Características:**
- Logs combinados en una sola terminal
- Más control
- ⚠️ Puede tener issues con señales en Windows

---

## 🎯 Recomendación por Caso

| Situación | Comando |
|-----------|---------|
| **Uso diario (Windows)** | `python manage.py rundev_simple` |
| **Uso diario (Linux/Mac)** | `python manage.py rundev_simple` o `./start_dev.sh` |
| **Debugging** | Dos terminales (manual) |
| **Producción** | Supervisor/systemd (ver COMO_EJECUTAR_DJANGO_Q.md) |

---

## 📋 Checklist Antes de Iniciar

```bash
# 1. Activar virtualenv (si no está activo)
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# 2. Verificar que Django-Q está instalado
pip list | grep django-q

# 3. Verificar migraciones
python manage.py migrate

# 4. Iniciar proyecto
python manage.py rundev_simple
```

---

## ❓ FAQ

### ¿Por qué necesito dos procesos?

**Respuesta corta:** Rendimiento y UX.

Django responde requests HTTP rápido (< 1 segundo). Tus reportes tardan 15 minutos. Si ejecutas todo en un proceso:
- Cliente espera 15 minutos → Timeout
- Servidor bloqueado → Otros usuarios esperan

Con worker separado:
- Cliente recibe respuesta inmediata
- Worker procesa en background
- Servidor sigue respondiendo otros requests

### ¿Qué pasa si cierro la ventana del worker?

Las tareas nuevas se encolan pero no se procesan hasta que vuelvas a iniciar el worker.

### ¿Puedo usar solo `python manage.py runserver`?

Sí, pero las tareas **NO se ejecutarán**. Se quedarán encoladas hasta que inicies el worker.

### ¿Cómo sé si el worker está corriendo?

Verás logs como:
```
[Q] INFO Q Cluster crucebot starting.
[Q] INFO Process-1 ready for work at 1234
```

### ¿Cómo detengo todo?

- Si usas `rundev_simple`: Ctrl+C en la terminal principal, cierra manualmente la ventana del worker
- Si usas terminales separadas: Ctrl+C en cada una

---

## 🐛 Troubleshooting

### Error: "django.core.exceptions.AppRegistryNotReady"

**Solución:**
```bash
python manage.py migrate
```

### Error: "ModuleNotFoundError: No module named 'django_q'"

**Solución:**
```bash
pip install django-q2
```

### Las tareas no se ejecutan

**Verificar:**
1. ¿Está corriendo el worker? Debe haber una ventana con logs de Django-Q
2. Mirar los logs del worker, debe decir "ready for work"
3. Verificar en Django shell:
```python
from django_q.models import Task
Task.objects.last()  # Ver última tarea
```

### Worker se cierra inmediatamente

**Posibles causas:**
- Error en `settings.py` (revisar Q_CLUSTER)
- Falta migración: `python manage.py migrate django_q`

---

## 📚 Más Información

- Ver `COMO_EJECUTAR_DJANGO_Q.md` para opciones de producción
- Ver `start_dev.bat` para script alternativo
- Ver documentación oficial: https://django-q2.readthedocs.io/
