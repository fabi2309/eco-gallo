"""Datos de demostración (solo si ECOGALLO_SEED=1 y la base está vacía).

Los usuarios demo usan el dominio `demo.invalid`: no son @edu.uaa.mx, así que
nadie puede iniciar sesión como ellos; solo sirven de vendedores en el catálogo.
"""
import shutil
from pathlib import Path

import config
from db import connect, now

IMGS = Path(__file__).resolve().parent / "seed_images"

DEMO = [
    ("demo1@demo.invalid", "Mariana Torres", "Ingeniería en Sistemas Computacionales", "Centro de Ciencias Básicas"),
    ("demo2@demo.invalid", "Luis Hernández", "Arquitectura", "Centro de Ciencias del Diseño y de la Construcción"),
    ("demo3@demo.invalid", "Ana García", "Contador Público", "Centro de Ciencias Económicas y Administrativas"),
]

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
    ("Libro de Contabilidad básica", "Primer año. Con apuntes a lápiz en los primeros capítulos.",
     "Libros", "Centro de Ciencias Económicas y Administrativas", "venta", 140, "Con detalles", "lib1a.jpg", 2),
    ("Lápices de dibujo técnico (set)", "Set de grafitos 2H a 6B, casi nuevos.",
     "Arquitectura", "Centro de Ciencias del Diseño y de la Construcción", "venta", 90, "Nuevo", "lapiz.jpg", 1),
]


def seed():
    con = connect()
    if con.execute("SELECT COUNT(*) FROM posts").fetchone()[0]:
        con.close()
        return
    t = now()
    ids = []
    for email, name, carrera, centro in DEMO:
        cur = con.execute(
            "INSERT OR IGNORE INTO users(email,name,carrera,centro,created_at) VALUES(?,?,?,?,?)",
            (email, name, carrera, centro, t))
        ids.append(cur.lastrowid or con.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()[0])
    for i, (title, desc, cat, centro, tipo, price, cond, img, a) in enumerate(POSTS):
        cur = con.execute(
            """INSERT INTO posts(author_id,title,description,category,centro,tipo,price_cents,condition,created_at)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (ids[a], title, desc, cat, centro, tipo, price * 100, cond, t - (len(POSTS) - i) * 3600))
        src = IMGS / img
        if src.exists():
            name = f"seed-{img}"
            shutil.copyfile(src, config.UPLOADS / name)
            con.execute("INSERT INTO post_images(post_id,filename,position) VALUES(?,?,0)", (cur.lastrowid, name))
    con.close()
    print("  Datos de demostración cargados.", flush=True)
