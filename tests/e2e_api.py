"""Prueba de extremo a extremo contra el gateway (requiere ECOGALLO_DEV=1 para leer el código)."""
import http.cookiejar, json, sys, urllib.request, urllib.error, uuid

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"

class Client:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
    def call(self, method, path, body=None, raw=None, headers=None):
        h = dict(headers or {})
        data = raw
        if body is not None:
            data = json.dumps(body).encode(); h["Content-Type"] = "application/json"
        req = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
        try:
            r = self.op.open(req)
            content = r.read() or b"{}"
            try:
                return r.status, json.loads(content)
            except Exception:
                return r.status, content
        except urllib.error.HTTPError as e:
            content = e.read() or b"{}"
            try:
                return e.code, json.loads(content)
            except Exception:
                return e.code, content

def check(cond, msg):
    print(("  ok  " if cond else "  FAIL"), msg)
    if not cond: check.failed = True
check.failed = False

def login(email, name):
    c = Client()
    s, r = c.call("POST", "/api/auth/request-code", {"email": email}); assert s == 200, r
    s, r = c.call("POST", "/api/auth/verify", {"email": email, "code": r["dev_code"]}); assert s == 200, r
    if r["needs_profile"]:
        s, r = c.call("PUT", "/api/me", {"name": name, "carrera": "Ingeniería en Sistemas Computacionales"}); assert s == 200, r
    return c

def multipart(fields, files=()):
    b = uuid.uuid4().hex; out = b""
    for k, v in fields.items():
        out += f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    for k, fn, data in files:
        out += (f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{fn}"\r\n'
                f'Content-Type: application/octet-stream\r\n\r\n').encode() + data + b"\r\n"
    out += f"--{b}--\r\n".encode()
    return out, {"Content-Type": f"multipart/form-data; boundary={b}"}

tag = uuid.uuid4().hex[:6]
print("Login por código")
c = Client()
s, r = c.call("POST", "/api/auth/request-code", {"email": "alguien@gmail.com"})
check(s == 200 and "dev_code" not in r, "correo no UAA y sin cuenta de egresado: no se manda código (respuesta neutra)")
s, r = c.call("POST", "/api/auth/request-code", {"email": "x@edu.uaa.mx.evil.com"})
check(s == 200 and "dev_code" not in r, "dominio falso no recibe código")
s, r = c.call("POST", "/api/auth/request-code", {"email": "no-es-correo"}); check(s == 400, "rechaza texto que no es correo")
s, r = c.call("GET", "/api/posts"); check(s == 401, "API protegida sin sesión")
e = f"al{tag}@edu.uaa.mx"
s, r = c.call("POST", "/api/auth/request-code", {"email": e}); check(s == 200 and "dev_code" in r, "envía código")
code = r["dev_code"]
s, r2 = c.call("POST", "/api/auth/request-code", {"email": e}); check(s == 429, "cooldown de reenvío")
bad = "000000" if code != "000000" else "111111"
s, r2 = c.call("POST", "/api/auth/verify", {"email": e, "code": bad}); check(s == 400, "código incorrecto rechazado")
s, r2 = c.call("POST", "/api/auth/verify", {"email": e, "code": code}); check(s == 200 and r2["needs_profile"], "código correcto → sesión")
s, r2 = c.call("POST", "/api/auth/verify", {"email": e, "code": code}); check(s == 400, "el código sirve una sola vez")
s, r2 = c.call("GET", "/api/posts"); check(s == 403, "perfil incompleto bloquea API")
s, r2 = c.call("PUT", "/api/me", {"name": "Vendedora Prueba", "carrera": "Carrera inventada"}); check(s == 400, "carrera fuera de la lista UAA se rechaza")
s, r2 = c.call("PUT", "/api/me", {"name": "Vendedora Prueba", "carrera": "Arquitectura"}); check(s == 200 and r2["user"]["centro"] == "Centro de Ciencias del Diseño y de la Construcción", "completa perfil; el centro sale de la carrera")
seller = c

