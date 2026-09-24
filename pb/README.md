# pb/ — esquema de PocketBase versionado

- `migrations/` — migraciones del Mercado (y futuras). En producción se copian a
  `~/pocketbase/pb_migrations/` y PocketBase las aplica al arrancar. Cada una trae su
  función de reversa (`pocketbase migrate down 1` la deshace).
- `test-fixtures/` — colecciones mínimas que existen en producción pero no se versionan
  aquí (p. ej. `streamers`). Solo se cargan en la PocketBase desechable de pruebas.

`scripts/pb-test-server.sh` levanta esa PocketBase desechable (puerto 8099 por defecto)
con fixtures + migraciones y un superusuario de prueba.
