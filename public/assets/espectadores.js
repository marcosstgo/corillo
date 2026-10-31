/* Cuántas PERSONAS están viendo un canal (31-oct-2026).
   mediamtx cuenta como "readers" también a sus procesos internos: el ffmpeg que hace la variante 720p (_low) lee el
   canal por RTSP, y el de WebRTC (_rtc) también. Eso inflaba el contador en +1. Y quien ve la variante 720p o por
   WebRTC queda en live/<canal>_low o live/<canal>_rtc, que no se sumaban.
   Aquí: solo sesiones de gente (HLS y WebRTC), sumando live/<canal>, _low y _rtc.
   Uso: corilloEspectadores(itemsDeMediamtx, 'katatonia') */
window.corilloEspectadores = function (paths, key) {
  var gente = function (r) { return r && (r.type === 'hlsSession' || r.type === 'webRTCSession'); };
  var n = 0;
  ['', '_low', '_rtc'].forEach(function (sufijo) {
    var p = (paths || []).find(function (x) { return x.name === 'live/' + key + sufijo; });
    if (p) n += (p.readers || []).filter(gente).length;
  });
  return n;
};