print("Publicación")
png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
body, h = multipart({"title": "Libro de prueba", "description": "Descripción suficiente para la prueba.",
                     "category": "Libros", "centro": "Centro de Ciencias Básicas", "tipo": "venta", "price": "200",
                     "condition": "Usado"}, [("images", "a.png", png)])
s, r = seller.call("POST", "/api/posts", raw=body, headers=h); check(s == 201, f"crea publicación {r}")
pid = r["id"]
body, h = multipart({"title": "Malo", "description": "Descripción suficiente.", "category": "Libros",
                     "tipo": "venta", "price": "10"}, [("images", "x.php", b"<?php ?>")])
s, r = seller.call("POST", "/api/posts", raw=body, headers=h); check(s == 400, "rechaza archivo no-imagen")

buyer = login(f"al{tag}b@edu.uaa.mx", "Comprador Prueba")
s, r = buyer.call("GET", f"/api/posts?q=prueba"); check(s == 200 and any(p["id"] == pid for p in r["posts"]), "búsqueda encuentra la publicación")
s, r = seller.call("POST", "/api/orders", {"post_id": pid}); check(s == 400, "no puedes comprar lo tuyo")

print("Pago retenido")
s, r = buyer.call("POST", "/api/orders", {"post_id": pid}); check(s == 201, "comprador paga → HELD")
oid = r["id"]
other = login(f"al{tag}c@edu.uaa.mx", "Otro Comprador")
s, r = other.call("POST", "/api/orders", {"post_id": pid}); check(s == 409, "nadie más puede comprarlo (reservado)")
s, r = other.call("GET", f"/api/orders/{oid}"); check(s == 404, "terceros no ven la orden")
s, r = seller.call("GET", "/api/wallet"); check(r["available_cents"] == 0 and r["pending_cents"] == 20000, "dinero pendiente, no disponible")
s, r = seller.call("POST", f"/api/orders/{oid}/confirm"); check(s == 403, "el vendedor NO puede liberar su propio pago")
s, r = seller.call("POST", f"/api/orders/{oid}/deliver"); check(s == 200, "vendedor marca entregado → DELIVERED")
s, r = seller.call("GET", "/api/wallet"); check(r["available_cents"] == 0, "sigue retenido tras 'entregado'")
s, r = buyer.call("POST", f"/api/orders/{oid}/confirm"); check(s == 200, "comprador confirma → RELEASED")
s, r = seller.call("GET", "/api/wallet"); check(r["available_cents"] == 20000 and r["pending_cents"] == 0, "fondos liberados al vendedor")
s, r = buyer.call("POST", f"/api/orders/{oid}/confirm"); check(s == 403, "no se libera dos veces")
s, r = buyer.call("GET", f"/api/orders/{oid}"); check(r["order"]["status"] == "RELEASED" and len(r["order"]["events"]) >= 3, "historial de eventos")
s, r = buyer.call("GET", f"/api/posts/{pid}"); check(r["post"]["status"] == "sold", "publicación marcada vendida")

print("Disputa y reembolso")
body, h = multipart({"title": "Calculadora", "description": "Calculadora en buen estado.", "category": "Tecnología",
                     "tipo": "venta", "price": "100.50", "condition": "Usado"})
s, r = seller.call("POST", "/api/posts", raw=body, headers=h); pid2 = r["id"]
s, r = buyer.call("POST", "/api/orders", {"post_id": pid2}); oid2 = r["id"]
s, r = buyer.call("POST", f"/api/orders/{oid2}/dispute", {"reason": "x"}); check(s == 400, "disputa exige motivo")
s, r = buyer.call("POST", f"/api/orders/{oid2}/dispute", {"reason": "No llegó el artículo al punto de encuentro."}); check(s == 200, "abre disputa")
s, r = seller.call("POST", f"/api/orders/{oid2}/refund"); check(s == 403, "vendedor no puede reembolsar en disputa (decide admin)")
admin = login("admin@edu.uaa.mx", "Admin ECO")
s, r = admin.call("GET", "/api/admin/overview"); check(s == 200 and len(r["disputes"]) >= 1, "admin ve disputas")
s, r = buyer.call("GET", "/api/admin/overview"); check(s == 403, "usuario normal no entra al admin")
s, r = admin.call("POST", f"/api/orders/{oid2}/resolve-refund", {"note": "Sin evidencia de entrega."}); check(s == 200, "admin reembolsa")
s, r = buyer.call("GET", f"/api/posts/{pid2}"); check(r["post"]["status"] == "active", "publicación vuelve a estar disponible")

