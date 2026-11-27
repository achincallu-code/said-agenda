# Despliegue en Neon y Render

## 1. Crear la base Neon

1. Crea un proyecto en Neon.
2. Copia la cadena de conexión PostgreSQL que comienza con `postgresql://`.
3. Conserva `?sslmode=require` si Neon la incluye.

## 2. Subir el proyecto

Sube esta carpeta a un repositorio de GitHub. Render necesita acceso al archivo `render.yaml`.

## 3. Crear el servicio en Render

1. En Render selecciona **New > Blueprint**.
2. Conecta el repositorio.
3. Cuando Render solicite `DATABASE_URL`, pega la cadena de conexión de Neon.
4. Inicia el despliegue.

No uses comillas alrededor de la cadena de conexión. Render configurará `DATABASE_URL` automáticamente.

## 4. Variables necesarias

- `DATABASE_URL`: cadena PostgreSQL de Neon.
- `AGENDA_SECRET_KEY`: clave larga y aleatoria. El archivo `render.yaml` genera una automáticamente.

## Ejecución local

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python agenda.py
```

La aplicación continúa usando `contactos.db` cuando no existe `DATABASE_URL`.

Para probar PostgreSQL localmente, crea una variable temporal:

```powershell
$env:DATABASE_URL="postgresql://usuario:contraseña@host/neondb?sslmode=require"
.venv\Scripts\python agenda.py
```
