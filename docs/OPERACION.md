# Operación y recuperación

## Producción sin pagos reales

Usa un solo proceso Waitress con sus hilos. La coordinación de respaldos y mantenimiento integrada está diseñada para esa topología; no ejecutes múltiples workers o réplicas contra los mismos directorios. Para varias réplicas se requiere almacenamiento y coordinación externa.

Configura variables del entorno (o un archivo privado para `docker --env-file`):

```text
ECOGALLO_ENV=production
ECOGALLO_DEV=0
ECOGALLO_SEED=0
PAYMENT_PROVIDER=disabled
ECOGALLO_SECURE=1
ECOGALLO_PUBLIC_URL=https://tu-dominio.example
ECOGALLO_SECRET=UN_SECRETO_ALEATORIO_PERSISTENTE_DE_AL_MENOS_32_CARACTERES
ECOGALLO_ADMINS=tu-administrador@edu.uaa.mx
ECOGALLO_SMTP_HOST=tu-servidor-smtp
ECOGALLO_SMTP_PORT=587
ECOGALLO_SMTP_USER=tu-usuario
ECOGALLO_SMTP_PASS=tu-clave
ECOGALLO_SMTP_FROM=tu-remitente-verificado
```

Genera un secreto real con `python -c "import secrets; print(secrets.token_hex(32))"`; no uses el texto de ejemplo. Si ya existen usuarios con 2FA, usa exactamente el contenido de la clave original `data/secret.key`: cambiarla rompe el descifrado y la autenticación de respaldos.

Arranque: `python run_prod.py`. Termina TLS en tu proxy/hosting y dirige el tráfico a Waitress en una red privada. Las cookies Secure y HSTS requieren ese HTTPS. Configura `ECOGALLO_PUBLIC_URL` con el origen público exacto. El backend no confía en encabezados de IP arbitrarios. El gateway Java usa un token compartido generado por sus scripts de arranque; detrás de otro proxy hace falta configurar de forma explícita una cadena de confianza equivalente.

Docker:

```text
docker build -t eco-gallo .
docker volume create ecogallo-data
docker run --env-file .env.production -v ecogallo-data:/app/data -p 127.0.0.1:8080:8080 eco-gallo
```

El contenedor corre como usuario sin privilegios y tiene comprobación de salud. No se copian archivos `.env`, bases ni dependencias Node al contexto. Usa un volumen; no almacenes la única copia de los datos dentro del contenedor. `.env.production` contiene secretos y no se versiona.

SMTP está implementado, pero el operador debe verificar entregas y configurar remitente, SPF/DKIM/DMARC según su proveedor. Completa también la identificación del responsable, contacto, aviso de privacidad y términos aplicables antes de abrir el servicio a usuarios reales. No se puede inferir esa información desde el repositorio.

## Stripe Test opcional

En desarrollo configura `PAYMENT_PROVIDER=stripe`, `STRIPE_SECRET_KEY=sk_test_...`, `STRIPE_WEBHOOK_SECRET=whsec_...` y registra `/api/stripe/webhook` mediante Stripe CLI o un endpoint HTTPS. Nunca mezcles claves de prueba y de producción.

Para probar sin completar una cuenta Connect real puedes activar `ECOGALLO_DEV=1` y `ECOGALLO_CONNECT_SIMULATED=1` **con una clave de prueba**. En Perfil pulsa Preparar vendedor de prueba. Checkout utiliza Stripe Test, pero la transferencia al vendedor es simulada. Esto no envía dinero ni habilita una cuenta real.

Eventos atendidos: `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed`, `checkout.session.expired`, `refund.created`, `refund.updated`, `refund.failed`, `charge.refunded` y `charge.dispute.created`.

Los retornos de Checkout abren la orden correspondiente. Las compras pendientes permiten continuar, cancelar de forma verificada y consultar estado. La conciliación se reintenta periódicamente y puede solicitarse desde la orden. Un resultado incierto nunca habilita la operación financiera opuesta. `RELEASING`, `REFUNDING` y `PAYMENT_REVIEW` bloquean el borrado de participantes.

