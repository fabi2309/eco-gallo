import com.sun.net.httpserver.Headers;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;

/**
 * ECO-GALLO UAA · Gateway (Java puro, sin dependencias).
 *
 * - Sirve el frontend estático (HTML/CSS/JS nativo).
 * - Reenvía /api y /uploads al backend Flask (127.0.0.1:5000).
 * - Aplica cabeceras de seguridad, límite de tamaño y límite de ritmo
 *   por IP en /api/auth/* (frena el abuso de envío de códigos).
 *
 * Uso: java Gateway.java [puertoGateway] [puertoBackend] [carpetaFrontend]
 */
public class Gateway {
    static final long MAX_BODY = 26L * 1024 * 1024;
    static final Set<String> HOP = Set.of("connection", "content-length", "host", "expect",
            "upgrade", "transfer-encoding", "keep-alive", "te", "trailer", "proxy-authorization");
    static final Map<String, String> TYPES = Map.ofEntries(
            Map.entry("html", "text/html; charset=utf-8"), Map.entry("css", "text/css; charset=utf-8"),
            Map.entry("js", "text/javascript; charset=utf-8"), Map.entry("json", "application/json"),
            Map.entry("svg", "image/svg+xml"), Map.entry("png", "image/png"),
            Map.entry("jpg", "image/jpeg"), Map.entry("jpeg", "image/jpeg"),
            Map.entry("webp", "image/webp"), Map.entry("ico", "image/x-icon"),
            Map.entry("woff2", "font/woff2"), Map.entry("txt", "text/plain; charset=utf-8"));

    static final String CSP = "default-src 'self'; img-src 'self' data:; "
            + "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            + "font-src 'self' https://fonts.gstatic.com; script-src 'self'; "
            + "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'";

    static HttpClient client;
    static String backend;
    static Path webRoot;

    // Límite de ritmo: ventana de 60 s por IP para /api/auth/*
    static final int AUTH_LIMIT = Integer.parseInt(System.getenv().getOrDefault("ECOGALLO_AUTH_LIMIT", "30"));
    static final Map<String, long[]> hits = new ConcurrentHashMap<>();

