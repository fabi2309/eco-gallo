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
ECOGALLO_ADMIN_PASSWORD=UNA_CONTRASEÑA_PROPIA_DE_12_O_MAS
ECOGALLO_SMTP_HOST=tu-servidor-smtp
ECOGALLO_SMTP_PORT=587
ECOGALLO_SMTP_USER=tu-usuario
ECOGALLO_SMTP_PASS=tu-clave
ECOGALLO_SMTP_FROM=tu-remitente-verificado
ECOGALLO_OPERATOR_NAME=Nombre del responsable de los datos personales
ECOGALLO_OPERATOR_ADDRESS=Domicilio del responsable
ECOGALLO_PRIVACY_EMAIL=correo-para-derechos-arco@tu-dominio.example
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

SMTP está implementado, pero el operador debe verificar entregas y configurar remitente, SPF/DKIM/DMARC según su proveedor. El aviso de privacidad y los términos de uso viven en `frontend/js/views/legal.js` y se muestran en `#/privacidad` y `#/terminos`. Toman el nombre, domicilio y correo del responsable de las variables `ECOGALLO_OPERATOR_*` y `ECOGALLO_PRIVACY_EMAIL` (obligatoria en producción). Son un texto base redactado para el proyecto: haz que el responsable y, de preferencia, el área jurídica de la universidad lo revisen antes de abrir el servicio. Si cambias el texto, sube `LEGAL_VERSION` en `backend/config.py`; todos los usuarios tendrán que aceptarlo de nuevo al entrar.

Derechos ARCO dentro de la aplicación: **Perfil → Privacidad y mis datos** permite descargar todos los datos de la cuenta en JSON (acceso), corregir el perfil (rectificación) y eliminar la cuenta (cancelación). La baja anonimiza la cuenta igual que la eliminación administrativa y no procede mientras haya compras o ventas abiertas. La oposición se atiende por el correo del responsable.

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

## Entrar con la cuenta Microsoft de la UAA

Los correos de la UAA (`al123456@edu.uaa.mx`) son cuentas de Microsoft 365. Para mostrar el botón «Entrar con mi cuenta UAA (Microsoft)»:

1. Quien administra Microsoft Entra ID en la universidad registra una aplicación web de **un solo inquilino** (*Accounts in this organizational directory only*).
2. URL de retorno (Web): `<ECOGALLO_PUBLIC_URL>/api/auth/microsoft/callback`. En desarrollo: `http://localhost:8080/api/auth/microsoft/callback`.
3. Permisos delegados: `openid`, `profile`, `email` (no requieren consentimiento de administrador).
4. Crea un secreto de cliente y configura:

```text
ECOGALLO_MS_CLIENT_ID=<Application (client) ID>
ECOGALLO_MS_CLIENT_SECRET=<valor del secreto>
ECOGALLO_MS_TENANT=<Directory (tenant) ID de la UAA, un GUID>
```

El servidor rechaza `common` u `organizations` como inquilino porque aceptarían cuentas de cualquier organización. Aun con el inquilino correcto, el correo debe pertenecer a `ECOGALLO_EMAIL_DOMAINS`. Si la cuenta tiene 2FA en ECO-GALLO, se pide igual después de Microsoft. Renueva el secreto antes de que venza (Entra ID le pone fecha de expiración).

## Celular confirmado por SMS (pagos con tarjeta)

Para pagar o cobrar con tarjeta, comprador y vendedor confirman su celular con un código por SMS; en cada compra con tarjeta, cada parte (y administración) ve el celular de la otra para poder localizarse si no se entrega. Los SMS se envían con Twilio:

```text
TWILIO_ACCOUNT_SID=<Account SID>
TWILIO_AUTH_TOKEN=<Auth Token>
TWILIO_FROM=<número de Twilio, formato +1...>
```

Sin Twilio, en desarrollo el código se muestra en pantalla; en producción los pagos con tarjeta no arrancan sin SMS. Del comprador solo se guarda la marca y los últimos 4 dígitos de su tarjeta, y del vendedor el titular, tipo (tarjeta de débito o CLABE) y últimos 4 dígitos: el número completo y el CVV se validan en el navegador y nunca llegan al servidor. Con Mercado Pago real, la tarjeta se captura en la página de Mercado Pago.

## Pagos con Mercado Pago

Alternativa a PayPal para México: Checkout Pro acepta tarjeta de crédito y débito, saldo de Mercado Pago, OXXO y SPEI. Se activa con `PAYMENT_PROVIDER=mercadopago`.

1. En *Tus integraciones* de Mercado Pago crea una aplicación (Checkout Pro) y copia el **Access Token**. Para pruebas usa las credenciales y los usuarios de prueba, con `MERCADOPAGO_TEST=1`.
2. En la sección **Webhooks** de la aplicación registra `<ECOGALLO_PUBLIC_URL>/api/mercadopago/webhook` con el evento **Pagos** y copia la **clave secreta**.
3. Configura:

```text
PAYMENT_PROVIDER=mercadopago
MERCADOPAGO_ACCESS_TOKEN=<access token>
MERCADOPAGO_WEBHOOK_SECRET=<clave secreta de webhooks>
MERCADOPAGO_TEST=1          # 0 solo en producción, junto con ECOGALLO_LIVE_PAYMENTS=1
```

Cómo funciona:

- Al comprar se reserva el artículo y se abre Checkout Pro. El enlace vence en 24 h. Una ficha OXXO o SPEI pendiente mantiene la reserva; si no se paga, Mercado Pago la cancela y la conciliación libera el artículo.
- La notificación solo dispara una consulta: el estado se lee siempre de la API de Mercado Pago, con la firma `x-signature` verificada. Si la notificación no llega, el regreso del comprador y la conciliación cada minuto aplican el mismo resultado.
- El dinero queda en la cuenta de Mercado Pago de la plataforma hasta que el comprador confirma la recepción. Entonces la orden aparece en **Administración → Pagos por liquidar a vendedores**. Quien administra transfiere el importe al vendedor y registra la referencia; el vendedor recibe un aviso.
- Los reembolsos (del vendedor o por disputa) se hacen por la API, por el importe exacto de la orden.
- Importe distinto, pago tras una cancelación, contracargo o mediación: la orden pasa a revisión y se avisa a administración.

La liquidación al vendedor es manual porque Mercado Pago no ofrece transferencias a terceros desde la API estándar. La alternativa automática sería el modelo *Marketplace* de Mercado Pago (cada vendedor vincula su cuenta por OAuth y el cobro llega directo a él), pero entonces el dinero ya no queda retenido por ECO-GALLO.
