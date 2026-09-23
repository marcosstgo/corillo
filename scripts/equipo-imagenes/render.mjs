import { chromium } from '/home/corillo-adm/.npm-global/lib/node_modules/playwright/index.mjs';
const b = await chromium.launch({ executablePath: '/home/corillo-adm/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome' });
const jobs=[['og',1200,630,'og-equipo'],['novato',1000,1500,'pin-setup-del-novato'],['serio',1000,1500,'pin-streamer-serio'],['nadie',1000,1500,'pin-accesorios-nadie-menciona'],['todo',1000,1500,'pin-equipo-recomendado']];
for (const [t,w,h,n] of jobs){ const p=await b.newPage({viewport:{width:w,height:h}}); await p.goto('http://127.0.0.1:8765/tpl.html?t='+t); await p.evaluate(()=>document.fonts.ready); await p.waitForTimeout(400);
 const fonts=await p.evaluate(()=>[...document.fonts].filter(f=>f.status==='loaded').map(f=>f.family).join(','));
 await p.screenshot({path:n+'.png'}); console.log(n,fonts); }
await b.close();
