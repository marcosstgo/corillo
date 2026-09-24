/// <reference path="../pb_data/types.d.ts" />
// SOLO PARA PRUEBAS (CI y local). Réplica mínima de la colección `streamers` de producción
// (mismo id pbc_3654200003, mismas reglas) para que las migraciones del Mercado tengan contra
// qué relacionarse en una PocketBase desechable. Nunca se copia a producción.
migrate((app) => {
  const c = new Collection({
    id: "pbc_3654200003",
    type: "auth",
    name: "streamers",
    listRule: null,
    viewRule: "@request.auth.id = id",
    createRule: null,
    updateRule: "@request.auth.id = id",
    deleteRule: null,
    fields: [
      { name: "key", type: "text", required: true },
      { name: "display_name", type: "text", required: true },
      { name: "active", type: "bool" },
      { name: "color", type: "text" },
      { name: "avatar", type: "file", maxSelect: 1 },
    ],
  })
  app.save(c)
}, (app) => {
  app.delete(app.findCollectionByNameOrId("streamers"))
})
