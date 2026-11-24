# Evidencias de las pruebas Android

Capturas de la ventana del emulador Eco-Gallo durante las pruebas del servidor temporal de 8081. Se utilizaron cuentas e imágenes ficticias; estas capturas no muestran los registros principales del usuario.

1. [Confirmación de pedido simulado](01-confirmacion-pedido.png): aviso y confirmación de recepción, con indicación de saldo ficticio y sin movimiento de dinero real.
2. [Selector Android real](02-selector-android.png): selección de una imagen de libro de prueba. Después de confirmar se completó el recorrido de publicación, revisión, edición y pausa/reanudación.

La prueba de selector real se ejecutó con `ECOGALLO_NATIVE_PICKER_CHECK=1` y `tools/test_mobile_posts.py emulator-5554 posts`. Los otros recorridos fueron `stability`, `community` y `posts`; todos terminaron con `All tests passed!`. Los resultados del cierre se resumen en [ENTREGA.md](../../ENTREGA.md). Los registros completos se conservan localmente en `mobile/build/cierre-*.log`, excluidos de Git porque pueden contener códigos efímeros de las cuentas de prueba.
