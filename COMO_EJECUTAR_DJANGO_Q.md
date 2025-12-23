# ¿Cómo Ejecutar Django-Q?

## 🤔 ¿Por qué necesito un proceso separado?

**Respuesta corta:** Seguridad, escalabilidad y rendimiento.

**Explicación técnica:**

Django (servidor web) está diseñado para **responder requests HTTP rápido**:
```
Cliente → Request → Django → Response (< 1 segundo)
```

Si ejecutas tareas largas (15 minutos) **dentro del request**:
```
Cliente → Request → Django (procesando 15 min...) → Timeout ❌
```

**Problema:**
- El cliente espera 15 minutos (mala UX)
- El worker del servidor está bloqueado
- Si otro usuario hace request, debe esperar
- Gunicorn/uWSGI tiene timeout → falla

**Solución:** Procesos separados
```
Cliente → Request → Django → Response "Encolado ✓" (1 segundo)
                          ↓
                    Worker procesa en background (15 min)
```

---

## ✅ Opciones para Ejecutar

### OPCIÓN 1: Modo Sync (Solo Desarrollo) ⭐ **YA CONFIGURADO**

```python
# settings.py
Q_CLUSTER = {
    ...
    'sync': True  # ← Ejecuta tareas inmediatamente sin worker
}
```

**Cómo usar:**
```bash
# Solo necesitas esto:
python manage.py runserver
```

**Ventajas:**
- ✅ Simple (no necesitas worker)
- ✅ Bueno para desarrollo/testing

**Desventajas:**
- ❌ NO es asíncrono real (bloquea el request)
- ❌ El usuario espera hasta que termine
- ❌ NO usar en producción

---

### OPCIÓN 2: Script de inicio (Desarrollo) ⭐ **RECOMENDADO DESARROLLO**

```bash
# Windows
.\start_dev.bat

# Linux/Mac
chmod +x start_dev.sh
./start_dev.sh
```

**Qué hace:**
1. Activa virtualenv
2. Abre Django-Q worker en ventana separada
3. Inicia servidor Django

**Ventajas:**
- ✅ Asíncrono real
- ✅ Un solo comando
- ✅ Fácil de usar

**Desventajas:**
- ⚠️ Solo para desarrollo local

---

### OPCIÓN 3: Dos terminales (Manual)

**Terminal 1: Worker**
```bash
cd C:\Users\tomas\PycharmProjects\CruceBotSupremo
.venv\Scripts\activate
python manage.py qcluster
```

**Terminal 2: Servidor**
```bash
cd C:\Users\tomas\PycharmProjects\CruceBotSupremo
.venv\Scripts\activate
python manage.py runserver
```

**Ventajas:**
- ✅ Control total
- ✅ Ves logs separados

**Desventajas:**
- ❌ Dos terminales abiertas

---

### OPCIÓN 4: Supervisor (Producción Linux) ⭐ **PRODUCCIÓN**

```ini
# /etc/supervisor/conf.d/crucebot.conf
[program:crucebot_web]
command=/path/to/venv/bin/gunicorn CruceBotSupremo.wsgi:application
directory=/path/to/project
user=www-data
autostart=true
autorestart=true

[program:crucebot_worker]
command=/path/to/venv/bin/python manage.py qcluster
directory=/path/to/project
user=www-data
autostart=true
autorestart=true
```

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start all
```

**Ventajas:**
- ✅ Inicia automáticamente al bootear servidor
- ✅ Reinicia automáticamente si crashea
- ✅ Logs centralizados

---

### OPCIÓN 5: systemd (Producción Linux)

```ini
# /etc/systemd/system/crucebot-web.service
[Unit]
Description=CruceBotSupremo Web
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/project
ExecStart=/path/to/venv/bin/gunicorn CruceBotSupremo.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/crucebot-worker.service
[Unit]
Description=CruceBotSupremo Worker
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/project
ExecStart=/path/to/venv/bin/python manage.py qcluster
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable crucebot-web crucebot-worker
sudo systemctl start crucebot-web crucebot-worker
```

---

### OPCIÓN 6: Docker Compose (Desarrollo + Producción) ⭐ **MÁS PROFESIONAL**

```yaml
# docker-compose.yml
version: '3.8'