print("Mensajes / varios")
s, r = buyer.call("POST", "/api/messages", {"post_id": pid2, "receiver_id": r["post"]["author"]["id"], "content": "<b>Hola</b>"}); check(s == 201, "envía mensaje")
s, r = seller.call("GET", "/api/threads"); check(len(r["threads"]) >= 1 and r["threads"][0]["unread"] == 1, "vendedora ve hilo con 1 sin leer")
s, r = seller.call("GET", "/api/impact"); check(s == 200 and r["reused_items"] >= 1, "dashboard de impacto")

print("Contraseña")
s, r = seller.call("PUT", "/api/auth/password", {"new_password": "corta1"}); check(s == 400, "rechaza contraseña corta")
s, r = seller.call("PUT", "/api/auth/password", {"new_password": "solo letras largas"}); check(s == 400, "exige al menos un número")
s, r = seller.call("PUT", "/api/auth/password", {"new_password": "clave12345"}); check(s == 200, "crea contraseña con sesión activa")
s, r = seller.call("PUT", "/api/auth/password", {"new_password": "otraclave99"}); check(s == 400, "cambiarla exige la actual")
pc = Client()
s, r = pc.call("POST", "/api/auth/login", {"email": e, "password": "clave12345"}); check(s == 200 and r["user"]["has_password"], "entra con correo + contraseña (sin código)")
s, r = pc.call("GET", "/api/posts"); check(s == 200, "la sesión por contraseña funciona")
s, r = Client().call("POST", "/api/auth/login", {"email": "nadie@edu.uaa.mx", "password": "clave12345"}); check(s == 401, "correo inexistente: mismo error que contraseña mala")
bruteforce = Client(); codes = [bruteforce.call("POST", "/api/auth/login", {"email": e, "password": "incorrecta1"})[0] for _ in range(6)]
check(codes[:5] == [401] * 5 and codes[5] == 429, "se bloquea tras 5 intentos fallidos")
s, r = Client().call("POST", "/api/auth/login", {"email": e, "password": "clave12345"}); check(s == 429, "bloqueado aunque la contraseña sea correcta")
print("Egresados")
admin2 = admin  # ya inició sesión arriba
pdf = b"%PDF-1.4\n" + b"0" * 64
em = f"egresado{tag}@gmail.com"
fields = {"email": em, "name": "Eva Egresada", "carrera": "Licenciatura en Derecho", "doc_type": "kardex", "password": "clave12345"}
ec = Client()
body, h = multipart(fields, [("document", "x.exe", b"MZ\x90\x00 no soy imagen")]); s, r = ec.call("POST", "/api/auth/egresado", raw=body, headers=h)
check(s == 400, "rechaza archivo que no es imagen/PDF (se revisa el contenido, no la extensión)")
body, h = multipart({**fields, "carrera": "Hechicería"}, [("document", "k.pdf", pdf)]); s, r = ec.call("POST", "/api/auth/egresado", raw=body, headers=h)
check(s == 400, "carrera fuera de catálogo")
body, h = multipart(fields, [("document", "k.pdf", pdf)]); s, r = ec.call("POST", "/api/auth/egresado", raw=body, headers=h)
check(s == 200 and "dev_code" in r, "registro de egresado con kárdex: manda código al correo personal")
ecode = r["dev_code"]
s, r = Client().call("POST", "/api/auth/login", {"email": em, "password": "clave12345"}); check(s == 403 and r.get("needs_email_verification"), "sin confirmar correo no entra ni con contraseña")
body, h = multipart({**fields, "name": "Impostor"}, [("document", "k.pdf", pdf)]); s, r = Client().call("POST", "/api/auth/egresado", raw=body, headers=h)
check(s == 409, "nadie puede pisar un registro pendiente de otra persona")
s, r = ec.call("POST", "/api/auth/verify", {"email": em, "code": ecode}); check(s == 200 and r["needs_verification"], "confirma correo → entra, pero en revisión")
s, r = ec.call("GET", "/api/posts"); check(s == 403 and r.get("needs_verification"), "egresado sin aprobar no ve el marketplace")
s, r = ec.call("GET", "/api/me"); check(s == 200 and r["verification"]["status"] == "pending", "ve su solicitud pendiente")
s, r = seller.call("GET", "/api/admin/verifications/1/file"); check(s == 403, "usuario normal no puede ver documentos")
s, r = admin2.call("GET", "/api/admin/overview"); q = [v for v in r["verifications"] if v["email"] == em]
check(s == 200 and len(q) == 1 and q[0]["is_pdf"], "admin ve la solicitud en su cola")
vid = q[0]["id"]
s, r = admin2.call("POST", f"/api/admin/verifications/{vid}/review", {"action": "reject"}); check(s == 400, "rechazar exige motivo")
s, r = admin2.call("POST", f"/api/admin/verifications/{vid}/review", {"action": "reject", "note": "El kárdex no se lee."}); check(s == 200, "admin rechaza con motivo")
s, r = ec.call("GET", "/api/me"); check(r["user"]["verif_status"] == "rejected" and "no se lee" in r["verification"]["note"], "el egresado ve el motivo")
s, r = admin2.call("GET", f"/api/admin/verifications/{vid}/file"); check(s == 404, "el documento se borra al resolver")
body, h = multipart({"doc_type": "titulo"}, [("document", "t.pdf", pdf)]); s, r = ec.call("POST", "/api/auth/egresado/document", raw=body, headers=h)
check(s == 200, "sube otro documento tras el rechazo")
s, r = admin2.call("GET", "/api/admin/overview"); vid = [v for v in r["verifications"] if v["email"] == em][0]["id"]
s, r = admin2.call("POST", f"/api/admin/verifications/{vid}/review", {"action": "approve"}); check(s == 200, "admin aprueba")
s, r = ec.call("GET", "/api/posts"); check(s == 200, "egresado aprobado ya usa el marketplace")
s, r = Client().call("POST", "/api/auth/login", {"email": em, "password": "clave12345"}); check(s == 200, "egresado entra con correo personal + contraseña")

