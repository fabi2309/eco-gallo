"""Punto de entrega (US-05) y búsqueda por distancia con GPS (US-10, US-16)."""
import db
from test_regressions import Actor, app  # noqa: F401

CU = (21.913, -102.316)          # aprox. Ciudad Universitaria
CENTRO = (21.882, -102.296)      # aprox. centro de Aguascalientes (~4 km)
LEON = (21.122, -101.682)        # León, Gto. (~110 km)


def publish(app, seller, title, coords=None, place="La Velaria"):  # noqa: F811
    data = {"title": title, "description": "Descripción suficientemente larga", "category": "Libros",
            "tipo": "donacion", "condition": "Usado", "meet_place": place}
    if coords:
        data.update(meet_lat=str(coords[0]), meet_lng=str(coords[1]))
    r = seller.call("POST", "/api/posts", data=data)
    assert r.status_code == 201, r.json
    with app.app_context():
        db.get_db().execute("UPDATE posts SET status='active' WHERE id=?", (r.json["id"],))
    return r.json["id"]


def test_meeting_point_and_coordinates_are_saved_rounded(app):  # noqa: F811
    seller = Actor(app, "v@edu.uaa.mx")
    r = seller.call("POST", "/api/posts", data={"title": "Bata", "description": "Bata talla M, limpia", "category": "Libros",
                                                "tipo": "donacion", "meet_place": "Biblioteca central, planta baja",
                                                "meet_lat": "21.9134567", "meet_lng": "-102.3161234"})
    pid = r.json["id"]
    p = seller.client.get(f"/api/posts/{pid}").json["post"]
    assert p["meeting"] == {"place": "Biblioteca central, planta baja", "lat": 21.913, "lng": -102.316}
    bad = seller.call("POST", "/api/posts", data={"title": "Bata", "description": "Bata talla M, limpia", "category": "Libros",
                                                  "tipo": "donacion", "meet_lat": "200", "meet_lng": "0"})
    assert bad.status_code == 400


def test_near_me_filters_by_radius_and_sorts_by_distance(app):  # noqa: F811
    seller, buyer = Actor(app, "s@edu.uaa.mx"), Actor(app, "b@edu.uaa.mx")
    far = publish(app, seller, "Libro en León", LEON)
    mid = publish(app, seller, "Libro en el centro", CENTRO)
    near = publish(app, seller, "Libro en CU", CU)
    publish(app, seller, "Libro sin ubicación")
    r = buyer.client.get(f"/api/posts?lat={CU[0]}&lng={CU[1]}&radius_km=10&sort=cerca").json
    assert [p["id"] for p in r["posts"]] == [near, mid] and r["total"] == 2
    assert r["posts"][0]["distance_km"] == 0.0 and 3 < r["posts"][1]["distance_km"] < 6
    r = buyer.client.get(f"/api/posts?lat={CU[0]}&lng={CU[1]}&radius_km=200&sort=cerca").json
    assert [p["id"] for p in r["posts"]] == [near, mid, far]
    assert buyer.client.get("/api/posts?lat=abc&lng=1").status_code == 400
    assert buyer.client.get(f"/api/posts?lat={CU[0]}&lng={CU[1]}&radius_km=0").status_code == 400
    # Sin ubicación, el catálogo no cambia.
    assert buyer.client.get("/api/posts").json["total"] == 4


def test_changing_meeting_text_requires_moderation(app):  # noqa: F811
    seller = Actor(app, "m@edu.uaa.mx")
    pid = publish(app, seller, "Calculadora", CU)
    r = seller.call("PUT", f"/api/posts/{pid}", data={"title": "Calculadora", "description": "Descripción suficientemente larga",
                                                      "category": "Libros", "tipo": "donacion", "condition": "Usado",
                                                      "meet_place": "Otro lugar"})
    assert r.status_code == 200
    with app.app_context():
        row = db.get_db().execute("SELECT status, meet_lat FROM posts WHERE id=?", (pid,)).fetchone()
    assert row["status"] == "pending" and row["meet_lat"] is None


def test_distance_function():
    assert db.distance_km(*CU, *CU) == 0
    assert 105 < db.distance_km(*CU, *LEON) < 120
    assert db.distance_km(None, 1, 2, 3) is None
