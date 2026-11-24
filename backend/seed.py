"""Datos de demostración (solo si ECOGALLO_SEED=1, nunca en producción).

- Cuentas con celular confirmado y cuenta para recibir (pagos con tarjeta), salvo al900108 (Jorge),
  que sirve para mostrar la confirmación del celular por SMS.
- Cuentas de estudiantes con las que SÍ se puede entrar (en desarrollo): correo al9001xx@edu.uaa.mx y la
  contraseña DEMO_PASSWORD. Así se puede abrir una cuenta en cada navegador y mostrar compras y mensajes.
- Publicaciones: se agregan las de la lista que todavía no existan (las bases anteriores reciben las nuevas).
- Escenas ya armadas (una sola vez): una conversación, una compra en efectivo pendiente, una compra con
  Mercado Pago retenida, una entregada esperando confirmación y dos completadas.
Las imágenes de `seed_images/` son fotos del equipo o ilustraciones propias.
"""
import shutil
from pathlib import Path

import config
from db import connect, now

IMGS = Path(__file__).resolve().parent / "seed_images"
DEMO_PASSWORD = "Demo2026"

# correo, nombre, carrera, centro, correo anterior (versiones previas usaban @demo.invalid)
DEMO = [
    ("al900101@edu.uaa.mx", "Mariana Torres", "Ingeniería en Sistemas Computacionales", "Centro de Ciencias Básicas", "demo1@demo.invalid"),
    ("al900102@edu.uaa.mx", "Luis Hernández", "Arquitectura", "Centro de Ciencias del Diseño y de la Construcción", "demo2@demo.invalid"),
    ("al900103@edu.uaa.mx", "Ana García", "Contador Público", "Centro de Ciencias Económicas y Administrativas", "demo3@demo.invalid"),
    ("al900104@edu.uaa.mx", "Carlos Ruiz", "Médico Cirujano", "Centro de Ciencias de la Salud", "demo4@demo.invalid"),
    ("al900105@edu.uaa.mx", "Sofía Méndez", "Licenciatura en Docencia del Idioma Inglés", "Centro de Ciencias Sociales y Humanidades", "demo5@demo.invalid"),
    ("al900106@edu.uaa.mx", "Diego Ramírez", "Ingeniería Civil", "Centro de Ciencias del Diseño y de la Construcción", ""),
    ("al900107@edu.uaa.mx", "Valeria López", "Licenciatura en Derecho", "Centro de Ciencias Sociales y Humanidades", ""),
    ("al900108@edu.uaa.mx", "Jorge Castillo", "Licenciatura en Economía", "Centro de Ciencias Económicas y Administrativas", ""),
]
M, LU, AN, CA, SO, DI, VA, JO = range(8)

