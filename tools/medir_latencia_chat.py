"""Mide la latencia del chat entre dos navegadores reales (objetivo 4 de la tesina: < 2 s).

Requisitos: servidor en modo DEV (ECOGALLO_DEV=1, muestra los códigos en pantalla), Playwright
(`pip install playwright && playwright install chromium`) y la ruta de la base SQLite de ESA instancia,
para crear una publicación de prueba ya aprobada. Úsalo solo con datos de prueba.

    python tools/medir_latencia_chat.py http://127.0.0.1:8080 data/ecogallo.sqlite
"""
import random
import sqlite3
import statistics
import sys
import time

from playwright.sync_api import sync_playwright


def signup(browser, base, email, name):
    page = browser.new_context(viewport={"width": 1100, "height": 850}).new_page()
    page.goto(base)
    page.click("#newstudent")
    page.fill("#email", email)
    page.click("text=Enviarme un código")
    page.wait_for_selector(".devcode b")
    for i, ch in enumerate(page.inner_text(".devcode b")):
        page.locator("#cells input").nth(i).fill(ch)
    page.wait_for_selector("text=Un último paso")
    page.fill("[name=name]", name)
    page.select_option("[name=carrera]", index=4)
    page.check("[name=accept_terms]")
    page.click("text=Empezar")
    page.wait_for_selector(".topbar")
    uid = page.evaluate("async () => (await (await fetch('/api/me')).json()).user.id")
    return page, uid


def main(base, db_path, rounds=10):
    base = base.rstrip("/") + "/"
    tag = random.randint(100000, 999999)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        a, a_id = signup(browser, base, f"al{tag}@edu.uaa.mx", "Prueba Uno")
        b, b_id = signup(browser, base, f"al{(tag + 1) % 1000000:06d}@edu.uaa.mx", "Prueba Dos")
        con = sqlite3.connect(db_path)
        post_id = con.execute(
            "INSERT INTO posts(author_id,title,description,category,tipo,price_cents,status,created_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (a_id, "Publicación de prueba de latencia", "Solo para medir el chat.", "Otros", "donacion", 0,
             "active", int(time.time()))).lastrowid
        con.commit()
        a.goto(base + f"#/chat/{post_id}/{b_id}")
        b.goto(base + f"#/chat/{post_id}/{a_id}")
        a.wait_for_selector("#f input")
        b.wait_for_selector("#f input")
        lat = []
        for i in range(rounds):
            sender, receiver = (a, b) if i % 2 == 0 else (b, a)
            text = f"Mensaje de prueba {tag}-{i}"
            sender.fill("#f input", text)
            t0 = time.perf_counter()
            sender.press("#f input", "Enter")
            receiver.wait_for_selector(f".bubble:has-text('{text}')", timeout=5000)
            lat.append(time.perf_counter() - t0)
            time.sleep(0.3)
        browser.close()
    print("Latencias (s):", [round(x, 2) for x in lat])
    print(f"Media {statistics.mean(lat):.2f} s · mediana {statistics.median(lat):.2f} s · máximo {max(lat):.2f} s")
    print("CUMPLE (< 2 s)" if max(lat) < 2 else "NO CUMPLE (>= 2 s)")
    return 0 if max(lat) < 2 else 1


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2]))
