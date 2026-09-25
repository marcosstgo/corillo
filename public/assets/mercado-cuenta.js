/* Sesión de CORILLO para las páginas del Mercado, sin cargar el SDK de PocketBase.
   Usa el mismo lugar que el SDK (localStorage.pocketbase_auth), así la sesión es la misma en todo el sitio. */
(function () {
  var PB = window.MK_PB || 'https://pb.corillo.live';   // MK_PB solo lo cambian las pruebas locales
  function leer() {
    try {
      var a = JSON.parse(localStorage.getItem('pocketbase_auth') || 'null');
      if (!a || !a.token) return null;
      var p = JSON.parse(atob(String(a.token).split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
      if (!p.exp || p.exp * 1000 < Date.now() + 60000) return null;
      return { token: a.token, record: a.record || a.model || {} };
    } catch (e) { return null; }
  }
  function guardar(token, record) {
    try { localStorage.setItem('pocketbase_auth', JSON.stringify({ token: token, record: record })); } catch (e) {}
  }
  window.MkCuenta = {
    sesion: leer,
    salir: function () { try { localStorage.removeItem('pocketbase_auth'); } catch (e) {} },
    entrar: function (email, password) {
      return fetch(PB + '/api/collections/streamers/auth-with-password', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identity: email, password: password }),
      }).then(function (r) {
        return r.json().then(function (j) {
          if (!r.ok) throw new Error((j && j.message) || 'login');
          guardar(j.token, j.record);
          return { token: j.token, record: j.record };
        });
      });
    },
    /** fetch a /api/mercado con la sesión. Devuelve {ok, status, j}. 401 borra la sesión vencida. */
    api: function (ruta, opts) {
      opts = opts || {};
      var s = leer(), h = opts.headers || {};
      if (s) h.Authorization = s.token;
      if (opts.json !== undefined) { h['Content-Type'] = 'application/json'; opts.body = JSON.stringify(opts.json); }
      return fetch('/api/mercado' + ruta, { method: opts.method || 'GET', headers: h, body: opts.body })
        .then(function (r) {
          if (r.status === 401) window.MkCuenta.salir();
          if (r.status === 204) return { ok: true, status: 204, j: {} };
          return r.json().catch(function () { return {}; }).then(function (j) { return { ok: r.ok, status: r.status, j: j }; });
        })
        .catch(function () { return { ok: false, status: 0, j: { detail: window.t ? t('comun.sin_conexion') : 'Sin conexión' } }; });
    },
  };
})();
