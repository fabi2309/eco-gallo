# ECO-GALLO móvil — Android

Cliente Flutter del backend Flask existente. Incluye acceso por contraseña, código de correo y segundo factor cuando la cuenta lo requiere; perfil; catálogo y publicaciones con fotos; favoritos y deseos; mensajes; notificaciones; carrito; compras en efectivo y simuladas; saldo, actividad e impacto mensual con ahorro estimado. «Mis publicaciones» permite editar, pausar, reanudar, retirar, destacar gratuitamente y cerrar donaciones o trueques entregados; también muestra visitas, contactos e interesados.

El panel administrativo, los documentos de egresados, el acceso Microsoft, el cambio de contraseña y la configuración del segundo factor se gestionan desde la web. El móvil permite autenticarse con el segundo factor ya configurado. La búsqueda cercana usa coordenadas aproximadas introducidas manualmente; no solicita permisos GPS. Este proyecto incluye Android; iOS, notificaciones push y publicación en tiendas no están configurados. Las notificaciones disponibles son internas de la app.

## Versión integrada: datos principales por USB

1. Detén el servidor anterior desde su terminal. En la raíz del proyecto ejecuta `./servidor_movil.bat --usb --codigos-locales` y deja esa terminal abierta. Utiliza `data/ecogallo.sqlite`, hace un respaldo previo en `data/backups/`, no agrega cuentas de demo y conserva las contraseñas existentes. Desactiva proveedores de pago externos y la lectura de `.env`.
2. Conecta el teléfono con un cable de datos, activa Depuración USB y acepta la autorización de esta computadora. Ejecuta `./conectar_movil_usb.bat`; si también está abierto el emulador, indica el serial del teléfono como argumento.
3. Instala **una vez por actualización** el archivo `artifacts/mobile/ECO-GALLO-local.apk`, generado con `./crear_apk_local.bat`. Puedes enviarlo por cable y abrirlo desde Archivos, permitiendo la instalación desde esa aplicación. También puedes instalarlo con `adb -s SERIAL install -r artifacts/mobile/ECO-GALLO-local.apk`. Al sustituir la versión anterior se conserva la misma firma de pruebas de esta computadora.
4. En ECO-GALLO configura `http://127.0.0.1:8080` e inicia sesión con una cuenta del proyecto principal. Web y móvil muestran los mismos registros del servidor. El teléfono no necesita un gestor de base de datos ni recibe una copia de SQLite.
5. Al reconectar el cable o reiniciar el teléfono repite solo el arranque del servidor, si estaba apagado, y `./conectar_movil_usb.bat`. No hay que recompilar ni reinstalar el APK cada vez y no se abren reglas de firewall.

`--codigos-locales` muestra códigos ficticios de correo y teléfono, sin enviar SMS ni correos reales, exclusivamente con `--usb` y escucha en loopback. Úsalo para la tesina con teléfonos y referencias ficticios. Sin esa opción, el acceso por contraseña sigue disponible, pero confirmar teléfonos nuevos necesita SMS configurado. Este modo local no es un despliegue público.

Al primer acceso acepta la versión vigente de los términos. En **Privacidad y términos** puedes leer ambos documentos, consultar/copiar tus datos y solicitar la baja con confirmación escrita, contraseña y 2FA cuando corresponda. El servidor impide la baja con operaciones abiertas.

Para probar compras sin teléfono ni referencia de cobro selecciona **Efectivo al entregar**, que es la opción predeterminada. El material queda reservado; el vendedor confirma el cobro al entregar o se cancela la reserva. Para probar **Tarjeta ficticia · simulación**, comprador y vendedor confirman un número ficticio en **Teléfono y cobros**; el vendedor guarda una referencia ficticia (titular, tipo y cuatro dígitos). Al comprar usa, por ejemplo, titular «Persona de prueba», últimos cuatro «4242» y vencimiento futuro. No introduzcas número completo, CVV, cuenta real ni RFC. Configurar estas referencias no habilita transferencias.

