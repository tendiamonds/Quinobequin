// The map's service worker, only for notifications (the next turn on the lock screen; see
// trailmap.py). It caches nothing, so the map is always the one on the site. A tap on a
// notification brings the map back.
self.addEventListener("install", function() { self.skipWaiting(); });
self.addEventListener("activate", function(e) { e.waitUntil(self.clients.claim()); });
self.addEventListener("notificationclick", function(e) {
  e.notification.close();
  e.waitUntil(self.clients.matchAll({type: "window", includeUncontrolled: true}).then(function(list) {
    for (var i = 0; i < list.length; i++) {
      if ("focus" in list[i]) return list[i].focus();
    }
    return self.clients.openWindow("map.html");
  }));
});
