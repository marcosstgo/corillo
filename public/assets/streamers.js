/* Fallback de emergencia — la fuente de verdad es PocketBase vía /api/streamers.
   Actualizar solo si PocketBase cambia y el API no está disponible. */
window.STREAMERS = [
  { key:'katatonia',     name:'Kata',          sub:'Design · Corillo DEV',        ava:'K', color:'linear-gradient(135deg,#e8c84a,#c09020)', host:true,  category:'Tecnología'   },
  { key:'tea',           name:'TEA',           sub:'Call of Duty Streamer',        ava:'T', color:'linear-gradient(135deg,#f9a8d4,#d0408a)', host:false, category:'Gaming'       },
  { key:'404_notfound',  name:'404_NotFound',  sub:'Manatí, Puerto Rico',          ava:'4', color:'linear-gradient(135deg,#a29bfe,#6c5ce7)', host:false, category:'Gaming'       },
  { key:'marcos',        name:'Marcos',        sub:'Artista Gráfico · Dev Corillo',ava:'M', color:'linear-gradient(135deg,#74b9ff,#0984e3)', host:false, category:'Tecnología'   },
  { key:'streamerpro',   name:'STREAMERPRO',   sub:'',                             ava:'S', color:'linear-gradient(135deg,#00cec9,#00838f)', host:false, category:'Tecnología'   },
  { key:'adrian',        name:'Adrián',        sub:'',                             ava:'A', color:'linear-gradient(135deg,#ff7675,#d63031)', host:false, category:'Gaming'       },
{ key:null, name:'???', sub:'Próximamente · Invitación', ava:'?', color:'linear-gradient(135deg,#2a2a3a,#1a1a28)', host:false, soon:true },
];