Las operaciones se asocian a su proveedor original. No se convierten órdenes Stripe en simuladas por cambiar la configuración. No reutilices usuarios `SIM-CONNECT-*` en producción; prepara cuentas independientes verificadas.

## Activación real: pendiente del operador y de Stripe

Para dinero real faltan las cuentas y requisitos de verificación de Stripe, incluida la cuenta bancaria necesaria para recibir depósitos. El RFC depende del tipo de entidad y lo que Stripe solicite. No se sustituyen por datos inventados.

Solo después de validar la plataforma y los vendedores, el webhook y el ciclo completo de prueba, configura claves live, `ECOGALLO_LIVE_PAYMENTS=1`, DEV=0 y simulación Connect=0. La aplicación rechaza combinaciones inseguras. Esto no sustituye la aprobación de Stripe ni acredita el funcionamiento real por sí solo.

Stripe Checkout cobra a la plataforma y Connect transfiere al vendedor tras la confirmación. No constituye una garantía legal de escrow. Verifica con Stripe que el modelo comercial, la gestión de fondos y los plazos estén autorizados para la plataforma antes de activarlo. Transferir a Connect tampoco equivale a que el banco del vendedor ya haya recibido el depósito.

Un contracargo, reembolso parcial o conflicto posterior a la transferencia pasa a revisión. Revisa la operación en el Dashboard de Stripe y concilia los movimientos antes de intervenir. No fuerces estados directamente en SQLite. El flujo de demostración sí puede completarse sin estos datos externos.

Fuentes oficiales: https://support.stripe.com/questions/add-a-bank-account-for-payouts y https://support.stripe.com/questions/required-information-to-open-your-stripe-account-in-mexico

## Respaldos y clave de recuperación

Los nuevos ZIP v2 contienen una carga cifrada y autenticada que incluye SQLite, fotos y documentos pendientes. El secreto del sistema no se incluye dentro del ZIP. Guarda el contenido original de `ECOGALLO_SECRET` (o de `data/secret.key` en desarrollo) en un gestor de secretos o soporte cifrado separado. Perder la clave significa no poder descifrar el respaldo ni los secretos 2FA.

Descarga regularmente copias a almacenamiento externo cifrado y verifica una restauración en un entorno aislado. Los respaldos locales no protegen contra pérdida del disco. Configura retención (`ECOGALLO_BACKUP_KEEP`, por defecto 7); los documentos borrados del sistema activo pueden permanecer en copias históricas hasta su vencimiento. No anuncies eliminación de todas las copias de forma inmediata.

La carga descomprimida del respaldo integrado está limitada a 128 MiB, 20,000 entradas y rutas seguras. Para datos mayores usa un respaldo externo consistente con el servicio detenido. Los ZIP antiguos sin cifrar no se restauran desde el panel: consérvalos y migra en un entorno original aislado, generando allí un respaldo v2 con la clave correcta. No borres las copias antiguas antes de validar su sustitución.

La restauración valida cifrado, rutas, integridad y claves foráneas; bloquea temporalmente nuevas solicitudes, drena las operaciones en curso, crea una copia preventiva y revierte DB/archivos si falla la sustitución. Todas las sesiones antiguas y autorizaciones de recuperación se invalidan; solo se conserva la sesión del administrador que restaura y que debe seguir siendo administrador en el respaldo.

Si hay cualquier historial Stripe, el panel bloquea la restauración para evitar revivir pagos y reintentos financieros antiguos. En ese caso detén el servicio, conserva el estado actual y sus claves, restaura en un entorno aislado y concilia órdenes, transferencias, reembolsos y eventos con Stripe antes de reabrir. No conectes una copia antigua a Stripe live. Un corte de energía durante la sustitución requiere recuperar desde la copia preventiva: la reversión automática cubre errores del proceso, no una transacción distribuida entre disco y Stripe.

## Monitoreo y capacidad

`/api/health` informa de disponibilidad HTTP; no acredita SMTP, pagos ni espacio en disco. El operador debe configurar alertas externas de salud, errores, espacio, antigüedad del último respaldo y conciliaciones pendientes. Los registros evitan mostrar códigos fuera de DEV. SQLite funciona con WAL y transacciones; mide la carga real antes de crecer a varias réplicas.