print("Filtros por estado y precio")
def newpost(client, title, price, cond="Usado", tipo="venta", cat="Libros", centro="Centro de Ciencias Básicas", desc="Descripción suficientemente larga."):
    f = {"title": title, "description": desc, "category": cat, "centro": centro, "tipo": tipo, "condition": cond}
    if tipo == "venta": f["price"] = str(price)
    body, h = multipart(f); s, r = client.call("POST", "/api/posts", raw=body, headers=h); assert s == 201, r
    return r["id"]
fp1 = newpost(seller, f"Filtro barato {tag}", 50, "Nuevo")
fp2 = newpost(seller, f"Filtro caro {tag}", 900, "Con detalles")
s, r = buyer.call("GET", f"/api/posts?q={tag}&condition=Nuevo"); check([x["id"] for x in r["posts"]] == [fp1], "filtra por estado del producto")
s, r = buyer.call("GET", f"/api/posts?q={tag}&min_price=100"); check([x["id"] for x in r["posts"]] == [fp2], "filtra por precio mínimo")
s, r = buyer.call("GET", f"/api/posts?q={tag}&max_price=100"); check([x["id"] for x in r["posts"]] == [fp1], "filtra por precio máximo")
s, r = buyer.call("GET", f"/api/posts?q={tag}&min_price=10&max_price=1000"); check(len(r["posts"]) == 2, "rango que incluye ambas")
s, r = buyer.call("GET", "/api/posts?condition=Roto"); check(s == 400, "estado inválido se rechaza")
s, r = buyer.call("GET", "/api/posts?min_price=abc"); check(s == 400, "precio inválido se rechaza")

