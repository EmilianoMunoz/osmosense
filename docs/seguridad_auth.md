# Seguridad, Login y Control de Acceso

Este documento describe el esquema actual de autenticación y autorización del
sistema. Cubre el login real contra PostGIS, los accesos demo de desarrollo, el
token de sesión y la separación de vistas por rol.

## Estado Actual

El sistema usa autenticación propia basada en:

- usuarios guardados en PostGIS;
- contraseñas hasheadas con PBKDF2-SHA256;
- token firmado con HMAC-SHA256;
- control de acceso por rol en FastAPI;
- estado de sesión en Streamlit.

El token actual no es JWT estándar. Es un token propio con formato:

```text
hmac_sha256.<payload_base64url>.<firma_base64url>
```

La implementación principal está en:

```text
backend/app/services/auth.py
```

## Roles

Los roles operativos vigentes son:

| Rol | Vista Streamlit | Alcance |
|---|---|---|
| `admin` | Admin | Acceso global a rankings, usuarios, parcelas, gestión y estado operativo. |
| `regional` | Regional | Acceso a vistas agregadas por UM/región. |
| `productor` | Productor | Acceso limitado a las parcelas asociadas a su `cliente_id`. |

También existen aliases legacy:

```python
ROLE_ALIASES = {
    "cliente_particular": "productor",
    "cliente_regional": "regional",
}
```

Eso permite mantener compatibilidad si aparecen roles viejos en datos previos.

## Login Real

El login manual del frontend llama a:

```text
POST /auth/login
```

Definido en:

```text
backend/app/main.py
```

La API delega en:

```python
authenticate_user(payload.email, payload.password)
```

La función `authenticate_user()`:

1. Lee `DATABASE_URL`.
2. Busca el usuario activo en la tabla `usuarios`.
3. Compara la contraseña ingresada contra `password_hash`.
4. Actualiza `last_login_at`.
5. Devuelve `access_token` y datos limpios del usuario.

Consulta usada:

```sql
SELECT usuario_id, email, nombre, rol, cliente_id, password_hash
FROM usuarios
WHERE lower(email) = %s
  AND activo = true
```

Si el login es exitoso, la respuesta tiene esta forma:

```json
{
  "source": "postgis",
  "token_type": "bearer",
  "access_token": "...",
  "user": {
    "usuario_id": 1,
    "email": "admin",
    "nombre": "Administrador",
    "rol": "admin",
    "cliente_id": null,
    "view_mode": "Admin"
  }
}
```

## Hash De Contraseña

Las contraseñas no se guardan en texto plano.

Se usa:

```text
PBKDF2-HMAC-SHA256
260000 iteraciones
salt aleatorio de 16 bytes
```

Formato guardado:

```text
pbkdf2_sha256$260000$<salt_base64>$<digest_base64>
```

Funciones:

```python
hash_password(password)
verify_password(password, password_hash)
```

Archivo:

```text
backend/app/services/auth.py
```

## Token De Acceso

El token se crea con:

```python
create_access_token(user)
```

El payload incluye:

| Campo | Descripción |
|---|---|
| `sub` | `usuario_id` |
| `email` | Usuario/email |
| `nombre` | Nombre visible |
| `rol` | `admin`, `regional` o `productor` |
| `cliente_id` | Productor/campo asociado, si aplica |
| `view_mode` | Vista inicial sugerida |
| `iat` | Fecha/hora de emisión |
| `exp` | Fecha/hora de expiración |

La duración por defecto es:

```text
8 horas
```

Puede cambiarse con:

```text
AUTH_TOKEN_TTL_SECONDS
```

La firma usa:

```text
HMAC-SHA256
```

La clave sale de:

```text
AUTH_SECRET
```

Si `AUTH_SECRET` no está definida, se usa un valor dev por defecto:

```text
estres-dev-auth-secret
```

En producción debe configurarse `AUTH_SECRET` explícitamente.

## Verificación Del Token

La API espera el token en el header:

```text
Authorization: Bearer <token>
```

La función:

```python
current_user()
```

valida:

1. Que exista header `Authorization`.
2. Que tenga prefijo `Bearer`.
3. Que la firma HMAC sea válida.
4. Que el token no esté expirado.

Si falla, responde:

```text
401 Unauthorized
```

## Permisos Por Endpoint

Los permisos se aplican con dependencias FastAPI.

### `require_roles`

Uso:

```python
Depends(require_roles("admin"))
```

Permite acceder solo a usuarios cuyo `rol` esté en la lista.

