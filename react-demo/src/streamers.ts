export interface Streamer {
  key: string | null;
  name: string;
  sub: string;
  ava: string;
  color: string;
  host?: boolean;
  soon?: boolean;
}

export const STREAMERS: Streamer[] = [
  { key: 'katatonia',      name: 'KATATONIA',      sub: 'Gaming · Aibonito PR',     ava: 'K', color: 'linear-gradient(135deg,#e8c84a,#c09020)', host: true },
  { key: 'tea',            name: 'TEA',             sub: 'Just chatting · vibes',    ava: 'T', color: 'linear-gradient(135deg,#f9a8d4,#d0408a)' },
  { key: 'mira_sanganooo', name: 'MIRA_SANGANOOO',  sub: 'Contenido · Florida USA',  ava: 'M', color: 'linear-gradient(135deg,#ff9f43,#e06010)' },
  { key: '404',            name: '404',             sub: 'Gaming · Manatí PR',       ava: '4', color: 'linear-gradient(135deg,#a29bfe,#6c5ce7)' },
  { key: 'elbala',         name: 'ELBALA',          sub: 'Gaming · Entretenimiento', ava: 'E', color: 'linear-gradient(135deg,#55efc4,#00b894)' },
  { key: 'marcos',         name: 'MARCOS',          sub: 'Gaming · Aibonito PR',     ava: 'M', color: 'linear-gradient(135deg,#74b9ff,#0984e3)' },
  { key: 'pataecabra',     name: 'PATAECABRA',      sub: 'Gaming · Ponce PR',        ava: 'P', color: 'linear-gradient(135deg,#ff7675,#d63031)' },
  { key: 'streamerpro',    name: 'STREAMERPRO',     sub: 'Gaming · Puerto Rico',     ava: 'S', color: 'linear-gradient(135deg,#00cec9,#00838f)' },
  { key: 'radblaster',     name: 'RADBLASTER',      sub: 'Gaming · Puerto Rico',     ava: 'R', color: 'linear-gradient(135deg,#fd79a8,#e84393)' },
  { key: 'elhermanoquiles', name: 'ELHERMANOQUILES', sub: 'Gaming · Puerto Rico',    ava: 'E', color: 'linear-gradient(135deg,#fdcb6e,#e17055)' },
  { key: 'xxdur3xx',       name: 'XXDUR3XX',        sub: 'Gaming · Ponce PR',        ava: 'X', color: 'linear-gradient(135deg,#e17055,#c0392b)' },
  { key: 'kamikazepr',     name: 'KAMIKAZEPR',      sub: 'Gaming · Puerto Rico',     ava: 'K', color: 'linear-gradient(135deg,#ff4757,#8e0a20)' },
  { key: 'superman',       name: 'SUPERMAN',        sub: 'Gaming · Puerto Rico',     ava: 'S', color: 'linear-gradient(135deg,#fd79a8,#e84393)' },
  { key: null,             name: '???',             sub: 'Próximamente · Invitación', ava: '?', color: 'linear-gradient(135deg,#2a2a3a,#1a1a28)', soon: true },
];