print("Pausar publicaciones")
s, r = buyer.call("POST", f"/api/posts/{fp1}/pause", {"paused": True}); check(s == 404, "otro usuario no puede pausar")
s, r = seller.call("POST", f"/api/posts/{fp1}/pause", {"paused": True}); check(s == 200 and r["status"] == "paused", "el autor pausa")
s, r = buyer.call("GET", f"/api/posts?q={tag}"); check(fp1 not in [x["id"] for x in r["posts"]], "pausada no sale en el catálogo")
s, r = buyer.call("POST", "/api/orders", {"post_id": fp1}); check(s >= 400, "no se puede comprar una pausada")
s, r = seller.call("GET", "/api/posts?mine=1"); check(fp1 in [x["id"] for x in r["posts"]], "el autor la sigue viendo en Mis publicaciones")
body, h = multipart({"title": f"Filtro barato {tag} (editado)", "description": "Descripción suficientemente larga.", "category": "Libros",
                     "centro": "Centro de Ciencias Básicas", "tipo": "venta", "condition": "Nuevo", "price": "55"})
s, r = seller.call("PUT", f"/api/posts/{fp1}", raw=body, headers=h); check(s == 200, "se puede editar estando pausada")
s, r = seller.call("POST", f"/api/posts/{fp1}/pause", {"paused": True}); check(s == 409, "no se pausa dos veces")
s, r = seller.call("POST", f"/api/posts/{fp1}/pause", {"paused": False}); check(s == 200 and r["status"] == "active", "reanuda")
s, r = buyer.call("GET", f"/api/posts?q={tag}"); check(fp1 in [x["id"] for x in r["posts"]], "reanudada vuelve al catálogo")

print("Foto de perfil y biografía")
s, r = seller.call("GET", "/api/me"); me_name = r["user"]["name"]; me_carrera = r["user"]["carrera"]
s, r = seller.call("PUT", "/api/me", {"name": me_name, "carrera": me_carrera, "bio": "Vendo libros de ingeniería <b>baratos</b>."}); check(s == 200 and r["user"]["bio"].startswith("Vendo"), "guarda biografía")
s, r = seller.call("PUT", "/api/me", {"name": me_name, "carrera": me_carrera}); check(r["user"]["bio"].startswith("Vendo"), "editar perfil sin mandar bio no la borra")
body, h = multipart({}, [("avatar", "a.exe", b"MZ no soy imagen")]); s, r = seller.call("POST", "/api/me/avatar", raw=body, headers=h); check(s == 400, "avatar: rechaza archivos que no son imagen")
body, h = multipart({}, [("avatar", "a.png", b"\x89PNG\r\n\x1a\n" + b"0" * 64)]); s, r = seller.call("POST", "/api/me/avatar", raw=body, headers=h); check(s == 200 and r["avatar"].startswith("/uploads/avatar-"), "sube foto de perfil")
av = r["avatar"]
s, r = buyer.call("GET", f"/api/posts/{fp1}"); check(r["post"]["author"]["avatar"] == av and "baratos" in r["post"]["author"]["bio"], "el comprador ve foto y bio del vendedor")
s, r = seller.call("DELETE", "/api/me/avatar"); check(s == 200, "quita la foto")
s, r = seller.call("GET", "/api/me"); check(r["user"]["avatar"] == "", "la foto quedó vacía")

