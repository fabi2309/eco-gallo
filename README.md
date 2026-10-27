# ECO-GALLO UAA

Marketplace universitario de economía circular (tesina ECO-GALLO). **Sin Angular, sin Node**:

| Capa | Tecnología |
|---|---|
| Frontend | HTML + CSS + JavaScript nativo (módulos ES, sin build) — `frontend/` |
| Gateway | **Java** puro (`com.sun.net.httpserver`): sirve el frontend, hace proxy a la API, cabeceras de seguridad y límite de ritmo en `/api/auth` — `gateway/Gateway.java` |
| Backend | **Python / Flask** + SQLite — `backend/` |

## Arrancar
### Opción 1: Con Gateway oficial (Java + Python)
Requisitos: Python 3.10+, Java 17+ (probado con 21).

```bash
./run.sh          # Linux / macOS      (Windows: run.bat)
# abre http://localhost:8080
```
### Opción 2: Desarrollo rápido (100% Python, sin necesidad de Java)
Si no tienes Java JDK instalado, puedes iniciar la aplicación completa directamente con Python:
```bash
pip install -r backend/requirements.txt
python run_dev.py     # En Windows también puedes usar: run_dev.bat
# abre http://localhost:8080
```

Sin SMTP configurado, el código de acceso se imprime en la consola y se muestra en pantalla
(`ECOGALLO_DEV=1`, solo desarrollo). Se cargan 8 publicaciones de demostración (`ECOGALLO_SEED=1`).

## Acceso (tres caminos)
| Quién | Cómo entra |
|---|---|
| **Estudiante** `@edu.uaa.mx` | Código de 6 dígitos al correo (vence en 10 min, un solo uso, 5 intentos, reenvío cada 45 s, 5 códigos/hora por correo). La primera vez se crea la cuenta y se pide nombre y **carrera** (lista). |
| **Con contraseña** (cualquier cuenta) | Correo + contraseña, sin códigos. Se crea al registrarse (opcional) o después en *Perfil*. Mínimo 8 caracteres con letras y número; se guarda con hash scrypt; 5 fallos seguidos bloquean 15 min; cambiarla cierra las demás sesiones. «Olvidé mi contraseña» = entrar con código y fijar una nueva. |
| **Egresado** | Se registra con **cualquier correo** + nombre + carrera + **kárdex o título** (imagen o PDF ≤ 6 MB) + contraseña. Confirma su correo con un código y queda **en revisión**: no ve el marketplace hasta que un admin lo apruebe en *Administración → Egresados por verificar*. Si lo rechazan, ve el motivo y puede subir otro documento. |

Los documentos se guardan en `data/private/verificaciones/` (nunca en `/uploads`), solo los puede abrir un admin y **se borran al resolver** la solicitud.
La sesión es una cookie `HttpOnly` + `SameSite=Lax`.

**Para enviar correos reales** define:
```
ECOGALLO_SMTP_HOST=smtp.gmail.com  ECOGALLO_SMTP_PORT=587
ECOGALLO_SMTP_USER=...  ECOGALLO_SMTP_PASS=...  ECOGALLO_SMTP_FROM="ECO-GALLO <...>"
# SMTPS (465): ECOGALLO_SMTP_SSL=1
```
Con HTTPS en producción añade `ECOGALLO_SECURE=1`. `ECOGALLO_AUTH_LIMIT` (por defecto 30) = peticiones por minuto e IP a `/api/auth/*` en el gateway; súbelo si muchos usuarios comparten la misma IP (red del campus) o para correr las pruebas. Administradores: `ECOGALLO_ADMINS=correo1@edu.uaa.mx,correo2@edu.uaa.mx`.

## Pago retenido (escrow)
```
Comprador paga ──► HELD (retenido) ──► DELIVERED (vendedor marca entregado, sigue retenido)
                      │                         │
                      └────── comprador confirma recepción ──► RELEASED (se libera al vendedor)
                      └────── comprador abre disputa ──► DISPUTED ──► admin: RELEASED | REFUNDED
                      └────── vendedor devuelve ──► REFUNDED
```
- **Solo el comprador** (o el admin en una disputa) puede liberar el dinero. No hay liberación automática por tiempo.
- La reserva del artículo y los cambios de estado son atómicos (SQLite `BEGIN IMMEDIATE` + `UPDATE … WHERE status IN (…)`), así que no se puede pagar dos veces ni liberar dos veces.
- Cada paso queda en un historial y genera notificaciones.
- Solo las **ventas** usan escrow; trueques y donaciones se acuerdan por mensaje.
- ⚠️ `backend/payments.py` trae un proveedor **simulado** (no mueve dinero ni pide tarjeta). Para producción implementa
  `PaymentProvider` con una pasarela que soporte retención/captura diferida (Stripe Connect, Mercado Pago…).

## Módulos (según la tesina)
Autenticación (código, contraseña, egresados verificados) · Publicaciones (hasta 4 fotos; se pueden **pausar** y reanudar) ·
Búsqueda y filtros (texto, categoría, tipo, centro, **estado del producto y rango de precio**) con **búsquedas recientes** ·
**Lista de deseos** (aviso en la campana cuando alguien publica algo que coincide; se revisa cada 30 s) ·
Perfil con **foto y biografía** · **Modo oscuro** · Mensajería por publicación
con puntos de encuentro seguros · Notificaciones · Historial · Reportes · Panel de administración (disputas, reportes, usuarios) ·
Dashboard de impacto (CO₂e estimado por categoría).

## Pruebas
Arranca con `ECOGALLO_ADMINS=admin@edu.uaa.mx ./run.sh` y luego `python3 tests/e2e_api.py` (~100 comprobaciones: login, contraseñas, egresados, filtros, pausa, foto/bio, lista de deseos, escrow, disputas, permisos; tarda ~1 min por esperas de reenvío). Para no chocar con el límite del gateway: `ECOGALLO_AUTH_LIMIT=500 ./run.sh`.

## Estructura
```
backend/   app.py config.py db.py security.py auth.py posts.py orders.py payments.py social.py admin.py seed.py
gateway/   Gateway.java
frontend/  index.html css/app.css js/{main,api,ui}.js js/views/*.js
data/      (se crea sola) base SQLite, fotos subidas y clave secreta
run_dev.py / run_dev.bat   servidor local de desarrollo en Python (sin necesidad de Java)
.env.example               plantilla con variables de entorno soportadas
```
## Centros y carreras
`backend/catalog.py` es la única fuente (registro, perfil, filtros, publicaciones). El centro del usuario se deduce de su carrera.
La lista se armó desde una fuente secundaria (el portal de la UAA bloquea la lectura automática): contrástala con
https://www.uaa.mx/portal/oferta-educativa/licenciaturas/ y corrige ahí si cambia algo. Las bases existentes se migran solas (nombres de centro y columnas nuevas).
