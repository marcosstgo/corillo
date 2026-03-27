// Service Worker — PWA + Push notifications

// Requerido por Chrome para considerar el SW válido para instalación PWA
self.addEventListener('fetch', () => {});

self.addEventListener('push', e => {
  let d = {};
  try { d = e.data?.json() ?? {}; } catch(_) {}
  e.waitUntil(
    self.registration.showNotification(d.title || 'CORILLO', {
      body: d.body || '',
      icon: '/assets/icon-512.png',
      data: { url: d.url || '/' },
      ...(d.channel ? { tag: d.channel, renotify: true } : {}),
    })
  );
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  e.waitUntil(clients.openWindow(e.notification.data?.url || '/'));
});