print("Lista de deseos")
s, r = buyer.call("POST", "/api/wishlist", {"term": "x"}); check(s == 400, "deseo demasiado corto")
s, r = buyer.call("POST", "/api/wishlist", {"term": "Teoría cuántica", "category": "Inventada"}); check(s == 400, "categoría inválida")
s, r = buyer.call("POST", "/api/wishlist", {"term": f"termodinamica {tag}", "category": "Libros"}); check(s == 201, "agrega un deseo"); wid = r["id"]
s, r = buyer.call("POST", "/api/wishlist", {"term": f"TERMODINÁMICA {tag}", "category": "Libros"}); check(s == 409, "no duplica (ignora acentos y mayúsculas)")
s, r = buyer.call("POST", "/api/wishlist", {"term": f"otracosa{tag}", "category": "Libros"}); wid_b = r["id"]
s, r = buyer.call("GET", "/api/notifications"); before = len(r["notifications"])
newpost(seller, f"Libro de Termodinámica {tag}", 120, desc="Sexta edición, casi nuevo.", cat="Apuntes")
s, r = buyer.call("GET", "/api/notifications"); check(len(r["notifications"]) == before, "categoría distinta: no avisa")
pid_w = newpost(seller, f"Libro de Termodinámica {tag}", 120, desc="Sexta edición, casi nuevo.", cat="Libros")
s, r = buyer.call("GET", "/api/notifications"); hits = [n for n in r["notifications"] if f"/post/{pid_w}" in n["link"]]
check(len(hits) == 1, "avisa al comprador cuando se publica algo que coincide (sin acentos)")
s, r = seller.call("GET", "/api/notifications"); check(not any("lista de deseos" in n["text"] for n in r["notifications"]), "el autor no se avisa a sí mismo")
s, r = other.call("DELETE", f"/api/wishlist/{wid}"); check(s == 404, "nadie borra deseos ajenos")
s, r = buyer.call("DELETE", f"/api/wishlist/{wid}"); check(s == 200, "quita un deseo")
for i in range(12):
    s, r = buyer.call("POST", "/api/wishlist", {"term": f"deseo extra {i} {tag}"})
check(s == 409, "límite de 10 deseos")
s, r = seller.call("POST", "/api/auth/logout"); s, r = seller.call("GET", "/api/posts"); check(s == 401, "logout cierra sesión")

print("Desbloqueo por código (espera el cooldown de reenvío)")
import time
for _ in range(50):
    code2 = Client().call("POST", "/api/auth/request-code", {"email": e})[1]
    if "dev_code" in code2: break
    time.sleep(1)
cc = Client(); s, r = cc.call("POST", "/api/auth/verify", {"email": e, "code": code2.get("dev_code", "000000")})
check(s == 200, "el código por correo funciona con la cuenta bloqueada")
for _ in range(50):
    r = Client().call("POST", "/api/auth/request-code", {"email": em})[1]
    if "dev_code" in r: break
    time.sleep(1)
check("dev_code" in r, "egresado registrado también puede entrar con código")
s, r = Client().call("POST", "/api/auth/login", {"email": e, "password": "clave12345"}); check(s == 200, "y la contraseña vuelve a funcionar")
print("Respaldos del sistema")
s, r = buyer.call("GET", "/api/admin/backups"); check(s == 403, "usuario regular no accede a respaldos")
s, r = buyer.call("POST", "/api/admin/backups/no_existe.zip/restore"); check(s == 403, "usuario regular no puede restaurar respaldos")
s, r = admin2.call("POST", "/api/admin/backups/no_existe.zip/restore"); check(s == 404, "restaurar archivo inexistente devuelve 404")
s, r = admin2.call("GET", "/api/admin/backups"); check(s == 200 and "backups" in r, "admin lista respaldos")
s, r = admin2.call("POST", "/api/admin/backups", {"tag": "e2e"}); check(s == 200 and "backup" in r, "admin genera respaldo")
b_name = r["backup"]["filename"]
s, r = admin2.call("GET", f"/api/admin/backups/{b_name}/download"); check(s == 200, "admin descarga archivo de respaldo")
backup_zip_bytes = r

# Modificar un dato antes de restaurar
original_name = admin2.call("GET", "/api/me")[1]["user"]["name"]
s, r = admin2.call("PUT", "/api/me", {"name": "Admin Temporal", "carrera": "Ingeniería en Sistemas Computacionales", "bio": "Bio temporal"})
check(s == 200 and r["user"]["bio"] == "Bio temporal", "modifica perfil antes de restaurar")

# Restaurar el respaldo
s, r = admin2.call("POST", f"/api/admin/backups/{b_name}/restore")
check(s == 200 and r.get("ok"), "admin restaura respaldo exitosamente")