Prueba también agregar varios artículos al **Carrito**, el punto de entrega y precio nuevo opcionales al publicar, destacar una publicación propia aprobada, ordenar por precio y **Cerca de un punto** con coordenadas aproximadas. Los cambios quedan sujetos a las mismas validaciones y revisión del servidor web.

## Probar en Windows con el emulador

1. Enciende el emulador Eco-Gallo desde Android Studio. Puedes cerrar la ventana del IDE después de arrancarlo para liberar memoria.
2. En una terminal PowerShell en la raíz del repositorio ejecuta `./run_mobile_demo.bat` y déjala abierta. La primera ejecución crea `.venv` e instala las dependencias Python.
3. En otra terminal, también en la raíz, ejecuta `./run_mobile.bat`. Configura `adb reverse` y ejecuta Flutter en `emulator-5554`. La primera compilación descarga herramientas de Gradle/Android y puede tardar bastante. Si el serial cambia, usa `./run_mobile.bat SERIAL` (consulta `flutter devices`).
4. En la app usa **movil@edu.uaa.mx** / **EcoGalloDemo123**. Son credenciales públicas y exclusivas de esta demo local.
5. Busca «Cálculo», abre el libro y vuelve al catálogo. Prueba los filtros Libros, Electrónica, Venta, Trueque y Donación. Un texto sin coincidencias debe mostrar un estado vacío. Cierra la sesión con el icono superior.
6. Para probar el primer acceso, elige «Primera vez o sin contraseña: usar código» y usa un correo ficticio institucional, por ejemplo `prueba-movil@edu.uaa.mx`. En esta demo el código aparece como «Solo desarrollo». Verifícalo y completa nombre y carrera. No se envían correos reales desde este servidor de demo.
7. Al terminar usa Ctrl+C en las terminales. En `flutter run`, `r` recarga cambios y `q` termina la ejecución. La próxima vez repite los pasos 1–3.

Si aparece «sin conexión», comprueba que la primera terminal siga mostrando `Running on http://127.0.0.1:8080`. Abre http://127.0.0.1:8080/api/health en el navegador del equipo: debe responder `{"ok":true}`. Después pulsa «Reintentar» en la app. `run_mobile.bat` comprueba el servidor antes de compilar y muestra las instrucciones si está apagado.

El servidor demo conserva sus datos en `data/mobile-demo/`, separado de `data/ecogallo.sqlite`; no elimina ni migra los datos habituales. Solo escucha en 127.0.0.1:8080. Si el puerto está ocupado, detén desde su terminal el otro servidor antes de arrancar la demo. La web de esta misma demo se puede abrir en http://127.0.0.1:8080.

Para usar tus datos habituales, arranca `./servidor_movil.bat --usb --codigos-locales` en lugar de `./run_mobile_demo.bat` y usa una cuenta existente. Ejecuta solo uno de los dos servidores a la vez. Los cambios de perfil desde móvil se comparten con la web del servidor elegido.

## Probar publicaciones con fotos y revisión

Si ya estaba abierto el servidor demo antes de esta actualización, reinícialo con `./run_mobile_demo.bat` para crear la cuenta de revisión. Reinicia también Flutter con `./run_mobile.bat`; el selector de fotos incluye código nativo y necesita reinstalación, no solo hot reload.

