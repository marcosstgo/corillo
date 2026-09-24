def test_api_importa_y_expone_health_y_mercado():
    import server
    rutas = {getattr(r, "path", "") for r in server.app.routes}
    assert "/health" in rutas
    from fastapi.testclient import TestClient
    assert TestClient(server.app).get("/mercado/meta").status_code == 200
