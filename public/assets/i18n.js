/* Traductor del lado del navegador (misma sintaxis que src/i18n/index.ts).
   Las páginas dejan su diccionario en <script type="application/json" id="i18n">. */
(function () {
  var d = {};
  try { d = JSON.parse(document.getElementById('i18n').textContent); } catch (e) {}
  window.LANG = document.documentElement.lang || 'es';
  window.t = function (clave, vars) {
    vars = vars || {};
    var v = clave.split('.').reduce(function (o, k) { return o == null ? undefined : o[k]; }, d);
    if (v && typeof v === 'object' && 'n' in vars) v = Number(vars.n) === 1 ? v.uno : v.otros;
    if (typeof v !== 'string') return clave;
    return v.replace(/\{(\w+)\}/g, function (_, k) { return k in vars ? String(vars[k]) : '{' + k + '}'; });
  };
})();