1. Entra en el móvil con `movil@edu.uaa.mx` / `EcoGalloDemo123` y pulsa **Publicar**.
2. Completa título, descripción, categoría, tipo y estado del material. El centro se propone desde tu perfil y se puede cambiar. En venta, el precio debe ser mayor a cero y no superar el límite del servidor; donaciones y trueques no piden precio y se envían con valor cero.
3. Pulsa **Seleccionar fotos**. Puedes usar hasta cinco JPG, PNG o WebP, de hasta 5 MB cada una y 24 MB en conjunto. Se muestran miniaturas y puedes quitar fotos antes de enviar. Son opcionales, igual que en la web. En este emulador se agregó una foto de libro de ejemplo en `Pictures/ECO-GALLO/` para probar la galería.
4. Pulsa **Enviar a revisión**. En **Mis publicaciones** debe aparecer **En revisión**; todavía no se verá en el catálogo general.
5. En el navegador del equipo abre http://127.0.0.1:8080 e inicia sesión con la cuenta pública de demo **revision@edu.uaa.mx** / **EcoGalloRevision123**. Abre el panel de administración y aprueba la publicación pendiente. Esta cuenta se crea exclusivamente con el servidor aislado de demo, nunca con el servidor habitual.
6. Vuelve a **Mis publicaciones** y pulsa **Actualizar**. Debe aparecer **Disponible**. Prueba **Pausar**, revisa que desaparezca del catálogo, y **Reanudar** para devolverla.
7. Prueba **Editar**. Guardar sin seleccionar fotos nuevas conserva las actuales. Si eliges fotos nuevas, reemplazan al conjunto anterior. Los cambios de contenido o de fotos vuelven a revisión; el backend decide el estado final. Las publicaciones reservadas o vendidas no ofrecen edición.

El formulario avisa antes de salir con cambios sin guardar. Durante el envío se bloquean los envíos repetidos. Si se interrumpe la conexión después de enviar, revisa **Mis publicaciones** antes de volver a intentarlo: el servidor pudo haber recibido la publicación.

El selector comprueba al iniciar si Android conservó fotos de una selección interrumpida. Al abrir un formulario nuevo puede recuperarlas y pedirte completar nuevamente los campos. Los textos del formulario y la sesión permanecen en memoria; no hay borrador persistente al cerrar por completo el proceso.