    public static void main(String[] args) throws Exception {
        int port = args.length > 0 ? Integer.parseInt(args[0]) : 8080;
        int backPort = args.length > 1 ? Integer.parseInt(args[1]) : 5000;
        webRoot = Path.of(args.length > 2 ? args[2] : "../frontend").toAbsolutePath().normalize();
        backend = "http://127.0.0.1:" + backPort;
        client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5))
                .followRedirects(HttpClient.Redirect.NEVER).build();

        String bind = System.getenv().getOrDefault("ECOGALLO_BIND", "0.0.0.0");
        HttpServer server = HttpServer.create(new InetSocketAddress(bind, port), 128);
        server.createContext("/", Gateway::handle);
        server.setExecutor(Executors.newVirtualThreadPerTaskExecutor());
        server.start();
        System.out.println("  ECO-GALLO gateway en http://localhost:" + port
                + "  ->  backend " + backend + "  | frontend " + webRoot);
    }

    static void handle(HttpExchange ex) throws IOException {
        try {
            String path = ex.getRequestURI().getPath();
            if (path.startsWith("/api/") || path.startsWith("/uploads/")) {
                if (path.startsWith("/api/auth/") && !allow(clientIp(ex))) {
                    sendJson(ex, 429, "{\"ok\":false,\"message\":\"Demasiadas solicitudes. Espera un minuto.\"}");
                    return;
                }
                proxy(ex);
            } else {
                serveStatic(ex, path);
            }
        } catch (Exception e) {
            e.printStackTrace();
            try { sendJson(ex, 502, "{\"ok\":false,\"message\":\"Servicio no disponible. Intenta en un momento.\"}"); }
            catch (Exception ignore) { }
        } finally {
            ex.close();
        }
    }

    static String clientIp(HttpExchange ex) {
        return ex.getRemoteAddress().getAddress().getHostAddress();
    }

    static boolean allow(String ip) {
        long now = System.currentTimeMillis();
        long[] w = hits.compute(ip, (k, v) -> {
            if (v == null || now - v[0] > 60_000) return new long[]{now, 1};
            v[1]++;
            return v;
        });
        if (hits.size() > 10_000) hits.entrySet().removeIf(e -> now - e.getValue()[0] > 60_000);
        return w[1] <= AUTH_LIMIT;
    }

    // ---------------------------------------------------------------- proxy
    static void proxy(HttpExchange ex) throws IOException, InterruptedException {
        String method = ex.getRequestMethod();
        byte[] body = readLimited(ex.getRequestBody());
        if (body == null) { sendJson(ex, 413, "{\"ok\":false,\"message\":\"El archivo es demasiado grande.\"}"); return; }

        String q = ex.getRequestURI().getRawQuery();
        URI target = URI.create(backend + ex.getRequestURI().getRawPath() + (q != null ? "?" + q : ""));
        HttpRequest.Builder rb = HttpRequest.newBuilder(target).timeout(Duration.ofSeconds(30));
        for (Map.Entry<String, List<String>> h : ex.getRequestHeaders().entrySet()) {
            String k = h.getKey();
            if (k == null) continue;
            String lk = k.toLowerCase();
            if (HOP.contains(lk) || lk.equals("x-real-ip") || lk.equals("x-forwarded-for")) continue;
            for (String v : h.getValue()) rb.header(k, v);
        }
        rb.header("X-Real-IP", clientIp(ex)); // el backend confía solo en este valor
        boolean hasBody = body.length > 0 || method.equals("POST") || method.equals("PUT") || method.equals("PATCH");
        rb.method(method, hasBody ? HttpRequest.BodyPublishers.ofByteArray(body) : HttpRequest.BodyPublishers.noBody());

        HttpResponse<byte[]> r = client.send(rb.build(), HttpResponse.BodyHandlers.ofByteArray());
        Headers out = ex.getResponseHeaders();
        r.headers().map().forEach((k, vals) -> {
            if (!HOP.contains(k.toLowerCase())) vals.forEach(v -> out.add(k, v)); // conserva varios Set-Cookie
        });
        securityHeaders(out);
        if (!out.containsKey("Cache-Control") && ex.getRequestURI().getPath().startsWith("/api/"))
            out.set("Cache-Control", "no-store");
        byte[] data = r.body();
        ex.sendResponseHeaders(r.statusCode(), method.equals("HEAD") ? -1 : (data.length == 0 ? -1 : data.length));
        if (data.length > 0 && !method.equals("HEAD")) try (OutputStream os = ex.getResponseBody()) { os.write(data); }
    }

    static byte[] readLimited(InputStream in) throws IOException {
        ByteArrayOutputStream bo = new ByteArrayOutputStream();
        byte[] buf = new byte[16384];
        long total = 0;
        int n;
        while ((n = in.read(buf)) > 0) {
            total += n;
            if (total > MAX_BODY) return null;
            bo.write(buf, 0, n);
        }
        return bo.toByteArray();
    }

    // -------------------------------------------------------------- estático
    static void serveStatic(HttpExchange ex, String reqPath) throws IOException {
        String m = ex.getRequestMethod();
        if (!m.equals("GET") && !m.equals("HEAD")) { sendJson(ex, 405, "{\"ok\":false}"); return; }
        String rel = reqPath.equals("/") ? "index.html" : reqPath.substring(1);
        Path file = webRoot.resolve(rel).normalize();
        if (!file.startsWith(webRoot) || !Files.isRegularFile(file)) {
            if (rel.contains(".")) { sendJson(ex, 404, "{\"ok\":false,\"message\":\"No encontrado\"}"); return; }
            file = webRoot.resolve("index.html");
        }
        String name = file.getFileName().toString();
        String ext = name.contains(".") ? name.substring(name.lastIndexOf('.') + 1).toLowerCase() : "";
        byte[] data = Files.readAllBytes(file);
        Headers h = ex.getResponseHeaders();
        h.set("Content-Type", TYPES.getOrDefault(ext, "application/octet-stream"));
        h.set("Cache-Control", ext.equals("html") ? "no-cache" : "no-cache, must-revalidate");
        securityHeaders(h);
        ex.sendResponseHeaders(200, m.equals("HEAD") ? -1 : data.length);
        if (!m.equals("HEAD")) try (OutputStream os = ex.getResponseBody()) { os.write(data); }
    }

    static void securityHeaders(Headers h) {
        h.set("Content-Security-Policy", CSP);
        h.set("X-Content-Type-Options", "nosniff");
        h.set("X-Frame-Options", "DENY");
        h.set("Referrer-Policy", "same-origin");
        h.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
    }

    static void sendJson(HttpExchange ex, int code, String json) throws IOException {
        byte[] b = json.getBytes(StandardCharsets.UTF_8);
        Headers h = ex.getResponseHeaders();
        h.set("Content-Type", "application/json; charset=utf-8");
        securityHeaders(h);
        ex.sendResponseHeaders(code, b.length);
        try (OutputStream os = ex.getResponseBody()) { os.write(b); }
    }
}
