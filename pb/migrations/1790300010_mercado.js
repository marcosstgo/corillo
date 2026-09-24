/// <reference path="../pb_data/types.d.ts" />
// Mercado de equipo usado. TODAS las reglas quedan en null (solo superusuario): el navegador
// nunca escribe ni lee estas colecciones directo; todo pasa por corillo-api (/api/mercado/*),
// que valida, procesa las fotos (WebP sin EXIF), aplica límites y oculta datos privados.
// Reversa: borra las 4 colecciones (y sus datos).
migrate((app) => {
  const streamers = app.findCollectionByNameOrId("streamers")
  const created = () => ({ name: "created", type: "autodate", onCreate: true, onUpdate: false })
  const updated = () => ({ name: "updated", type: "autodate", onCreate: true, onUpdate: true })

  const anuncios = new Collection({
    type: "base", name: "mercado_anuncios",
    listRule: null, viewRule: null, createRule: null, updateRule: null, deleteRule: null,
    fields: [
      { name: "vendedor", type: "relation", collectionId: streamers.id, maxSelect: 1, required: true, cascadeDelete: false },
      { name: "titulo", type: "text", min: 5, max: 90, required: true },
      { name: "categoria", type: "text", max: 40, pattern: "^[a-z0-9-]+$", required: true },
      { name: "subcategoria", type: "text", max: 40, pattern: "^[a-z0-9-]*$" },
      { name: "marca", type: "text", max: 60 },
      { name: "modelo", type: "text", max: 80 },
      { name: "condicion", type: "select", maxSelect: 1, required: true, values: ["nuevo", "como-nuevo", "buen-estado", "para-piezas"] },
      { name: "precio", type: "number", min: 0, max: 100000, required: false },
      { name: "negociable", type: "bool" },
      { name: "descripcion", type: "text", max: 3000 },
      { name: "incluye", type: "json", maxSize: 8000 },
      { name: "falta", type: "json", maxSize: 8000 },
      { name: "pueblo", type: "text", max: 40, pattern: "^[a-z0-9-]+$", required: true },
      { name: "entrega", type: "select", maxSelect: 1, required: true, values: ["persona", "envio", "ambos"] },
      { name: "whatsapp", type: "text", max: 20, hidden: true },
      { name: "estado", type: "select", maxSelect: 1, required: true, values: ["disponible", "reservado", "vendido"] },
      { name: "vendido_at", type: "date" },
      { name: "pausado", type: "bool" },
      { name: "moderacion", type: "select", maxSelect: 1, required: true, values: ["visible", "oculto"] },
      { name: "motivo_oculto", type: "text", max: 300 },
      { name: "reportes", type: "number", min: 0, onlyInt: true },
      { name: "fotos", type: "file", maxSelect: 10, maxSize: 5242880, mimeTypes: ["image/webp"] },
      { name: "og", type: "file", maxSelect: 1, maxSize: 2097152, mimeTypes: ["image/jpeg"] },
      created(), updated(),
    ],
    indexes: [
      "CREATE INDEX idx_mercado_anuncios_vendedor ON mercado_anuncios (vendedor)",
      "CREATE INDEX idx_mercado_anuncios_pub ON mercado_anuncios (moderacion, pausado, estado, categoria)",
    ],
  })
  app.save(anuncios)

  app.save(new Collection({
    type: "base", name: "mercado_reportes",
    listRule: null, viewRule: null, createRule: null, updateRule: null, deleteRule: null,
    fields: [
      { name: "anuncio", type: "relation", collectionId: anuncios.id, maxSelect: 1, required: true, cascadeDelete: true },
      { name: "motivo", type: "select", maxSelect: 1, required: true, values: ["prohibido", "estafa", "spam", "ofensivo", "vendido", "otro"] },
      { name: "detalle", type: "text", max: 500 },
      { name: "ip", type: "text", max: 64, required: true },
      { name: "resuelto", type: "bool" },
      created(),
    ],
    indexes: ["CREATE UNIQUE INDEX idx_mercado_reportes_ip ON mercado_reportes (anuncio, ip)"],
  }))

  app.save(new Collection({
    type: "base", name: "mercado_mensajes",
    listRule: null, viewRule: null, createRule: null, updateRule: null, deleteRule: null,
    fields: [
      // No obligatoria: si el vendedor borra el anuncio, el mensaje se queda (para moderar abuso)
      // con la relación vacía; el título y el vendedor se copian aquí al guardarlo.
      { name: "anuncio", type: "relation", collectionId: anuncios.id, maxSelect: 1, required: false, cascadeDelete: false },
      { name: "anuncio_titulo", type: "text", max: 90 },
      { name: "vendedor", type: "relation", collectionId: streamers.id, maxSelect: 1, required: false, cascadeDelete: false },
      { name: "nombre", type: "text", max: 80, required: true },
      { name: "email", type: "email", required: true },
      { name: "mensaje", type: "text", max: 2000, required: true },
      { name: "ip", type: "text", max: 64, required: true },
      { name: "enviado", type: "bool" },
      created(),
    ],
    indexes: ["CREATE INDEX idx_mercado_mensajes_ip ON mercado_mensajes (ip, created)"],
  }))

  app.save(new Collection({
    type: "base", name: "mercado_bloqueos",
    listRule: null, viewRule: null, createRule: null, updateRule: null, deleteRule: null,
    fields: [
      { name: "tipo", type: "select", maxSelect: 1, required: true, values: ["ip", "email", "vendedor"] },
      { name: "valor", type: "text", max: 200, required: true },
      { name: "motivo", type: "text", max: 300 },
      created(),
    ],
    indexes: ["CREATE UNIQUE INDEX idx_mercado_bloqueos ON mercado_bloqueos (tipo, valor)"],
  }))
}, (app) => {
  for (const n of ["mercado_bloqueos", "mercado_mensajes", "mercado_reportes", "mercado_anuncios"]) {
    try { app.delete(app.findCollectionByNameOrId(n)) } catch (_) {}
  }
})
