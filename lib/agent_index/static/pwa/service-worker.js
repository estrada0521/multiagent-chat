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

