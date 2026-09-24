def test_api_importa_y_expone_health():
    import server
    rutas = {r.path for r in server.app.routes}
    assert "/health" in rutas
