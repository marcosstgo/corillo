/// <reference path="../pb_data/types.d.ts" />
// Mercado / cuentas: `first_live_at` = primera vez que el canal salió en vivo.
// Un canal SIN esta fecha es solo "perfil" (vendedor del Mercado) y no aparece como canal en el sitio.
// Al aplicarse, marca a TODAS las cuentas que ya existían (decisión de Marcos 2026-09-24) para que
// nada desaparezca del roster. Reversa: quita el campo (se pierde solo esa fecha).
migrate((app) => {
  const c = app.findCollectionByNameOrId("streamers")
  c.fields.add(new DateField({ name: "first_live_at" }))
  app.save(c)
  const now = new Date().toISOString().replace("T", " ")
  app.db().newQuery("UPDATE streamers SET first_live_at = {:now} WHERE first_live_at = '' OR first_live_at IS NULL")
    .bind({ now }).execute()
}, (app) => {
  const c = app.findCollectionByNameOrId("streamers")
  c.fields.removeByName("first_live_at")
  app.save(c)
})
