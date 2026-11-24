# Presentación de ECO-GALLO por USB

La presentación usa el APK ya instalado y el servidor de la computadora, compartido con la web. El teléfono no guarda ni abre SQLite: llama a la API Flask y esta trabaja con la base principal. No es necesario Internet para catálogo, fotografías, chat, notificaciones internas y operaciones simuladas por USB.

## Preparación antes de entrar al salón

- Conserva el APK local y este repositorio en la computadora. Deja instalados Python, el entorno `.venv`, Android SDK Platform Tools y los controladores USB. Comprueba que el cable transfiere datos, no solamente carga.
- Prepara tres cuentas existentes con contraseña: comprador, vendedor y administrador. Verifica las contraseñas y los roles antes; no los cambies durante la exposición. Si tienen segundo factor, lleva la aplicación autenticadora o un código de recuperación sin mostrarlo al público.
- Usa una publicación de venta disponible, propia del vendedor y destinada a la demostración. No uses artículos reservados, vendidos o de otra operación importante. Prepara también una imagen JPG o PNG pequeña para publicar y un deseo que coincida con el título que vas a crear.
- Las operaciones de la exposición modifican los datos principales. Conserva un respaldo privado completo con su clave. No restaures un respaldo durante la presentación ni compartas la carpeta `data/` con el código público.
- Mantén la computadora conectada a corriente y evita la suspensión. Si usarás teléfono físico, cierra el emulador y Android Studio para liberar memoria; el APK instalado no necesita Flutter en ejecución.
- No dependas del correo para entrar. Registro, recuperación y códigos por correo necesitan SMTP válido y conexión al servicio; el arranque con datos principales no muestra códigos de desarrollo.

## Arranque en dos terminales

Detén desde su terminal cualquier servidor anterior del puerto 8080. En la primera terminal PowerShell:

```powershell
cd C:\Users\reyli\Documents\GIT\eco-gallo
.\servidor_movil.bat --usb
```

Este modo solo escucha en la propia PC, sin abrir la red ni cambiar el firewall. Usa `data/ecogallo.sqlite`, las fotos y el secreto principal, crea un respaldo SQLite previo y fuerza los pagos nuevos a simulación. Si tus datos están en otra carpeta existente, añade `--data "C:\ruta\datos"`; no selecciones `data/mobile-demo` si quieres mostrar los registros principales.

En otra terminal:

```powershell
cd C:\Users\reyli\Documents\GIT\eco-gallo
.\conectar_movil_usb.bat
```

Con varios dispositivos, comprueba `flutter devices` y especifica uno:

```powershell
.\conectar_movil_usb.bat emulator-5554
# Para el teléfono, sustituye emulator-5554 por su identificador real.
```

El script solo crea el túnel, sin compilar ni reinstalar. Desbloquea el teléfono y autoriza la depuración USB cuando Android lo solicite. El túnel debe repetirse después de desconectar o reiniciar el dispositivo.