La selección utiliza [image_picker, publicado por Flutter](https://pub.dev/packages/image_picker), con reducción a 1920 píxeles por lado, calidad 85 y sin solicitar metadatos completos. Las comprobaciones locales de formato y tamaño complementan la validación del servidor: este vuelve a decodificar y normalizar las imágenes, elimina metadatos y aplica autorización y CSRF. No se añadieron permisos generales de almacenamiento.

## Probar comunidad y pedidos simulados

Reinicia el servidor con `./run_mobile_demo.bat` y la aplicación con `./run_mobile.bat` después de actualizar. El menú **☰** del catálogo abre Favoritos, Lista de deseos, Mensajes, Notificaciones, Compras y ventas, Saldo, Mi perfil, Mi actividad e Impacto.

- **Favoritos:** abre un material y pulsa el corazón. Desde el menú puedes consultarlo o quitarlo. Si el material vuelve a revisión o deja de estar disponible, se muestra sin revelar contenido privado y todavía puedes quitarlo.
- **Deseos:** agrega un término y, opcionalmente, categoría y centro. Cuando se apruebe una publicación coincidente, aparecerá un aviso en Notificaciones.
- **Mensajes:** pulsa **Contactar** en una publicación ajena. La conversación admite hasta 1000 caracteres por mensaje y sugerencias de puntos de encuentro. Consulta cambios incrementales cada segundo solo mientras la conversación está visible y la app está en primer plano, y muestra «Visto» cuando la otra persona leyó el mensaje. También puedes usar Actualizar. La bandeja muestra los mensajes sin leer. Los textos se conservan en el campo si falla el envío.
- **Notificaciones:** abre el destino de un aviso o pulsa **Marcar estas como leídas**. Los destinos del catálogo, pedidos y conversaciones se abren en pantallas nativas; los avisos administrativos se consultan en la web.
- **Perfil:** cambia nombre, carrera, biografía y fotografía. La imagen admite hasta 2 MB; el centro académico se deriva de la carrera. La configuración de seguridad permanece en la web.

Para probar ambas partes de una operación con un solo emulador:

1. En el móvil entra con **movil@edu.uaa.mx** / **EcoGalloDemo123**.
2. En el navegador del equipo entra con **companero-demo@edu.uaa.mx** / **EcoGalloDemo123**. Es otra cuenta ficticia que solo se crea al iniciar el servidor demo aislado.
3. Busca **Libro para probar pedidos** en el móvil. Esta publicación ficticia se crea una sola vez junto con la segunda cuenta. Prueba Contactar y responde desde la web.
4. Desde el detalle pulsa **Comprar · elegir forma de pago**. En la pantalla siguiente puedes elegir efectivo o tarjeta ficticia. Para esta última completa primero teléfono confirmado y referencia ficticia del vendedor en ambas cuentas como se explica arriba; selecciona **Tarjeta ficticia · simulación**, introduce solo titular, últimos cuatro y vencimiento ficticios y confirma. Se reserva el artículo y aparece un pedido con pago ficticio retenido. No se pide RFC ni cuenta bancaria completa.
5. Desde la web del vendedor marca la entrega. En el móvil actualiza el pedido y pulsa **Confirmar recepción**. El artículo queda vendido y el saldo ficticio aparece en la cuenta del vendedor.
6. Con otras publicaciones de prueba, revisa las alternativas: el vendedor puede reembolsar; el comprador puede abrir una disputa con un motivo de al menos diez caracteres. La cuenta **revision@edu.uaa.mx** / **EcoGalloRevision123** resuelve las disputas desde la administración web.
7. En una donación o trueque propio aprobado, usa **Marcar entregado** desde Mis publicaciones; no se crea un pago. Revisa su efecto en Actividad e Impacto.

El detalle del pedido muestra únicamente las acciones autorizadas por el servidor para tu cuenta y estado. Las operaciones de pago enviadas por el móvil llevan una restricción de simulación que el servidor valida antes de contactar cualquier proveedor externo. Si te conectas a un servidor con Stripe o Mercado Pago, el móvil permite efectivo, pero el pago en línea y sus acciones financieras corresponden a la web. No se abren automáticamente enlaces de checkout ni se integran claves de pago en el APK.

Si se corta la conexión al confirmar una operación, actualiza su detalle antes de repetirla. Los estados y las autorizaciones del backend determinan el resultado; no se muestra una confirmación de éxito sin respuesta del servidor.

## Conexión y seguridad

- La dirección inicial es `http://127.0.0.1:8080`. El botón de conexión permite corregirla; cambiarla cierra la sesión local. El arranque normal recuerda solo la dirección, sin guardar contraseñas ni cookies.
- `adb reverse tcp:8080 tcp:8080` permite llegar al backend por emulador o teléfono Android USB sin abrir el servidor a la red local. El script acepta el serial de un teléfono conectado.
- HTTP está limitado en depuración a 127.0.0.1, localhost y 10.0.2.2. El APK local de perfil, compilado explícitamente con `LOCAL_NETWORK_BUILD=true`, también admite IP privadas 10.x, 172.16–31.x y 192.168.x. Las direcciones públicas requieren HTTPS y la compilación release conserva HTTPS obligatorio.
- Se usa la cookie de sesión existente y el token CSRF del backend. No se relajan sus controles. La app guarda la sesión solamente en memoria y no guarda contraseñas en disco. Al cerrar completamente el proceso debes volver a entrar.
- Las peticiones de API no siguen redirecciones y las fotos se aceptan del mismo servidor. Las imágenes tienen tamaño de decodificación limitado para reducir memoria.
- No se integran SDK de pagos ni claves Stripe en la app. La demo fuerza pagos simulados y desactiva SMTP, Stripe real y tareas programadas. No mueve dinero.
- Este proyecto no está preparado para publicar en Play Store: falta firma de distribución y configurar un backend HTTPS si se desea salir de la tesina local.

## Validación para desarrollo

Desde `mobile/`:

```powershell
flutter pub get
flutter analyze
flutter test
```

Con el servidor demo y el emulador encendidos, desde la raíz configura el túnel (o ejecuta primero el script móvil):

```powershell
& "$env:LOCALAPPDATA/Android/Sdk/platform-tools/adb.exe" -s emulator-5554 reverse tcp:8080 tcp:8080
cd mobile
flutter test integration_test/demo_flow_test.dart -d emulator-5554
```

La prueba de integración requiere la demo y sus credenciales; no debe apuntarse a una cuenta real. Las pruebas locales comprueban cookie/CSRF, restricciones de conexión, sesión vencida y navegación acceso → búsqueda → detalle → salida. Gradle tiene límite de heap de 2 GB y dos workers para este equipo; el primer build también consume memoria fuera de ese heap.

Para verificar publicaciones sin modificar tu demo, desde la raíz del repositorio:

```powershell
.venv/Scripts/python.exe tools/test_mobile_posts.py
```

Este ejecutor levanta un servidor temporal en 127.0.0.1:8081, crea cuentas de autor, otro estudiante y revisor, configura el túnel del emulador y ejecuta `posts_flow_test.dart`. Verifica subida real de imágenes con el selector sustituido por fotos de prueba, conservación/reemplazo de fotos, revisión, catálogo, pausa, reanudación, donación, trueque y rechazo de acciones de otra cuenta. Al terminar elimina la base temporal y el túnel de 8081; conserva el servidor del usuario en 8080. Acepta un serial como argumento si no es `emulator-5554`.

Para una comprobación manual adicional del selector nativo, define `$env:ECOGALLO_NATIVE_PICKER_CHECK='1'` antes de ejecutar ese script: la prueba esperará hasta tres minutos a que elijas una foto y confirmes en la galería del emulador. Después quita la variable con `Remove-Item Env:ECOGALLO_NATIVE_PICKER_CHECK`.

Versiones utilizadas: Flutter 3.50.1 / Dart 3.14.0, Android SDK 36 y NDK 30.0.16248370 (el ya instalado en este equipo). Este SDK de Flutter usa `material_ui` para Material. `pubspec.lock` fija las dependencias resueltas de la app.

El recorrido de comunidad y pedidos utiliza la misma infraestructura temporal:

```powershell
.venv/Scripts/python.exe tools/test_mobile_posts.py emulator-5554 community
```

Comprueba favoritos, chat entre cuentas distintas, avisos de deseos y lectura de notificaciones, edición de perfil y avatar, actividad, impacto, saldo, compra y confirmación, reembolso, disputa y resolución, y cierre de una donación. Verifica que un tercero no pueda consultar pedidos y que un comprador no ejecute acciones del vendedor. Las operaciones se realizan exclusivamente sobre cuentas y base temporales del puerto 8081.

## Revisión de estabilidad móvil

La app admite vertical y horizontal sin bloquear el giro. Se corrigieron desbordamientos del acceso, la verificación pendiente y el chat con poco espacio, teclado o texto grande. Los borradores de los formularios y del chat permanecen al girar mientras el proceso siga abierto. Se evita duplicar rutas y confirmaciones mediante toques repetidos; enfocar un campo sin cambiar su texto ya no marca el formulario como modificado.

Los contadores de mensajes y notificaciones se actualizan cada cinco segundos y al volver a la app. Las bandejas abiertas se consultan cada 15 segundos y el chat cada segundo mediante cambios incrementales; las consultas periódicas se suspenden en segundo plano y las de cada bandeja también al abrir otra pantalla. Leer una conversación o una notificación actualiza los contadores. Abrir una notificación marca únicamente esa; «Marcar estas como leídas» afecta a las que ya se muestran, hasta 50, sin marcar avisos nuevos que lleguen durante la petición. La API verifica que pertenezcan a la cuenta autenticada.

Cerrar sesión sin red elimina el acceso y las credenciales de memoria del dispositivo, y muestra que no pudo confirmar la revocación en el servidor. Las respuestas de una sesión o conexión anterior se descartan. Se impiden avisos a controladores ya cerrados y se rechazan imágenes con direcciones inválidas, credenciales o un origen externo. El chat solicita una vista nueva después de enviar si había un sondeo anterior pendiente, para mostrar el mensaje enviado.

La verificación local incluye 47 pruebas Flutter y una matriz de 336 casos: 21 pantallas, cuatro tamaños/orientaciones, texto normal o al 180 %, y teclado visible u oculto. Las pruebas del servidor comprueban, entre otros controles, permisos, CSRF, proveedores de pagos y lectura selectiva de notificaciones. Estas comprobaciones acotan los casos revisados; no certifican ausencia total de fallos ni sustituyen probar un teléfono físico.

Para repetir la prueba Android de giro real y cierre de sesión sin conexión:

```powershell
.venv/Scripts/python.exe tools/test_mobile_posts.py emulator-5554 stability
```

Utiliza cuentas y servidor temporales de 8081, gira Android mediante Flutter, conserva un borrador, descarta el formulario y comprueba que salir sin red no deja una cookie de acceso. Solicita el teclado del sistema y registra su espacio visible; con el teclado físico del equipo el emulador puede no desplegar el virtual. La matriz de pruebas local sí reserva el espacio del teclado virtual en ambas orientaciones.

Los recorridos Android disponibles son `stability`, `community`, `posts` y `extended`. El último prueba aceptación de términos, confirmación de teléfono con código local, referencia ficticia, carrito, efectivo, cancelación, tarjeta ficticia y consulta de datos personales. Se ejecuta con `.venv/Scripts/python.exe tools/test_mobile_posts.py emulator-5554 extended`. El selector de imágenes se sustituye por archivos de prueba en los recorridos automatizados; el selector nativo tiene la comprobación adicional descrita arriba. Las pruebas no modifican los datos del servidor demo de 8080.

Después de actualizar estos archivos, reinicia el backend demo con `./run_mobile_demo.bat` para cargar la lectura selectiva de notificaciones y vuelve a ejecutar `./run_mobile.bat`. Los avisos son internos: recibirlos en la barra de Android o con la app cerrada requeriría integrar notificaciones push, que no forma parte de esta demo.

## APK independiente: datos principales, Wi-Fi y alternativa USB

El APK se instala una sola vez. No incorpora la base de datos: tanto la web como el móvil usan el servidor de la PC. El móvil admite Android 7.0 o posterior. La PC necesita el entorno Python del proyecto; para crear otro APK necesita Flutter/Android SDK, pero para volver a conectar por USB solo se usa el ADB ya instalado.

### Obtener e instalar el APK

Desde la raíz del repositorio ejecuta `./crear_apk_local.bat`. El resultado es `artifacts/mobile/ECO-GALLO-local.apk`, un APK de perfil optimizado para pruebas de tesina, firmado con la clave de pruebas de este equipo, con soporte ARM de teléfono y x64. No es una distribución de Play Store. Las actualizaciones deben conservar la misma firma para instalarse encima de la versión anterior.

Copia ese archivo al teléfono y ábrelo. Android puede pedir permitir la instalación desde la aplicación que lo abre (navegador o gestor de archivos). También se puede descargar en la misma Wi-Fi desde `http://IP-DE-LA-PC:8080/descargas/ecogallo-local.apk` una vez arrancado el servidor siguiente. La ruta ofrece únicamente ese APK, no archivos de datos o secretos del proyecto.

### Arrancar con los registros del proyecto principal

1. Detén con Ctrl+C el servidor anterior del puerto 8080, incluida la demo. No ejecutes ambos a la vez.
2. En la raíz ejecuta `./servidor_movil.bat` y deja la terminal abierta. No requiere compilar la app ni descargar paquetes en cada arranque.
3. Usa las cuentas y contraseñas existentes del proyecto. Las cuentas públicas `movil`, `revision` y `companero-demo` pertenecen a la demo aislada y no se crean aquí.
4. La web en `http://127.0.0.1:8080` y el móvil comparten `data/ecogallo.sqlite`, las fotos y `data/secret.key`. Si tu proyecto usa otra carpeta de datos, arranca `./servidor_movil.bat --data "C:\ruta\a\los\datos"` con esa carpeta existente completa.

El script comprueba que ya existan la base y su secreto, hace un respaldo consistente de SQLite en `data/backups/antes-movil-*.sqlite` y después arranca Waitress sin depurador. No agrega cuentas, publicaciones de demo ni administradores nuevos, y no cambia contraseñas. Los cambios que hagas desde el móvil sí afectan a los registros del proyecto principal. Los pagos nuevos quedan en simulación, sin claves Stripe ni conciliación automática; las operaciones anteriores de proveedor externo conservan sus restricciones y no se convierten en pagos simulados.

No se muestran códigos de acceso de desarrollo en la red. Para entrar por código, recuperar contraseña o registrar una cuenta nueva necesitas conservar una configuración SMTP válida; sin SMTP usa cuentas existentes con contraseña. No se promete correo real sin un servicio configurado.

### Conectar por Wi-Fi

1. Conecta PC y teléfono a una red privada de confianza. No hace falta salida a Internet para usar la API, pero el router debe permitir comunicación entre dispositivos.
2. El servidor muestra posibles direcciones; también puedes ejecutar `ipconfig` y buscar la IPv4 del adaptador Wi-Fi. Evita direcciones de adaptadores virtuales, como VirtualBox. La IP puede cambiar al cambiar de red.
3. Desde el navegador del teléfono abre `http://IP-DE-LA-PC:8080/api/health`; debe devolver `{"ok":true}`. En esta revisión la PC tenía `192.168.100.18` en Wi-Fi; comprueba que siga siendo esa dirección.
4. Abre ECO-GALLO > Configurar conexión y escribe `http://IP-DE-LA-PC:8080`. Pulsa Conectar e inicia sesión con una cuenta del proyecto principal. La dirección se guarda, pero la sesión se mantiene solo en memoria.
5. Si Windows bloquea la conexión y estás en tu propia red de confianza, configura esa red como Privada. En PowerShell como administrador, desde la raíz del proyecto, ejecuta `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\allow_mobile_lan.ps1`. El script permite únicamente TCP 8080 al Python del proyecto desde la subred local y con perfil Privado; no desactiva el firewall. No se ejecuta automáticamente. Para retirar la regla usa `Remove-NetFirewallRule -Name ECO-GALLO-Tesina-8080-Private` como administrador.

El modo local usa HTTP sin cifrar. Úsalo para la tesina en una red controlada o por USB; no abras este puerto hacia Internet. Para una distribución pública se necesita HTTPS y firma de distribución.

### Conectar por cable sin reinstalar

1. Mantén el mismo servidor encendido. Si solo usarás cable, puedes arrancarlo con `./servidor_movil.bat --usb`: escucha únicamente en la propia PC.
2. Conecta un cable de datos, activa Depuración USB y autoriza esta PC en el teléfono. Es una preparación inicial; algunos teléfonos piden de nuevo la autorización al reconectar.
3. Ejecuta `./conectar_movil_usb.bat`. Detecta el único dispositivo autorizado y crea `adb reverse tcp:8080 tcp:8080`. Si hay varios dispositivos, indica el identificador: `./conectar_movil_usb.bat SERIAL`.
4. En la app selecciona `http://127.0.0.1:8080` en Configurar conexión. Si cambias de dirección, vuelve a iniciar sesión.
5. Al reconectar el cable o reiniciar, repite únicamente el script USB. No reinstala, no compila, no modifica la base y no necesita Internet ni Wi-Fi. El túnel puede perderse al desconectar; no es una conexión permanente del teléfono.

Si una red de escuela o de invitados aísla dispositivos, estar en el mismo Wi-Fi no basta. Usa el cable; no cambies la seguridad de esa red ni abras puertos del router. La computadora debe permanecer encendida y sin suspensión en ambos métodos.

### Comprobación con los datos principales

- Confirma que una publicación existente se ve igual en la web y en el móvil, con la misma cuenta y permisos.
- Cambia tu biografía desde el teléfono y compruébala en la web. Usa una publicación propia prescindible para revisar fotos, revisión, edición y pausa.
- Abre dos cuentas existentes, una en el teléfono y otra en la web: intercambia mensajes y prueba deseos/notificaciones. El administrador existente aprueba publicaciones desde la web.
- Prueba compras solo como simulación con publicaciones destinadas a prueba; modifican estados y saldo ficticio de la base principal.
- Cambia entre Wi-Fi y USB desde Configurar conexión. Reinicia la app para comprobar que recuerda la dirección y verifica giro, teclado, notificaciones internas y errores de desconexión.
