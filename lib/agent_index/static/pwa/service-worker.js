"use strict";

const SW_VERSION = "20260331-1";
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
      `${prefix}/pwa-icon-192.png`,
      `${prefix}/pwa-icon-512.png`,
      `${prefix}/apple-touch-icon.png`,
    ]
  : [
      `${prefix}/app.webmanifest`,
      `${prefix}/pwa-icon-192.png`,
      `${prefix}/pwa-icon-512.png`,
      `${prefix}/apple-touch-icon.png`,
      `${prefix}/chat-assets/chat-app.js`,
      `${prefix}/chat-assets/chat-app.css`,
    ];

function shouldHandle(url) {
  if (url.origin !== scopeUrl.origin) return false;
  const path = url.pathname;
  if (staticPaths.includes(path)) return true;
  if (isHubScope) return false;
  return (
    path.startsWith(`${prefix}/chat-assets/`) ||
    path.startsWith(`${prefix}/font/`) ||
    path.startsWith(`${prefix}/icon/`)
  );
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
  if (!shouldHandle(url)) return;

  event.respondWith((async () => {
    const cache = await caches.open(cacheName);
    const cached = await cache.match(request);
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
