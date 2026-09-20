/* Discord en vivo — lee el widget PÚBLICO del servidor (lo habilitó el admin) y lo normaliza.
   window.CorilloDiscord.load() -> Promise<{online, total, invite, members[], voice[], games[]}>
   Caché de 5 min en sessionStorage (Discord también cachea 5 min). Sin datos privados: solo lo que el widget publica. */
(function () {
  var GID = '240118405116461056';
  var WIDGET = 'https://discord.com/api/guilds/' + GID + '/widget.json';
  var TTL = 5 * 60 * 1000;
  function getJSON(url) { return fetch(url, { signal: AbortSignal.timeout(7000) }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }); }
  function cached(key, fn) {
    try { var c = JSON.parse(sessionStorage.getItem(key) || 'null'); if (c && Date.now() - c.t < TTL) return Promise.resolve(c.d); } catch (e) {}
    return fn().then(function (d) { try { sessionStorage.setItem(key, JSON.stringify({ t: Date.now(), d: d })); } catch (e) {} return d; });
  }
  function load(inviteCode) {
    return cached('cd_live_v1', function () {
      var inv = inviteCode ? getJSON('https://discord.com/api/v10/invites/' + inviteCode + '?with_counts=true').catch(function () { return null; }) : Promise.resolve(null);
      return Promise.all([getJSON(WIDGET), inv]).then(function (r) {
        var w = r[0], i = r[1];
        var names = {}; (w.channels || []).forEach(function (c) { names[c.id] = c.name; });
        // el widget también lista bots (p. ej. "in 2640 servers"): se descartan
        var BOTS = /^(mee6|streamcord|corillo bot|carl-bot|dyno|probot|mudae|groovy|rythm)$/i;
        var members = (w.members || []).filter(function (m) { return !BOTS.test(m.username || '') && !(m.game && /^in \d+ servers?$/i.test(m.game.name || '')); })
          .map(function (m) { return { name: m.username, avatar: m.avatar_url, status: m.status, game: m.game ? m.game.name.replace(/[™®]/g, '').replace(/\s+/g, ' ').trim() : '', channel: m.channel_id || '' }; });
        var byGame = {}; members.forEach(function (m) { if (m.game) byGame[m.game] = (byGame[m.game] || 0) + 1; });
        var games = Object.keys(byGame).map(function (g) { return { name: g, count: byGame[g] }; }).sort(function (a, b) { return b.count - a.count; });
        var voice = (w.channels || []).map(function (c) { return { id: c.id, name: c.name, pos: c.position, members: members.filter(function (m) { return m.channel === c.id; }) }; }).sort(function (a, b) { return (b.members.length - a.members.length) || (a.pos - b.pos); });
        return { online: members.length, total: i ? i.approximate_member_count : null, members: members, voice: voice, games: games };
      });
    });
  }
  window.CorilloDiscord = { load: load };
})();