POSTS = [
    # título, descripción, categoría, centro, tipo, precio, estado, imagen, autor(idx)
    ("Libro de Cálculo Vectorial", "Edición reciente, sin subrayados. Ideal para ingenierías de 3er semestre.",
     "Libros", "Centro de Ciencias Básicas", "venta", 250, "Usado", "libcv.jpg", 0),
    ("Protoboard y cables Dupont", "Kit básico para prácticas de circuitos digitales. Incluye 40 cables.",
     "Electrónica", "Centro de Ciencias de la Ingeniería", "venta", 120, "Como nuevo", "proto.jpg", 0),
    ("Multímetro digital", "Mide voltaje, corriente y continuidad. Funciona perfecto, puntas incluidas.",
     "Electrónica", "Centro de Ciencias Básicas", "venta", 300, "Usado", "multim.jpg", 0),
    ("Kit de dibujo arquitectónico", "Escuadras, escalímetro y compás. Lo usé solo dos semestres.",
     "Arquitectura", "Centro de Ciencias del Diseño y de la Construcción", "venta", 180, "Como nuevo", "kitarq.jpg", 1),
    ("Bata de laboratorio talla M", "Lavada y planchada. Se la regalo a quien la necesite para prácticas.",
     "Uniformes", "Centro de Ciencias de la Salud", "donacion", 0, "Usado", "bata.jpg", 2),
    ("Calculadora científica", "La cambio por una calculadora graficadora o por libro de Física.",
     "Tecnología", "Centro de Ciencias Básicas", "trueque", 0, "Usado", "calcu.jpg", 1),
    ("Libro de inglés nivel 1", "Libro de texto para el primer nivel de inglés. Con apuntes a lápiz en las primeras unidades.",
     "Libros", "Centro de Ciencias Sociales y Humanidades", "venta", 140, "Con detalles", "lib1a.jpg", 4),
    ("Lápices de dibujo técnico (set)", "Set de grafitos 2H a 6B, casi nuevos.",
     "Arquitectura", "Centro de Ciencias del Diseño y de la Construcción", "venta", 90, "Nuevo", "lapiz.jpg", 1),
    ("Libro de Física Universitaria", "Volumen 1, mecánica y ondas. Hojas completas, sin rayar.",
     "Libros", "Centro de Ciencias Básicas", "venta", 320, "Usado", "fisica.jpg", 0),
    ("Libro de Química General", "Ideal para el primer semestre. Algunas páginas subrayadas con marcatextos.",
     "Libros", "Centro de Ciencias Básicas", "venta", 280, "Con detalles", "quimica.jpg", 3),
    ("Apuntes de Álgebra Lineal", "Apuntes completos del semestre con ejercicios resueltos. Los regalo.",
     "Apuntes", "Centro de Ciencias Básicas", "donacion", 0, "Usado", "algebra.jpg", 0),
    ("Diccionario inglés–español", "Diccionario bilingüe de bolsillo. Pastas en buen estado.",
     "Libros", "Centro de Ciencias Sociales y Humanidades", "venta", 150, "Usado", "diccionario.jpg", 4),
    ("Laptop para programar", "Core i5, 8 GB de RAM y SSD de 256 GB. Batería de unas 4 horas. Incluye cargador.",
     "Tecnología", "Centro de Ciencias Básicas", "venta", 4500, "Usado", "laptop.jpg", 0),
    ("Audífonos con micrófono", "Para clases en línea y laboratorio de idiomas. Funcionan perfecto.",
     "Tecnología", "Centro de Ciencias Sociales y Humanidades", "venta", 220, "Como nuevo", "audifonos.jpg", 4),
    ("Lentes de seguridad para laboratorio", "Nuevos, sin usar. Me sobraron de la lista de material.",
     "Laboratorio", "Centro de Ciencias Básicas", "venta", 80, "Nuevo", "lentes.jpg", 3),
    ("Estetoscopio", "Doble campana, buen sonido. Lo cambio por un baumanómetro.",
     "Laboratorio", "Centro de Ciencias de la Salud", "trueque", 0, "Usado", "estetoscopio.jpg", 3),
    ("Filipina clínica talla M", "Color verde agua, lavada. Solo la usé un semestre.",
     "Uniformes", "Centro de Ciencias de la Salud", "venta", 200, "Como nuevo", "filipina.jpg", 3),
    ("Mochila para laptop", "Resistente al agua, con compartimento acolchado. La cambio por un libro de cálculo.",
     "Otros", "General", "trueque", 0, "Usado", "mochila.jpg", 2),
    ("Balón de voleibol", "Para la clase de deportes. Se lo regalo a quien lo use.",
     "Deportes", "General", "donacion", 0, "Usado", "balon.jpg", 1),
    ("Arduino UNO con sensores", "Incluye sensor ultrasónico, LEDs y cable USB. Ideal para proyectos.",
     "Electrónica", "Centro de Ciencias de la Ingeniería", "venta", 350, "Como nuevo", "arduino.jpg", 0),
    ("Memoria USB 64 GB", "Nueva, en su empaque. La gané en un evento y ya tengo otra.",
     "Tecnología", "General", "venta", 90, "Nuevo", "usb.jpg", 2),
    ("Restirador portátil", "Con regla paralela. Perfecto para los primeros semestres de Arquitectura.",
     "Arquitectura", "Centro de Ciencias del Diseño y de la Construcción", "venta", 600, "Usado", "restirador.jpg", 1),
    ("Tabla periódica plastificada", "Tamaño carta, ideal para exámenes de química. La regalo.",
     "Apuntes", "Centro de Ciencias Básicas", "donacion", 0, "Como nuevo", "tablaperiodica.jpg", 3),
    ("Calculadora financiera", "Para materias de finanzas y matemáticas financieras. Con funda.",
     "Tecnología", "Centro de Ciencias Económicas y Administrativas", "venta", 400, "Usado", "calcfin.jpg", 2),
    ("Libro de Fundamentos de Programación", "Ejemplos en C y Python. Perfecto para primer semestre de Sistemas.",
     "Libros", "Centro de Ciencias Básicas", "venta", 230, "Usado", "programacion.jpg", 0),
    ("Atlas de Anatomía Humana", "Tomo 1. Láminas a color en muy buen estado.",
     "Libros", "Centro de Ciencias de la Salud", "venta", 650, "Como nuevo", "anatomia.jpg", 3),
    ("Libro de Microeconomía", "Con ejercicios resueltos al final de cada capítulo.",
     "Libros", "Centro de Ciencias Económicas y Administrativas", "venta", 260, "Usado", "microeco.jpg", 7),
    ("Libro de Introducción al Derecho", "Lectura obligatoria de primer semestre. Sin subrayar.",
     "Libros", "Centro de Ciencias Sociales y Humanidades", "venta", 210, "Como nuevo", "derecho.jpg", 6),
    ("Kit de disección", "Estuche completo con pinzas, tijeras y mangos de bisturí. Lo cambio por una filipina.",
     "Laboratorio", "Centro de Ciencias de la Salud", "trueque", 0, "Usado", "diseccion.jpg", 3),
    ("Acuarelas y pinceles", "Paleta de 12 colores y 3 pinceles. Para Diseño o Arquitectura.",
     "Arquitectura", "Centro de Ciencias del Diseño y de la Construcción", "venta", 120, "Como nuevo", "acuarelas.jpg", 1),
    ("Tableta gráfica", "Con lápiz y cable USB. Ideal para dibujo digital y diseño.",
     "Tecnología", "Centro de Ciencias del Diseño y de la Construcción", "venta", 850, "Usado", "tableta.jpg", 5),
    ("Casco de seguridad para obra", "Requisito para las visitas de obra. Ajustable, sin golpes.",
     "Laboratorio", "Centro de Ciencias del Diseño y de la Construcción", "venta", 150, "Como nuevo", "casco.jpg", 5),
    ("Raspberry Pi 4 (4 GB)", "Con carcasa y memoria microSD de 32 GB. Para proyectos de IoT.",
     "Electrónica", "Centro de Ciencias Básicas", "venta", 1200, "Como nuevo", "raspberry.jpg", 0),
    ("Sudadera talla M", "Color verde, muy calientita. Ya no me queda.",
     "Uniformes", "General", "donacion", 0, "Usado", "sudadera.jpg", 6),
    ("Apuntes de Contabilidad Financiera", "Resúmenes y ejercicios del primer parcial al final.",
     "Apuntes", "Centro de Ciencias Económicas y Administrativas", "venta", 60, "Usado", "contabilidad.jpg", 2),
    ("Lámpara de escritorio LED", "Brazo articulado y tres niveles de luz. Ideal para estudiar de noche.",
     "Otros", "General", "venta", 180, "Como nuevo", "lampara.jpg", 7),
    ("Microscopio escolar", "Aumentos 40x a 400x. Lo cambio por un kit de disección o un estetoscopio.",
     "Laboratorio", "Centro de Ciencias Básicas", "trueque", 0, "Usado", "microscopio.jpg", 4),
    ("Raqueta de tenis de mesa", "Con dos pelotas. Para la clase de deportes o el torneo interno.",
     "Deportes", "General", "venta", 100, "Usado", "raqueta.jpg", 5),
]