services:
  web:
    build: .
    command: gunicorn CruceBotSupremo.wsgi:application --bind 0.0.0.0:8000
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    depends_on:
      - db

  worker:
    build: .
    command: python manage.py qcluster
    volumes:
      - .:/app
    depends_on:
      - db

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: crucebot
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
```

```bash
# Un solo comando arranca TODO
docker-compose up
```

**Ventajas:**
- ✅ Funciona igual en desarrollo y producción
- ✅ Fácil deployment
- ✅ Escalable

---

## 🎯 ¿Qué usar según tu caso?

| Escenario | Solución Recomendada |
|-----------|---------------------|
| **Desarrollo local (Windows)** | `start_dev.bat` o `sync: True` |
| **Desarrollo local (Linux/Mac)** | `start_dev.sh` o `sync: True` |
| **Servidor Linux (producción)** | Supervisor o systemd |
| **Docker** | Docker Compose |
| **Heroku** | Procfile con web + worker |
| **Testing rápido** | `sync: True` |

---

## ⚠️ Importante: sync=True

**Configuración actual:**
```python
Q_CLUSTER = {
    ...
    'sync': True  # ← Esto está activado en tu proyecto
}
```

**Qué significa:**
- Las tareas se ejecutan **inmediatamente** dentro del request
- **NO necesitas** `python manage.py qcluster`
- Es como si no usaras Django-Q (ejecuta la función directo)

**Cuándo cambiar a `sync: False`:**
- Cuando vayas a producción
- Cuando quieras asincronía real
- Cuando las tareas tarden mucho (>30 segundos)

---

## 🚀 Recomendación para tu proyecto

### Ahora mismo (Desarrollo):

**Opción A (Más simple):**
```python
# Ya está configurado
Q_CLUSTER = {'sync': True, ...}
```
```bash
# Solo correr:
python manage.py runserver
```

**Opción B (Asíncrono real):**
```python
# Cambiar a:
Q_CLUSTER = {'sync': False, ...}
```
```bash
# Usar:
.\start_dev.bat
```

### Cuando subas a producción:

1. Cambiar `sync: False`
2. Usar Supervisor o systemd
3. Configurar Gunicorn/uWSGI para Django
4. Worker separado con `qcluster`

---

## 📚 Alternativas a Django-Q

Si querés algo más integrado:

### 1. **Huey** (Más simple)
- Puede correr dentro de Django (thread)
- Menos features pero más fácil

### 2. **django-rq** (Redis Queue)
- Requiere Redis
- Similar a Django-Q

### 3. **Celery** (Más complejo)
- Industry standard
- Mucho más potente
- Mucho más complejo

### 4. **APScheduler** (Solo scheduling)
- No es task queue
- Solo para tareas programadas

---

## ✅ Resumen

**La respuesta a tu pregunta:**

> "¿No hay manera que se ejecute cuando arranco el mismo proyecto?"

**Sí, hay 3 formas:**

1. ✅ **`sync: True`** - Ya lo configuré, solo corre `runserver`
2. ✅ **`start_dev.bat`** - Corre ambos con un comando
3. ✅ **Producción** - Supervisor/systemd arrancan automáticamente

**Pero entendé:**
- Procesos separados es el **diseño correcto**
- Todas las task queues funcionan así (Celery, RQ, etc.)
- Es por seguridad y rendimiento
- `sync: True` es **solo para desarrollo** (pierde el propósito de async)

**Mi recomendación:**
- Desarrollo: Usa `start_dev.bat` (asíncrono real)
- Producción: Supervisor/systemd (robusto)
