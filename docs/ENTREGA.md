# Entrega técnica — ECO-GALLO

Fecha de revisión: 17 de noviembre de 2026. Cambios aplicados sobre `rama-rey1`, que ya contenía el merge Stripe `debdc20`. Los cambios permanecen locales para revisión; no se publicaron ni se activaron pagos reales.

## Resultado

Quedó operativo y comprobado el flujo de demostración sin RFC, cuenta bancaria ni dinero real. El marketplace conserva venta, trueque, donación, mensajería, moderación y administración. Se corrigieron los errores reproducidos en las auditorías y se añadieron controles y pruebas de regresión.

La activación real de Stripe sigue pendiente de la cuenta bancaria, la verificación que Stripe requiera y la validación de extremo a extremo con las cuentas del operador y vendedores. El código no inventa ni evita información fiscal/bancaria. Producción deja los pagos deshabilitados por defecto.

## Qué hace el sistema

1. Estudiantes de los dominios UAA configurados entran por código al correo o contraseña. El registro pide nombre y carrera y deriva el centro académico. Pueden activar 2FA y guardar códigos de recuperación de un solo uso.
2. Egresados confirman su correo y entregan un documento privado para revisión. Hasta su aprobación no acceden al marketplace. El documento activo se elimina al resolver; las copias históricas cifradas siguen su retención documentada.
3. Los usuarios publican ventas, trueques o donaciones en tres pasos. El sistema valida y normaliza fotos, solicita moderación y permite pausar/reanudar. Cambiar texto o fotos exige revisión nueva. Las publicaciones pendientes son visibles para su autor y administración.
4. El catálogo tiene búsqueda, sugerencias, filtros y paginación. Favoritos y deseos permiten seguir materiales y recibir alertas después de aprobar una publicación o su reducción de precio.
5. Los participantes pueden conversar por publicación, consultar notificaciones e historial y reportar contenido o usuarios. Se muestran puntos de encuentro y estimaciones orientativas de impacto.
6. En una venta de demostración, el comprador crea una orden, el vendedor marca entrega y el comprador confirma recepción. Las disputas las resuelve un administrador y los reembolsos vuelven a dejar disponible el artículo. Todo es ficticio y está identificado como tal.
7. Stripe preparado incorpora Checkout, Connect, firma de webhooks, idempotencia, continuación y cancelación verificadas de Checkout, sincronización y conciliación periódica. Los resultados inciertos y las operaciones en revisión bloquean acciones opuestas y borrado de participantes. Un reembolso pendiente no se anuncia como concluido; uno fallido requiere revisión.
8. Administración revisa publicaciones y egresados, atiende reportes y disputas, consulta usuarios con paginación, métricas y gráficas locales, y gestiona respaldos cifrados.

## Cambios principales

- Servidor Waitress para producción, sin depuración, contenedor sin privilegios, volumen persistente y healthcheck que respeta el Host configurado.
- Validación de producción: HTTPS, cookies Secure, secreto persistente y SMTP; rechazo de DEV, simulación y claves live fuera de producción o sin habilitación explícita.
- Protección CSRF por sesión y verificación de origen, cabeceras consistentes también sin Java, validación de JSON y límite de autenticación. El contador de fallos de contraseña se actualiza atómicamente. Las IP de proxy solo se confían con un token compartido.
- Restablecimiento de contraseña con una autorización reciente por correo, después de 2FA cuando corresponde; vence en diez minutos, se consume al usarla y revoca otras sesiones y desafíos.
- Estados financieros durables y asociados al proveedor original. Reintentos de una misma transferencia/reembolso no habilitan la operación contraria. Soporte de objetos reales del SDK Stripe 16 y de firmas verificadas.
- Webhooks aplicados junto a su registro de deduplicación, recuperación de sesiones todavía no persistidas y procesamiento de reembolsos/contracargos relevantes.
- Prohibición de borrar usuarios con cualquiera de los estados financieros abiertos, y bloqueo de restauración web cuando hay historial Stripe para evitar repetir pagos históricos.
- Respaldos ZIP v2 con carga y metadatos autenticados, rutas seguras tanto en Windows como en Linux, límites de extracción, mantenimiento, copia preventiva y reversión ante fallas. La clave se custodia por separado. Se invalidan las sesiones históricas al restaurar.
- Corrección de fechas Unix en estadísticas; reemplazo del CDN de gráficas por gráficos locales accesibles; etiquetas de todos los estados; publicaciones en revisión en Mis publicaciones; acceso a Administración desde Perfil en pantallas pequeñas.
- Paginación del catálogo, publicaciones propias, órdenes y usuarios. Validación de precios extremos sin errores 500 y control de solicitudes de búsqueda obsoletas.
- Decodificación y reescritura de imágenes, eliminación de metadatos y contenido añadido, validación completa del lote y limpieza de fotos sustituidas o fallidas.
- Limpieza de conflictos en `.gitignore`, requisito Java 21 documentado y arranques de desarrollo en un entorno `.venv` del proyecto.
- CI ampliada para recoger todos los tests, compilar el gateway y ejecutar la API a través de él. Nuevas pruebas HTTP sobre Waitress disponibles localmente.
- Documentación de configuración de Stripe, producción sin pagos, conservación de claves, límites de respaldo y recuperación financiera.