Ejemplos:

| Endpoint | Roles |
|---|---|
| `/rankings/latest` | `admin` |
| `/rankings/latest/geojson` | `admin` |
| `/pipeline/state` | `admin` |
| `/admin/usuarios` | `admin` |
| `/admin/parcelas/disponibles` | `admin` |
| `/regional/um/latest/geojson` | `admin`, `regional` |

### `require_cliente_or_admin`

Uso:

```python
Depends(require_cliente_or_admin)
```

Regla:

- `admin` puede acceder a cualquier `cliente_id`;
- `productor` solo puede acceder a su propio `cliente_id`;
- `regional` no puede acceder a endpoints de productor.

Se usa en:

```text
GET /clientes/{cliente_id}/rankings/latest/geojson
```

## Sesión En Streamlit

El frontend guarda la sesión en:

```python
st.session_state
```

Campos principales:

| Campo | Uso |
|---|---|
| `authenticated` | Indica si hay sesión iniciada. |
| `auth_user` | Usuario/email. |
| `auth_label` | Nombre visible. |
| `auth_rol` | Rol operativo. |
| `auth_cliente_id` | Productor asociado, si aplica. |
| `auth_source` | `postgis`, `demo` o local. |
| `auth_token` | Token bearer para llamadas a API. |
| `view_mode` | Vista activa: Admin, Regional o Productor. |

Archivo:

```text
frontend/auth.py
```

## Separación De Vistas

La vista disponible se decide en:

```text
frontend/views/dashboard.py
```

Función:

```python
select_view_mode()
```

Reglas:

- `admin`: puede elegir `Admin`, `Regional` o `Productor`;
- `regional`: solo ve `Regional`;
- `productor`: solo ve `Productor`;
- sesión no autenticada: pantalla de login.

## Accesos Demo

El login tiene botones rápidos para desarrollo:

```text
Productor vid
Productor olivo
Admin
Regional
```

Estos botones usan:

```python
login_as(DEMO_USERS["..."])
```

Importante:

- no llaman a `/auth/login`;
- no generan token real;
- dejan `auth_source = "demo"`;
- no deben considerarse autenticación productiva.

Si se entra con demo, algunos endpoints protegidos no pueden responder porque no
hay bearer token. En ese caso el frontend puede usar fallback local si existe.

Para probar el flujo real PostGIS hay que escribir usuario y contraseña en el
formulario de login.

## Fallback Local

El frontend intenta primero consultar la API.

Si la API no responde, el token no existe, el endpoint devuelve error o se agota
el timeout, algunas vistas usan CSV/GeoJSON local como fallback.

Ejemplos:

```python
load_geojson()
load_cliente_geojson_local()
load_zonificacion_san_rafael()
```

Esto sirve para desarrollo y demo local, pero en producción debe verificarse que
la fuente sea `postgis`.

El dashboard muestra avisos de fuente:

- API disponible/no disponible;
- datos desde PostGIS;
- datos desde CSV/fallback local.

## Tests

Los tests principales están en:

```text
tests/test_auth.py
tests/test_api_handlers.py
```

Cubren:

- hash y verificación de contraseña;
- roundtrip del token firmado;
- rechazo de tokens inválidos;
- permisos por rol;
- productor limitado a su propio `cliente_id`;
- admin con acceso global.

Comando:

```bash
venv/bin/python -m pytest tests/test_auth.py tests/test_api_handlers.py -q
```

## Limitaciones Actuales

- El token no es JWT estándar.
- No hay refresh token.
- No hay revocación de token en servidor.
- Los accesos demo siguen disponibles para desarrollo.
- `AUTH_SECRET` debe configurarse explícitamente en producción.
- El fallback local es útil para desarrollo, pero puede ocultar problemas de API
  si no se revisa la fuente mostrada.
- No hay HTTPS configurado dentro de la app; debe resolverlo el proxy/despliegue.

## Camino A Producción

Antes de producción conviene:

1. Migrar el token propio a JWT estándar o documentar formalmente la decisión de mantener HMAC propio.
2. Definir `AUTH_SECRET` fuerte en `.env`/secrets de cloud.
3. Desactivar accesos demo o protegerlos detrás de una variable de entorno.
4. Exigir HTTPS en el entorno cloud.
5. Agregar política de rotación de contraseñas si el alcance del producto lo requiere.
6. Registrar intentos de login fallidos.
7. Revisar expiración de token y UX al expirar sesión.
8. Agregar tests de permisos con cliente/productor reales desde fixtures PostGIS.