def _users(con, t):
    """Crea o actualiza las cuentas demo y devuelve sus ids en el orden de DEMO."""
    from security import hash_password
    pw = hash_password(DEMO_PASSWORD) if config.DEV else ""
    ids = []
    for email, name, carrera, centro, old in DEMO:
        if old and not con.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            con.execute("UPDATE users SET email=? WHERE email=?", (email, old))
        con.execute("INSERT OR IGNORE INTO users(email,name,carrera,centro,created_at) VALUES(?,?,?,?,?)",
                    (email, name, carrera, centro, t))
        con.execute("""UPDATE users SET name=?, carrera=?, centro=?, email_verified=1, terms_version=?,
                         terms_accepted_at=CASE WHEN terms_accepted_at>0 THEN terms_accepted_at ELSE ? END
                       WHERE email=?""", (name, carrera, centro, config.LEGAL_VERSION, t, email))
        if pw:
            con.execute("UPDATE users SET password_hash=?, failed_logins=0, locked_until=0 WHERE email=? AND password_hash=''",
                        (pw, email))
        ids.append(con.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()[0])
    # Celular ya confirmado y cuenta para recibir, para mostrar los pagos con tarjeta. Jorge (el último) se
    # queda sin ellos a propósito: con su cuenta se demuestra la confirmación por SMS.
    for k, uid in enumerate(ids[:-1]):
        con.execute("""UPDATE users SET phone=?, phone_verified_at=?, payout_kind=?, payout_last4=?, payout_holder=name,
                         payout_updated_at=? WHERE id=? AND phone=''""",
                    (f"+52449555{k + 1:04d}", t, "clabe" if k % 2 else "tarjeta", f"{(k + 1) * 1111 % 10000:04d}", t, uid))
    return ids


