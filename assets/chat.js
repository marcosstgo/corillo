/* ── CHAT SHARED JS — loaded by all individual channel pages ── */
/* Requires: player.js loaded first (provides `channel` global) */

// ── CHAT VISIBILITY ──
let chatVisible = localStorage.getItem('corillo_chat') === 'visible';

function showChat() {
  chatVisible = true;
  localStorage.setItem('corillo_chat', 'visible');
  $('#content').classList.remove('chat-hidden');
  $('#chatFab').classList.remove('visible');
  if ($('#chatToggleBtn')) $('#chatToggleBtn').classList.add('active');
}

function hideChat() {
  chatVisible = false;
  localStorage.setItem('corillo_chat', 'hidden');
  $('#content').classList.add('chat-hidden');
  $('#chatFab').classList.add('visible');
  if ($('#chatToggleBtn')) $('#chatToggleBtn').classList.remove('active');
}

if (!chatVisible) {
  $('#content').classList.add('chat-hidden');
  $('#chatFab').classList.add('visible');
} else {
  if ($('#chatToggleBtn')) $('#chatToggleBtn').classList.add('active');
}

if ($('#chatToggleBtn')) $('#chatToggleBtn').addEventListener('click', () => chatVisible ? hideChat() : showChat());
if ($('#chatCloseBtn'))  $('#chatCloseBtn').addEventListener('click', hideChat);
$('#chatFab').addEventListener('click', showChat);

// ── WEBSOCKET CHAT ──
const WS_BASE = location.protocol === 'https:' ? 'wss:' : 'ws:';
const _savedUser = localStorage.getItem('corillo_username') || '';
const WS_URL  = `${WS_BASE}//${location.host}/chat-api/ws/${channel}${_savedUser ? '?user=' + encodeURIComponent(_savedUser) : ''}`;

let ws = null, wsTimer = null, _wsRetries = 0;

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function userColor(name) {
  const palette = ['#e8c84a','#4ade80','#60a5fa','#f472b6','#fb923c','#a78bfa','#34d399','#f87171','#38bdf8','#facc15'];
  let h = 0;
  for (let i = 0; i < name.length; i++) h = name.charCodeAt(i) + ((h << 5) - h);
  return palette[Math.abs(h) % palette.length];
}

function addChatMsg(msg) {
  const box = $('#chatMsgs');
  const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 60;
  const el = document.createElement('div');
  if (msg.type === 'system') {
    el.className = 'chat-msg is-system';
    el.textContent = msg.text;
  } else {
    const color = msg.bot ? '#9147ff' : userColor(msg.user);
    el.className = 'chat-msg' + (msg.bot ? ' is-bot' : '');
    el.innerHTML = `<span class="msg-user" style="color:${color}">${escHtml(msg.user)}:</span> <span class="msg-text">${escHtml(msg.text)}</span>`;
  }
  box.appendChild(el);
  if (atBottom) box.scrollTop = box.scrollHeight;
}

function connectWs() {
  if (ws && ws.readyState < 2) return;
  ws = new WebSocket(WS_URL);
  ws.onopen = () => { clearTimeout(wsTimer); _wsRetries = 0; };
  ws.onmessage = ({ data }) => {
    try {
      const msg = JSON.parse(data);
      if (msg.type === 'welcome') {
        localStorage.setItem('corillo_username', msg.user);
        if ($('#chatYou')) $('#chatYou').textContent = msg.user;
        return;
      }
      addChatMsg(msg);
    } catch {}
  };
  ws.onclose = () => {
    // Backoff exponencial: 3s → 4.5s → 6.75s → … → 30s máx
    // Evita tormenta de reconexiones si el servidor cae y vuelve
    const delay = Math.min(30000, 3000 * Math.pow(1.5, _wsRetries));
    _wsRetries++;
    wsTimer = setTimeout(connectWs, delay);
  };
  ws.onerror = () => ws.close();
}

function sendMsg() {
  const input = $('#chatInput');
  const text = input.value.trim();
  if (!text || !ws || ws.readyState !== 1) return;
  ws.send(JSON.stringify({ text }));
  input.value = '';
}

$('#chatSend').addEventListener('click', sendMsg);
$('#chatInput').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMsg(); }
});

// On mobile: scroll the input row into view after the virtual keyboard opens
$('#chatInput').addEventListener('focus', function() {
  setTimeout(() => this.closest('.chat-input-wrap').scrollIntoView({ behavior: 'smooth', block: 'end' }), 350);
});

connectWs();
