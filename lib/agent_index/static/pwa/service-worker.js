"use strict";

const SW_VERSION = "20260419-1";
const scopeUrl = new URL(self.registration.scope);
const scopePath = scopeUrl.pathname.replace(/\/$/, "");
const scriptPath = new URL(self.location.href).pathname;
const isHubScope = scriptPath.endsWith("/hub-service-worker.js");
const prefix = scopePath || "";
const cacheNamespace = `agent-index-${isHubScope ? "hub" : "chat"}`;
const cacheName = `${cacheNamespace}-${SW_VERSION}`;

const staticPaths = isHubScope
  ? [
      `${prefix}/hub.webmanifest`,
      `${prefix}/hub-launch-shell.html`,
      `${prefix}/pwa-icon-192.png`,
      `${prefix}/pwa-icon-512.png`,
      `${prefix}/apple-touch-icon.png`,
    ]
  : [
      `${prefix}/app.webmanifest`,
      `${prefix}/pwa-icon-192.png`,
      `${prefix}/pwa-icon-512.png`,
      `${prefix}/apple-touch-icon.png`,
    ];

function shouldHandle(url) {
  if (url.origin !== scopeUrl.origin) return false;
  const path = url.pathname;
  if (staticPaths.includes(path)) return true;
  if (isHubScope) return false;
  return (
    path.startsWith(`${prefix}/font/`) ||
    path.startsWith(`${prefix}/icon/`)
  );
}

function isNetworkFirstAsset(url) {
  if (isHubScope) return false;
  return false;
}

function isHubLaunchNavigation(request, url) {
  if (!isHubScope) return false;
  if (request.mode !== "navigate") return false;
  const path = url.pathname || "/";
  if (!prefix) return path === "/" || path === "/index.html";
  return path === `${prefix}/` || path === `${prefix}/index.html`;
}

function defaultNotificationUrl() {
  return `${scopePath || ""}/?follow=1`;
}

function bestClientForTarget(windowClients, targetUrl) {
  let bestClient = null;
  let bestScore = -1;
  for (const client of windowClients) {
    const clientUrl = client?.url || "";
    if (!clientUrl) continue;
    let current;
    try {
      current = new URL(clientUrl);
    } catch (_err) {
      continue;
    }
    if (current.origin !== targetUrl.origin) continue;
    let score = 1;
    if (current.pathname === targetUrl.pathname) score = 3;
    if (current.pathname === targetUrl.pathname && current.search === targetUrl.search) score = 4;
    if (score > bestScore) {
      bestScore = score;
      bestClient = client;
    }
  }
  return bestClient;
}

function urlB64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4 || 4)) % 4);
  const normalized = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(normalized);
  return Uint8Array.from(raw, (char) => char.charCodeAt(0));
}

async function maybeResubscribeFromConfig(clientId = "service-worker") {
  if (!isHubScope || !self.registration?.pushManager) return;
  try {
    const response = await fetch(`${prefix}/push-config`, { cache: "no-store" });
    if (!response.ok) return;
    const config = await response.json();
    const publicKey = typeof config?.public_key === "string" ? config.public_key : "";
    if (!publicKey) return;
    const subscription = await self.registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlB64ToUint8Array(publicKey),
    });
    const payload = {
      client_id: clientId,
      subscription: subscription?.toJSON ? subscription.toJSON() : subscription,
    };
    await fetch(`${prefix}/push/subscribe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (_err) {
    // Ignore push subscription refresh failures.
  }
}

async function putIfOk(cache, request, response) {
  if (response && response.ok) {
    await cache.put(request, response.clone());
  }
  return response;
}

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(cacheName);
    await Promise.all(staticPaths.map(async (path) => {
      try {
        const response = await fetch(path, { cache: "no-store" });
        await putIfOk(cache, path, response);
      } catch (_err) {
        // Ignore install-time fetch failures; runtime fetch can still populate the cache.
      }
    }));
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.map((key) => {
      if (key.startsWith(cacheNamespace) && key !== cacheName) {
        return caches.delete(key);
      }
      return Promise.resolve(false);
    }));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);

  if (isHubLaunchNavigation(request, url)) {
    event.respondWith((async () => {
      const cache = await caches.open(cacheName);
      try {
        const freshShell = await fetch(`${prefix}/hub-launch-shell.html`, { cache: "no-store" });
        if (freshShell && freshShell.ok) {
          await cache.put(`${prefix}/hub-launch-shell.html`, freshShell.clone());
          return freshShell;
        }
      } catch (_err) {
        // Fallback to cache below when offline/unreachable.
      }
      const shell = await cache.match(`${prefix}/hub-launch-shell.html`);
      if (shell) return shell;
      return fetch(request);
    })());
    return;
  }

  if (!shouldHandle(url)) return;

  event.respondWith((async () => {
    const cache = await caches.open(cacheName);
    const cached = await cache.match(request);
    if (isNetworkFirstAsset(url)) {
      try {
        const response = await fetch(request, { cache: "no-store" });
        return await putIfOk(cache, request, response);
      } catch (err) {
        if (cached) return cached;
        throw err;
      }
    }

    if (cached) {
      event.waitUntil(
        fetch(request)
          .then((response) => putIfOk(cache, request, response))
          .catch(() => undefined)
      );
      return cached;
    }

    try {
      const response = await fetch(request);
      return await putIfOk(cache, request, response);
    } catch (err) {
      const fallback = await cache.match(request);
      if (fallback) return fallback;
      throw err;
    }
  })());
});

self.addEventListener("push", (event) => {
  event.waitUntil((async () => {
    let payload = {};
    try {
      payload = event.data ? await event.data.json() : {};
    } catch (_err) {
      try {
        payload = { body: event.data ? await event.data.text() : "" };
      } catch (_err2) {
        payload = {};
      }
    }
    const title = typeof payload?.title === "string" && payload.title
      ? payload.title
      : "multiagent";
    const options = {
      body: typeof payload?.body === "string" && payload.body ? payload.body : "New agent reply",
      tag: typeof payload?.tag === "string" && payload.tag ? payload.tag : `push-${Date.now()}`,
      renotify: !!payload?.renotify,
      icon: typeof payload?.icon === "string" && payload.icon ? payload.icon : `${prefix}/pwa-icon-192.png`,
      badge: typeof payload?.badge === "string" && payload.badge ? payload.badge : `${prefix}/pwa-icon-192.png`,
      data: {
        url: typeof payload?.url === "string" && payload.url ? payload.url : defaultNotificationUrl(),
        session: typeof payload?.session === "string" ? payload.session : "",
      },
    };
    await self.registration.showNotification(title, options);
  })());
});

self.addEventListener("pushsubscriptionchange", (event) => {
  event.waitUntil(maybeResubscribeFromConfig("service-worker"));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const rawUrl = event.notification?.data?.url || defaultNotificationUrl();
  const target = new URL(rawUrl, scopeUrl);
  const targetUrl = target.toString();
  event.waitUntil((async () => {
    const windowClients = await clients.matchAll({ type: "window", includeUncontrolled: true });
    const bestClient = bestClientForTarget(windowClients, target);
    if (bestClient) {
      if ("navigate" in bestClient) {
        try {
          await bestClient.navigate(targetUrl);
        } catch (_err) {
          // Ignore and fall through to focus/open.
        }
      }
      if ("focus" in bestClient) {
        return bestClient.focus();
      }
    }
    return clients.openWindow(targetUrl);
  })());
});
