# ECO-GALLO UAA

Marketplace universitario de economía circular: venta, trueque y donación de materiales entre estudiantes y egresados verificados.

## Ejecutar la demostración

Python 3.11 o posterior. En Windows ejecuta `run_dev.bat`, que instala dependencias y abre el servidor en http://localhost:8080. También puedes usar:

```powershell
python -m pip install -r backend/requirements.txt
$env:ECOGALLO_DEV="1"
$env:ECOGALLO_SEED="1"
$env:ECOGALLO_ADMINS="admin@edu.uaa.mx"
python run_dev.py
```

Los códigos de acceso se muestran en pantalla solo en DEV. Accede con un correo institucional; la primera vez completa nombre y carrera. El administrador se asigna desde `ECOGALLO_ADMINS`. No hay una contraseña administrativa universal.

**La demostración no cobra ni transfiere dinero y no pide RFC ni cuenta bancaria.** Sus saldos, compras y reembolsos son ficticios y están señalados. Es suficiente para probar el flujo completo de entrega, confirmación, disputas y devoluciones.

Las variables se leen del entorno del proceso. `.env.example` es una plantilla; copiarla a `.env` no la carga automáticamente. Docker sí puede leer un archivo mediante `--env-file`.

## Funciones

### Aplicación móvil Android

El cliente Flutter está en `mobile/`: acceso, perfil, catálogo y publicaciones con fotos, favoritos, deseos, mensajes, notificaciones, compras y ventas simuladas, saldo, actividad e impacto. Incluye «Mis publicaciones», edición, pausa, reanudación y cierre de donaciones o trueques; conserva la revisión administrativa de la web. Para una prueba aislada ejecuta `run_mobile_demo.bat` y, en otra terminal con el emulador encendido, `run_mobile.bat`. Consulta los pasos, cuentas de demo y alcance en [mobile/README.md](mobile/README.md).

### Aplicación web

- Acceso institucional por correo, contraseña y 2FA opcional con códigos de recuperación.
- Restablecimiento de contraseña después de verificar correo y, si está activado, 2FA; autorización de 10 minutos y un solo uso.
- Registro de egresados con revisión administrativa y documentos privados.
- Publicación en tres pasos, hasta cinco fotografías, premoderación y nueva revisión al cambiar contenido o fotos; pausa y reanudación.
- Catálogo con búsqueda, sugerencias, filtros, paginación, favoritos y lista de deseos con alertas de coincidencia o reducción de precio.
- Perfil, fotografía, biografía, insignias e historial paginado.
- Mensajes por publicación, notificaciones, reportes y puntos de encuentro.
- Compras y ventas con estados protegidos, historial, disputas y resolución administrativa.
- Panel administrativo con revisión de publicaciones, egresados, usuarios, reportes, operaciones financieras y gráficas locales accesibles.
- Impacto de reutilización y estimaciones orientativas de CO₂e por categoría.
- Respaldos cifrados, verificados y rotados; restauración con mantenimiento, copia preventiva y reversión ante fallas.

## Pagos

| Proveedor | Uso |
|---|---|
| `simulado` | Desarrollo sin dinero, RFC, datos bancarios ni claves. |
| `disabled` | Marketplace operativo con contacto por mensajes y sin cobros en línea. Predeterminado en producción. |
| `stripe` | Stripe Checkout y Connect; requiere claves, webhook y cuentas habilitadas. |

La transferencia al banco real exige completar los requisitos de Stripe. El RFC depende del tipo de cuenta y las verificaciones solicitadas; el sistema no omite ni falsifica esos requisitos. Consulta [configuración, recuperación y límites de operación](docs/OPERACION.md).

## Seguridad y despliegue

El servidor de desarrollo y el gateway Java escuchan únicamente en loopback por defecto. Producción utiliza `run_prod.py` con Waitress sin depurador. El gateway Java opcional requiere **Java 21+** (`run.sh` o `run.bat`). La protección CSRF, las cabeceras y el límite de autenticación se aplican también en Python.

Producción exige HTTPS, cookies Secure, SMTP y un secreto persistente; rechaza DEV y simulación. No publiques directamente el servidor de desarrollo. Las instrucciones de proxy, Docker y respaldo están en [OPERACION.md](docs/OPERACION.md).

## Pruebas

La instalación del APK, los modos de conexión USB y red local y el alcance del cliente Android se describen en [mobile/README.md](mobile/README.md). La configuración de producción y respaldos está en [OPERACION.md](docs/OPERACION.md).

```powershell
python -m pip install -r backend/requirements.txt -r requirements-dev.txt
python -m pytest tests -q
python -m flake8 backend tests --config=.flake8
python -m bandit -r backend -ll -ii
python -m pip_audit -r backend/requirements.txt
python tests/run_e2e.py
```

Las pruebas automatizadas usan bases temporales. `run_e2e.py` arranca Waitress en un puerto local disponible y ejecuta la suite por HTTP real. Las pruebas Stripe usan respuestas controladas: no acreditan cobros ni transferencias reales. Los fallos financieros, firmas, duplicados, permisos y respaldos tienen pruebas de regresión.

## Estructura

`backend/`: Flask y SQLite. `frontend/`: HTML/CSS/JavaScript nativo. `gateway/`: gateway Java opcional. `tests/`: pruebas. `data/`: datos persistentes excluidos de Git. `docs/`: operación y comprobaciones.

El catálogo de carreras vive en `backend/catalog.py` y debe contrastarse con la oferta oficial de la UAA cuando cambie. Las métricas de CO₂e son estimaciones, no mediciones certificadas.
