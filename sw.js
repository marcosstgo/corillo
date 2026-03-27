// Service Worker — Push notifications
self.addEventListener('push', e => {
  const d = e.data?.json() ?? {};
  e.waitUntil(
    self.registration.showNotification(d.title || 'CORILLO', {
      body: d.body || '',
      icon: '/assets/icon-512.png',
      data: { url: d.url || '/' },
      tag: d.channel,
      renotify: true,
    })
  );
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  e.waitUntil(clients.openWindow(e.notification.data?.url || '/'));
});
