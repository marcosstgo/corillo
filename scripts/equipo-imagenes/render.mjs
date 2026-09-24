import { chromium } from '/home/corillo-adm/.npm-global/lib/node_modules/playwright/index.mjs';
const b = await chromium.launch({ executablePath: '/home/corillo-adm/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome' });
// Uso: node render.mjs [nombre…]  (sin nombres: todas). Sirve public/ en BASE (por defecto :8765).
const BASE=process.env.BASE||'http://127.0.0.1:8765';
const todos=[['og',1200,630,'og-equipo'],['mercado',1200,630,'og-mercado'],['novato',1000,1500,'pin-setup-del-novato'],['serio',1000,1500,'pin-streamer-serio'],['nadie',1000,1500,'pin-accesorios-nadie-menciona'],['todo',1000,1500,'pin-equipo-recomendado']];
const pedir=process.argv.slice(2), jobs=pedir.length?todos.filter(j=>pedir.includes(j[3])):todos;
for (const [t,w,h,n] of jobs){ const p=await b.newPage({viewport:{width:w,height:h}}); await p.goto(BASE+'/tpl.html?t='+t); await p.evaluate(()=>document.fonts.ready); await p.waitForTimeout(400);
 const fonts=await p.evaluate(()=>[...document.fonts].filter(f=>f.status==='loaded').map(f=>f.family).join(','));
 await p.screenshot({path:n+'.png'}); console.log(n,fonts); }
await b.close();
