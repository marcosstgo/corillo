/// <reference path="../pb_data/types.d.ts" />
// Reenvío de correo en ambos sentidos: cada mensaje abre un "hilo" con un alias
// r+<hilo>.<lado>@mg.corillo.live. Nadie ve el correo del otro. Reversa: quita los campos.
migrate((app) => {
  const c = app.findCollectionByNameOrId("mercado_mensajes")
  c.fields.add(new TextField({ name: "hilo", max: 40, pattern: "^[a-z0-9]*$" }))
  c.fields.add(new NumberField({ name: "respuestas", min: 0, onlyInt: true }))
  c.fields.add(new DateField({ name: "ultima_respuesta" }))
  c.indexes.push("CREATE UNIQUE INDEX idx_mercado_mensajes_hilo ON mercado_mensajes (hilo) WHERE hilo != ''")
  app.save(c)
}, (app) => {
  const c = app.findCollectionByNameOrId("mercado_mensajes")
  c.indexes = c.indexes.filter((i) => !i.includes("idx_mercado_mensajes_hilo"))
  for (const n of ["hilo", "respuestas", "ultima_respuesta"]) c.fields.removeByName(n)
  app.save(c)
})