Abre [la comprobación del servidor](http://127.0.0.1:8080/api/health) en la PC: debe devolver `{"ok":true}`. Abre [la web](http://127.0.0.1:8080) y el APK ECO-GALLO. En la app, Configurar conexión debe indicar `http://127.0.0.1:8080`. La dirección se recuerda; cambiarla o cerrar completamente el proceso requiere iniciar sesión nuevamente.

Si necesitas reinstalar, abre `artifacts/mobile/ECO-GALLO-local.apk` en el teléfono y permite la instalación desde el gestor de archivos. Para el emulador puedes instalar ese mismo APK con el `adb.exe` de Android SDK:

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" -s emulator-5554 install -r .\artifacts\mobile\ECO-GALLO-local.apk
```

Después abre ECO-GALLO desde su icono. Para reconstruir el APK, utiliza `crear_apk_local.bat`; no es necesario hacerlo en cada presentación. Mantén la firma de este equipo para actualizar la instalación existente.

## Recorrido sugerido de 10 a 15 minutos

| Paso | Acción | Qué demostrar |
|---|---|---|
| 1 | Entra en el móvil como comprador. | Acceso, identidad, catálogo y búsqueda sobre los registros existentes. |
| 2 | Abre una publicación, desliza sus fotos, guárdala y consulta Favoritos. | Datos, fotografías y preferencias compartidos con la web. |
| 3 | Desde otra cuenta publica un material con la imagen preparada. | Validación del formulario y estado En revisión. |
| 4 | En la web del administrador aprueba el material. Actualiza el móvil. | Moderación y permisos: el comprador no ve publicaciones pendientes. |
| 5 | Abre Contactar y responde desde la web del vendedor. | Chat entre participantes y actualización de mensajes. |
| 6 | Revisa el deseo preparado y Notificaciones al aprobar el material coincidente. | Avisos internos, contador y lectura individual. |
| 7 | Compra una venta disponible mediante pago simulado. El vendedor marca entrega en la web y el comprador confirma en el móvil. | Estado del pedido, historial y saldo ficticio. No se mueve dinero real. |
| 8 | Cambia una biografía y compruébala en la web. Consulta Actividad e Impacto. | Persistencia, trazabilidad e impacto estimado. |
| 9 | Gira el dispositivo mientras escribes un borrador y vuelve a vertical. | Adaptación y conservación del texto mientras el proceso está abierto. |
| 10 | Cierra sesión y explica las limitaciones. | Cierre del recorrido y alcance de la tesina. |

Para tener comprador, vendedor y administrador abiertos, usa el móvil y dos perfiles separados del navegador; dos ventanas normales del mismo perfil comparten la sesión. Actualizar un pedido manualmente después de una acción en la web evita esperar una actualización de pantalla que no es automática en ese detalle.

No compres con el propio vendedor. Para repetir una compra, usa otra publicación: al completar la anterior queda vendida. Disputas y reembolsos se pueden explicar o mostrar con otra operación preparada; no alargues el recorrido principal.

## Fallas posibles y recuperación

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| El puerto 8080 está ocupado. | Quedó otro servidor abierto. | Detén únicamente el servidor anterior desde su terminal y arranca `servidor_movil.bat --usb`. |
| La app muestra Sin conexión. | Servidor apagado, suspensión o túnel perdido. | Comprueba `/api/health` en la PC, reconecta el cable, repite el script USB y pulsa Reintentar. |
| El dispositivo no aparece o está `unauthorized`. | Cable de carga, bloqueo o autorización USB pendiente. | Desbloquea, acepta la autorización y prueba otro cable/puerto. Revisa el controlador del fabricante. |
| El script indica varios dispositivos. | Teléfono y emulador conectados. | Indica el identificador explícitamente; no dependas de la detección automática. |
| Aparecen cuentas o artículos distintos. | Arrancaste la demo aislada o elegiste otra carpeta de datos. | Verifica en la terminal la ruta `data` y usa tus cuentas principales; no borres ninguna base para corregirlo. |
| No llega un código de acceso. | No hay SMTP o Internet para el correo. | Usa una cuenta con contraseña ya comprobada. No dependas del registro en directo. |
| No puedes entrar con la contraseña. | Contraseña incorrecta, bloqueo temporal o segundo factor. | Usa las credenciales comprobadas. No repitas intentos; prepara una cuenta alternativa autorizada. |
| La publicación no aparece en el catálogo. | Pendiente de moderación, pausada o filtro activo. | Revísala en Mis publicaciones, apruébala con el administrador y limpia filtros. |
| No se puede comprar o editar. | Es propia, está reservada/vendida o pertenece a un proveedor externo. | Usa una venta ajena, disponible y destinada a la prueba simulada. |
| La foto no carga o no se puede enviar. | Formato/tamaño, selección cancelada o archivo inaccesible. | Usa JPG/PNG pequeño; revisa miniaturas antes de enviar. Publicaciones: máximo cinco fotos; avatar: hasta 2 MB. |
| Se corta la conexión después de Enviar/Comprar. | El servidor pudo completar la operación antes del corte. | Reconecta y revisa Mis publicaciones o Compras y ventas antes de repetirla. |
| Notificaciones o chat tardan. | Actualización periódica o app en segundo plano. | Vuelve a primer plano o pulsa Actualizar. Chat: 8 s; bandejas: 15 s; contadores: 30 s. |
| No hay notificación en la barra de Android. | Solo existen notificaciones internas. | Abre Notificaciones dentro de ECO-GALLO; push con la app cerrada no está integrado. |
| Se pierde un borrador al cerrar la app. | Los textos permanecen en memoria, no en disco. | No cierres el proceso durante la demostración; prepara textos breves para repetirlos. |
| El emulador va lento. | Falta de RAM durante compilación o varias herramientas abiertas. | Usa el APK ya generado, cierra compilaciones y herramientas innecesarias, o cambia al teléfono físico. |
| El APK no se actualiza. | Firma distinta o instalación restringida por Android. | Usa el APK de este equipo. No desinstales sin considerar que se perderán las preferencias locales. |

No desactives el firewall ni abras puertos del router para la presentación por USB. Si necesitas continuar sin móvil, la web del mismo servidor permite mostrar el flujo principal; las capturas guardadas sirven como evidencia adicional, no como sustituto de una prueba en vivo.

## Qué explicar como alcance

- Android es el cliente móvil incluido; iOS y publicación en tiendas quedan fuera.
- Las operaciones financieras son simuladas; no se pide RFC ni cuenta bancaria y no se mueve dinero.
- Administración, verificación documental y configuración de seguridad se realizan desde la web. El móvil respeta los roles y el segundo factor ya configurado.
- Los avisos son internos. La app necesita servidor disponible y no tiene un modo de trabajo sin conexión ni sincronización posterior.
- Las cifras de CO2 son estimaciones orientativas por categoría.
- Las pruebas documentadas cubren los casos verificados; no certifican ausencia absoluta de fallos ni preparación para producción.

## Cierre

Al terminar, cierra sesión, detén el servidor con Ctrl+C y desconecta el cable. Los registros de la presentación se conservan en la base principal. Conserva el respaldo cifrado y su clave de forma privada; no los entregues dentro del paquete público de código/APK.