## Comprobaciones ejecutadas

| Comprobación | Resultado |
|---|---|
| `python -m pytest tests -q` | **69 aprobadas**, incluyendo regresiones financieras, firmas reales con el SDK, CSRF, permisos, recuperación y migración de una base anterior. |
| Suite API por HTTP real contra Waitress y una base temporal | **167 comprobaciones aprobadas**, resultado TODO OK. |
| Flake8 sobre backend, pruebas y arranques | **0 errores**. |
| Sintaxis de todos los módulos JavaScript con `node --check` | Sin errores. |
| Bandit con el filtro de CI (`-ll -ii`) | **0 hallazgos medios/altos reportables**. Las consultas dinámicas permitidas solo usan estructura constante y parámetros enlazados. |
| pip-audit de los requisitos finales | **Sin vulnerabilidades conocidas detectadas**. Se actualizó Pillow a la serie corregida 13 tras detectar problemas en 12. |
| `git diff --check` | Sin errores de formato. |
| Navegador sobre datos ficticios | Acceso por contraseña, perfil guardado con CSRF, gráficas mensuales visibles, publicación en tres pasos y artículo En revisión visible al autor. |
| Arranque de producción en un proceso nuevo | Aplicación carga sin debug con pagos deshabilitados, sirve frontend, protege Host y aplica HSTS. |

Las pruebas usaron datos aislados; no modificaron la base real del proyecto, no enviaron correos reales y no movieron dinero. Las operaciones Stripe externas se sustituyeron por respuestas controladas, pero la prueba de firma sí utiliza la implementación real del SDK.

## Lo que aún requiere configuración o validación externa

- **Pagos reales:** aprobación/configuración de Stripe, CLABE/cuenta bancaria, datos fiscales y de identidad solicitados, vendedores habilitados y pruebas reales de integración en Stripe Test. Las simulaciones no acreditan transferencias bancarias.
- **Publicación:** dominio, TLS/proxy, SMTP real y su entregabilidad, secreto persistente, administradores definitivos y volumen de datos. El responsable debe completar sus datos de contacto, aviso de privacidad y términos aplicables.
- **Operación:** copias externas cifradas y alertas del hosting para errores, espacio, antigüedad del respaldo y conciliaciones pendientes. El mecanismo integrado usa un solo proceso con hilos; varias réplicas necesitan coordinación externa.
- **Herramientas no disponibles localmente:** no se construyó el contenedor Docker ni se ejecutó Java en este equipo. Se revisó su configuración y se mantuvo la compilación Java 21 y construcción Docker en CI. Waitress sí se probó mediante HTTP real.

No se afirma ausencia absoluta de fallas ni certificación de seguridad. Las comprobaciones cubren los casos descritos y no reemplazan la validación con servicios y datos de producción.

## Cómo comprobarlo

En Windows ejecuta `run_dev.bat`. Se prepara `.venv`, se instalan dependencias y se abre el servidor local en http://localhost:8080. Usa el administrador configurado en `ECOGALLO_ADMINS` y un segundo correo institucional de prueba. Sin SMTP, en DEV el código aparece en pantalla. Publica un artículo, apruébalo desde Administración y completa la compra simulada con el otro usuario.

Para repetir las pruebas: instala `backend/requirements.txt` y `requirements-dev.txt` en tu entorno y ejecuta `python -m pytest tests -q` y `python tests/run_e2e.py`. El runner HTTP usa una base desechable y puede tardar alrededor de dos minutos por los tiempos de reenvío de códigos.

Para ponerlo en un servidor utiliza exclusivamente la configuración descrita en [OPERACION.md](OPERACION.md).