# Verificar que volvió al estado previo y la sesión sigue activa
s, r = admin2.call("GET", "/api/me")
check(s == 200 and r["user"]["name"] == original_name and r["user"]["bio"] != "Bio temporal", "datos restaurados al estado original y sesión conservada")

# Probar subida de respaldo
body, h = multipart({}, [("backup_file", "subido.zip", backup_zip_bytes)])
s, r = admin2.call("POST", "/api/admin/backups/upload", raw=body, headers=h)
check(s == 200 and r.get("ok"), "admin sube archivo de respaldo")
uploaded_b_name = r["backup"]["filename"]

# Eliminar respaldos de prueba
s, r = admin2.call("DELETE", f"/api/admin/backups/{b_name}"); check(s == 200, "admin elimina respaldo")
s, r = admin2.call("DELETE", f"/api/admin/backups/{uploaded_b_name}"); check(s == 200, "admin elimina respaldo subido")

print("Métricas de publicación, favoritos y alertas de lista de deseos")
# Seller vuelve a iniciar sesión
seller = Client()
s, r = seller.call("POST", "/api/auth/login", {"email": e, "password": "clave12345"})
check(s == 200, "seller vuelve a iniciar sesión")

# Crear un nuevo post de venta con seller
body, h = multipart({
    "title": f"Libro de Física {tag}",
    "description": "Edición especial para ingenierías",
    "category": "Libros",
    "centro": "Centro de Ciencias Básicas",
    "tipo": "venta",
    "price": "350.00",
    "condition": "Como nuevo",
}, [("images", "fisica.png", png)])
s, r = seller.call("POST", "/api/posts", raw=body, headers=h)
check(s == 201 and "id" in r, "crea publicación de prueba para métricas y alertas")
f_post_id = r["id"]

# Buyer consulta la publicación (incrementa vistas)
s, r = buyer.call("GET", f"/api/posts/{f_post_id}")
check(s == 200 and r["post"]["stats"]["views"] >= 1, "la visualización por otro usuario incrementa el contador de vistas")

# Buyer guarda en favoritos
s, r = buyer.call("POST", f"/api/posts/{f_post_id}/favorite")
check(s == 200 and r["favorited"] is True, "usuario guarda publicación en favoritos")

# Listar favoritos
s, r = buyer.call("GET", "/api/favorites")
check(s == 200 and f_post_id in r["post_ids"], "publicación aparece en la lista de favoritos del usuario")

# Liberar espacio en la lista de deseos de buyer y agregar deseo coincidente
s, r = buyer.call("GET", "/api/wishlist")
if r.get("items"):
    buyer.call("DELETE", f"/api/wishlist/{r['items'][0]['id']}")
s, r = buyer.call("POST", "/api/wishlist", {"term": "Física", "category": "Libros"})
check(s == 201, "buyer registra deseo coincidente")

# Seller consulta estadísticas de su publicación
s, r = seller.call("GET", f"/api/posts/{f_post_id}")
check(s == 200 and r["post"]["stats"]["interested"] >= 1, "estadísticas reflejan personas interesadas (favoritos + deseos)")

# Seller baja el precio de $350.00 a $280.00
body, h = multipart({
    "title": f"Libro de Física {tag}",
    "description": "Edición especial para ingenierías",
    "category": "Libros",
    "centro": "Centro de Ciencias Básicas",
    "tipo": "venta",
    "price": "280.00",
    "condition": "Como nuevo",
}, [("images", "fisica.png", png)])
s, r = seller.call("PUT", f"/api/posts/{f_post_id}", raw=body, headers=h)
check(s == 200, "seller actualiza publicación bajando el precio")

# Buyer revisa sus notificaciones y debe tener la alerta de bajó de precio
s, r = buyer.call("GET", "/api/notifications")
has_drop_alert = any("Bajó de precio" in n["text"] and "$280.00" in n["text"] for n in r.get("notifications", []))
check(s == 200 and has_drop_alert, "buyer recibe notificación automática por reducción de precio")

print("\nRESULTADO:", "FALLÓ" if check.failed else "TODO OK")
sys.exit(1 if check.failed else 0)
