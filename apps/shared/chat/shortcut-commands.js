    let _shortcutCommandsCache = null;
    const loadShortcutCommandsOnce = async () => {
      if (_shortcutCommandsCache) return _shortcutCommandsCache;
      const r = await fetch("/shortcut-commands", { cache: "no-store" });
      if (!r.ok) throw new Error("shortcut-commands failed");
      const j = await r.json();
      const commands = Array.isArray(j.commands) ? j.commands : [];
      const list = document.documentElement.dataset.mobile === "1"
        ? commands.filter((command) => !command.desktop_only)
        : commands;
      if (!list.length) throw new Error("empty shortcut commands");
      _shortcutCommandsCache = list;
      return list;
    };
    const parseSlashCommandInput = (rawInput, list) => {
      const normalized = rawInput.trim();
      const sorted = [...list].sort((a, b) => String(b.slash || "").length - String(a.slash || "").length);
      for (const c of sorted) {
        const slash = String(c.slash || "");
        if (!slash.startsWith("/")) continue;
        if (normalized === slash) {
          return { id: c.id, arg: "", path: c.path, insert: c.insert || "" };
        }
        if (c.has_arg && normalized.startsWith(slash + " ")) {
          return { id: c.id, arg: normalized.slice(slash.length + 1), path: c.path };
        }
      }
      return null;
    };