# Puntos de entrega en Ciudad Universitaria (UAA, Aguascalientes), aproximados a ~100 m como los reales.
MEETING = [("La Velaria", 21.9139, -102.3159), ("Cafetería CCB", 21.9128, -102.3173),
           ("Punto de Encuentro Central", 21.9146, -102.3165)]


def _posts(con, ids, t):
    # Publicaciones demo de versiones anteriores sin punto de entrega: se les asigna uno (para «Cerca de mí»).
    demo_ids = set(ids)
    old_posts = [row for row in con.execute(
        "SELECT id, author_id FROM posts WHERE meet_lat IS NULL ORDER BY id").fetchall()
        if row[1] in demo_ids]
    for k, (pid, _) in enumerate(old_posts):
        place, lat, lng = MEETING[k % len(MEETING)]
        con.execute("UPDATE posts SET meet_place=?, meet_lat=?, meet_lng=? WHERE id=?", (place, lat, lng, pid))
    added = 0
    for i, (title, desc, cat, centro, tipo, price, cond, img, a) in enumerate(POSTS):
        if con.execute("SELECT 1 FROM posts WHERE author_id=? AND title=?", (ids[a], title)).fetchone():
            continue
        cur = con.execute(
            """INSERT INTO posts(author_id,title,description,category,centro,tipo,price_cents,condition,created_at)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (ids[a], title, desc, cat, centro, tipo, price * 100, cond, t - (len(POSTS) - i) * 3600))
        place, lat, lng = MEETING[i % len(MEETING)]
        con.execute("UPDATE posts SET meet_place=?, meet_lat=?, meet_lng=? WHERE id=?", (place, lat, lng, cur.lastrowid))
        src = IMGS / img
        if src.exists():
            name = f"seed-{img}"
            shutil.copyfile(src, config.UPLOADS / name)
            con.execute("INSERT INTO post_images(post_id,filename,position) VALUES(?,?,0)", (cur.lastrowid, name))
        added += 1
    return added


def _scenes(con, ids, t):
    """Conversaciones y compras en distintos estados, para enseñar el flujo sin prepararlo a mano."""
    demo_ids = ",".join(str(i) for i in ids)
    if con.execute(f"SELECT 1 FROM orders WHERE buyer_id IN ({demo_ids}) LIMIT 1").fetchone():  # nosec B608 - ids enteros propios
        return False

    def post(title):
        return con.execute("SELECT id, author_id, price_cents, status FROM posts WHERE title=?", (title,)).fetchone()

    def chat(title, pairs, start):
        p = post(title)
        for k, (who, other, text) in enumerate(pairs):
            con.execute("INSERT INTO messages(post_id,sender_id,receiver_id,content,created_at,read_at) VALUES(?,?,?,?,?,?)",
                        (p["id"], ids[who], ids[other], text, start + k * 240, start + k * 240 + 60 if k < len(pairs) - 1 else None))

    def order(title, buyer, status, provider, events, start):
        p = post(title)
        if not p or p["status"] != "active":
            return None
        cur = con.execute(
            """INSERT INTO orders(post_id,buyer_id,seller_id,amount_cents,status,payment_ref,payment_provider,
                                  checkout_group,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (p["id"], ids[buyer], p["author_id"], p["price_cents"], status,
             "sim_demo" if provider == "simulado" else "", provider, f"demo-{p['id']}", start, start + len(events) * 600))
        oid = cur.lastrowid
        if provider == "simulado":
            con.execute("UPDATE orders SET card_brand='visa', card_last4='4242' WHERE id=?", (oid,))
        for k, (actor, event, note) in enumerate(events):
            con.execute("INSERT INTO order_events(order_id,actor_id,event,note,created_at) VALUES(?,?,?,?,?)",
                        (oid, ids[actor] if actor is not None else p["author_id"], event, note, start + k * 600))
        if status == "RELEASED":
            con.execute("UPDATE posts SET status='sold', closed_at=? WHERE id=?", (start + len(events) * 600, p["id"]))
            if provider != "efectivo":
                con.execute("INSERT INTO wallet_entries(user_id,order_id,amount_cents,kind,created_at) VALUES(?,?,?,?,?)",
                            (p["author_id"], oid, p["price_cents"], "release", start + len(events) * 600))
        else:
            con.execute("UPDATE posts SET status='reserved' WHERE id=?", (p["id"],))
        return oid

    def note(user, text, link, at):
        con.execute("INSERT INTO notifications(user_id,text,link,created_at) VALUES(?,?,?,?)",
                    (ids[user], text, link, at))

    day = 86400
    # 1) Solo conversación: Valeria pregunta por el libro de Cálculo (queda disponible para comprarlo en vivo).
    chat("Libro de Cálculo Vectorial", [
        (VA, M, "¡Hola! ¿Sigue disponible el libro de Cálculo Vectorial?"),
        (M, VA, "¡Hola, Valeria! Sí, sigue disponible y está sin subrayar."),
        (VA, M, "¿Me lo podrías entregar mañana en la Cafetería CCB?"),
        (M, VA, "Claro, mañana a las 12. Puedes pagarlo con Mercado Pago o en efectivo al recibirlo."),
    ], t - 2 * 3600)

    # 2) Compra en efectivo pendiente: Diego apartó el multímetro de Mariana.
    o = order("Multímetro digital", DI, "CASH_PENDING", "efectivo", [
        (DI, "cash_pending", "Artículo apartado. Se paga en efectivo al momento de la entrega en el campus."),
    ], t - 5 * 3600)
    if o:
        chat("Multímetro digital", [
            (DI, M, "Hola, aparté el multímetro para pagarlo en efectivo. ¿Nos vemos en La Velaria?"),
            (M, DI, "¡Perfecto! Mañana a las 10:00 en La Velaria. Llevo las puntas también."),
            (DI, M, "Va, ahí nos vemos. Llevo el efectivo exacto ($300)."),
        ], t - 5 * 3600 + 300)
        note(M, "Diego Ramírez apartó «Multímetro digital» para pagarlo en efectivo. Coordina la entrega en un punto seguro del campus y cobra al entregar.", f"#/order/{o}", t - 5 * 3600)

    # 3) Mercado Pago, dinero retenido: Valeria compró el kit de dibujo de Luis.
    o = order("Kit de dibujo arquitectónico", VA, "HELD", "simulado", [
        (VA, "paid_held", "Pago realizado y retenido por ECO-GALLO hasta que confirmes la recepción."),
    ], t - day)
    if o:
        chat("Kit de dibujo arquitectónico", [
            (VA, LU, "¡Ya pagué el kit! ¿Cuándo nos vemos?"),
            (LU, VA, "Gracias, Valeria. ¿Te parece el jueves en el Punto de Encuentro Central?"),
        ], t - day + 300)
        note(LU, "Valeria López pagó «Kit de dibujo arquitectónico». El dinero está retenido: entrega el artículo y espera la confirmación.", f"#/order/{o}", t - day)

    # 4) Entregado, esperando que el comprador confirme: Diego compró el libro de Química a Carlos.
    o = order("Libro de Química General", DI, "DELIVERED", "simulado", [
        (DI, "paid_held", "Pago realizado y retenido por ECO-GALLO hasta que confirmes la recepción."),
        (CA, "delivered", "El vendedor indica que entregó el artículo."),
    ], t - 2 * day)
    if o:
        note(DI, "Carlos Ruiz marcó «Libro de Química General» como entregado. Si ya lo tienes, confirma la recepción.", f"#/order/{o}", t - 2 * day + 600)

    # 5) Completada en efectivo: Sofía compró la calculadora financiera a Ana.
    order("Calculadora financiera", SO, "RELEASED", "efectivo", [
        (SO, "cash_pending", "Artículo apartado. Se paga en efectivo al momento de la entrega en el campus."),
        (AN, "cash_paid", "El vendedor entregó el artículo y recibió el pago en efectivo. Compra completada."),
    ], t - 4 * day)

    # 6) Completada con Mercado Pago: Jorge compró las acuarelas a Luis.
    order("Acuarelas y pinceles", JO, "RELEASED", "simulado", [
        (JO, "paid_held", "Pago realizado y retenido por ECO-GALLO hasta que confirmes la recepción."),
        (LU, "delivered", "El vendedor indica que entregó el artículo."),
        (JO, "confirmed", "El comprador confirmó que recibió el artículo. Fondos liberados al vendedor."),
    ], t - 6 * day)
    return True


def seed():
    if config.PRODUCTION:
        return
    con = connect()
    t = now()
    ids = _users(con, t)
    # Corrección: la foto del libro de inglés estaba publicada como «Libro de Contabilidad básica».
    con.execute("""UPDATE posts SET title='Libro de inglés nivel 1', category='Libros',
                   centro='Centro de Ciencias Sociales y Humanidades',
                   description='Libro de texto para el primer nivel de inglés. Con apuntes a lápiz en las primeras unidades.'
                   WHERE title='Libro de Contabilidad básica' AND author_id IN (%s)""" % ",".join(map(str, ids)))  # nosec B608 - ids enteros
    added = _posts(con, ids, t)
    scenes = _scenes(con, ids, t)
    con.close()
    if added:
        print(f"  Datos de demostración: {added} publicaciones agregadas.", flush=True)
    if scenes:
        print("  Datos de demostración: conversaciones y compras de ejemplo listas.", flush=True)
    if config.DEV:
        print(f"  Cuentas de demostración: al900101@edu.uaa.mx … al900108@edu.uaa.mx · contraseña {DEMO_PASSWORD}", flush=True)
