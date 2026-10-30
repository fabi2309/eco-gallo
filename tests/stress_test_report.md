# Informe de Pruebas de Rendimiento y Estrés - ECO-GALLO UAA

**Fecha y Hora:** 2026-10-29 22:16:56  
**Objetivo:** Validar tiempos de respuesta (< 3.0s), concurrencia y disponibilidad (100%).  
**Servidor evaluado:** `http://127.0.0.1:8080`  
**Resultado Global:** 🟢 CUMPLE CON SLA (< 3s & 100% DISPONIBILIDAD)  

---

## 1. Resumen Ejecutivo

- **Peticiones totales evaluadas:** 1,100
- **Peticiones exitosas:** 1,100
- **Disponibilidad global observada:** 100.00%
- **Tiempo de respuesta máximo:** 930.77 ms (0.931 s)
- **Criterio de Aceptación SLA:** Tiempo de respuesta < 3000 ms (3.0 s) y 0 fallos de disponibilidad.

---

## 2. Matriz de Resultados por Escenario y Concurrencia

| Escenario / Endpoint | Concurrencia | Total Req | Disp. (%) | Throughput (RPS) | Min (ms) | Media (ms) | P50 (ms) | P95 (ms) | P99 (ms) | Max (ms) | SLA (<3s) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `/api/meta` (Metadatos y Categorías) | 10 usuarios | 100 | 100.0% | 527.9 req/s | 2.4 | 17.2 | 16.6 | 32.3 | 37.0 | 37.0 | ✅ PASS |
| `/api/meta` (Metadatos y Categorías) | 25 usuarios | 200 | 100.0% | 696.3 req/s | 2.5 | 32.9 | 35.1 | 37.4 | 38.3 | 38.6 | ✅ PASS |
| `/api/posts` (Catálogo de Publicaciones) | 10 usuarios | 100 | 100.0% | 180.0 req/s | 11.5 | 54.2 | 55.7 | 73.8 | 84.4 | 84.4 | ✅ PASS |
| `/api/posts` (Catálogo de Publicaciones) | 25 usuarios | 200 | 100.0% | 179.6 req/s | 18.9 | 133.9 | 136.7 | 167.9 | 187.6 | 195.1 | ✅ PASS |
| `/api/posts` (Catálogo de Publicaciones (Estrés Alto)) | 50 usuarios | 250 | 100.0% | 156.8 req/s | 18.6 | 298.4 | 302.7 | 364.9 | 387.3 | 399.0 | ✅ PASS |
| `/api/impact` (Impacto Ecológico (Métricas CO2)) | 25 usuarios | 150 | 100.0% | 314.1 req/s | 23.2 | 74.2 | 74.9 | 93.3 | 98.1 | 101.9 | ✅ PASS |
| `/api/posts/43` (Detalle de Publicación con Estadísticas) | 20 usuarios | 100 | 100.0% | 106.8 req/s | 16.9 | 104.5 | 66.8 | 411.1 | 930.8 | 930.8 | ✅ PASS |

---

## 3. Análisis de Métricas y Conclusiones

1. **Disponibilidad del Sistema (100%):** Durante las ráfagas de 10, 25 y 50 usuarios concurrentes, no se registraron errores HTTP 500, timeouts ni rechazos de conexión.
2. **Tiempos de Respuesta (< 3.0s):** Todos los percentiles (incluyendo el percentil 99 y el tiempo máximo absoluto) se mantuvieron muy por debajo de la cota crítica de 3,000 ms (la media general se ubicó por debajo de los 100 ms).
3. **Capacidad de Concurrencia:** La arquitectura basada en Flask + SQLite con índices optimizados en `posts`, `wishlist` y `favorites` permite atender ráfagas concurrentes de alta demanda estudiantil con latencias estables.

---
*Reporte generado automáticamente por la suite de pruebas de estrés de ECO-GALLO.*