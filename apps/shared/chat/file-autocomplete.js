    const showFileAutocompleteLoading = () => {
      fileDrop.innerHTML = `<div class="file-dropdown-loading">${loadingIndicatorHtml("Searching files…")}</div>`;
      _dropActiveIdx = -1;
      positionComposerDropdown(fileDrop);
      if (!fileDrop.classList.contains("visible")) {
        if (_dropTimeout) { clearTimeout(_dropTimeout); _dropTimeout = null; }
        fileDrop.classList.remove("closing");
        fileDrop.style.display = "block";
        fileDrop.classList.add("visible");
        closePlusMenu();
      }
    };
    const _scoreFileMatchCache = new Map();
    let _scoreFileMatchCacheEntryCount = 0;
    const SCORE_FILE_MATCH_CACHE_HARD_MAX = 300000;
    const _basenameCache = new Map();
    const BASENAME_CACHE_MAX = 65536;
    const _stemByBaseCache = new Map();
    const STEM_BY_BASE_MAX = 65536;
    const fileStemFromBase = (base) => {
      const cachedStem = _stemByBaseCache.get(base);
      if (cachedStem !== undefined) return cachedStem;
      const stem = base.replace(/\.[^.]+$/, "");
      if (_stemByBaseCache.size >= STEM_BY_BASE_MAX) _stemByBaseCache.clear();
      _stemByBaseCache.set(base, stem);
      return stem;
    };
    const clearFileAutocompleteScoreCache = () => {
      _scoreFileMatchCache.clear();
      _scoreFileMatchCacheEntryCount = 0;
      _basenameCache.clear();
      _stemByBaseCache.clear();
    };
    const basename = (path) => {
      const s = String(path || "");
      const cachedBase = _basenameCache.get(s);
      if (cachedBase !== undefined) return cachedBase;
      const i = Math.max(s.lastIndexOf("/"), s.lastIndexOf("\\"));
      const b = i === -1 ? s : s.slice(i + 1);
      if (_basenameCache.size >= BASENAME_CACHE_MAX) _basenameCache.clear();
      _basenameCache.set(s, b);
      return b;
    };
    const composerAutocompleteRelativeDir = (fullPath) => {
      let p = String(fullPath || "").trim().replace(/\\/g, "/");
      for (let i = 0; i < 8; i += 1) {
        const next = p.replace(/\/+/g, "/");
        if (next === p) break;
        p = next;
      }
      p = p.replace(/^\/+/, "").replace(/\/+$/g, "");
      if (!p.includes("/")) return "";
      const idx = p.lastIndexOf("/");
      return idx > 0 ? p.slice(0, idx) : "";
    };
    const fileExtForPath = (path) => {
      const base = basename(path);
      const dot = base.lastIndexOf(".");
      return dot >= 0 ? base.slice(dot + 1).toLowerCase() : "";
    };
    const formatFileSize = (size) => {
      const value = Number(size);
      if (!Number.isFinite(value) || value < 0) return "";
      if (value >= 1024 * 1024) {
        const mb = value / (1024 * 1024);
        return `${mb >= 10 ? mb.toFixed(0) : mb.toFixed(1).replace(/\.0$/, "")} MB`;
      }
      if (value === 0) return "0 KB";
      const kb = value / 1024;
      return `${kb >= 10 ? kb.toFixed(0) : kb.toFixed(1).replace(/\.0$/, "")} KB`;
    };
    const isPathSegDelimiter = (ch) => {
      const c = ch.charCodeAt(0);
      return c === 47 || c === 92 || c === 46 || c === 95 || c === 45 || (c <= 32 && c !== 0);
    };
    const pathHasSegmentEqualTo = (full, query) => {
      const n = full.length;
      const qLen = query.length;
      if (!qLen || qLen > n) return false;
      let i = 0;
      while (i < n) {
        while (i < n && isPathSegDelimiter(full[i])) i++;
        if (i >= n) break;
        if (full.startsWith(query, i)) {
          const after = i + qLen;
          if (after === n || isPathSegDelimiter(full[after])) return true;
        }
        while (i < n && !isPathSegDelimiter(full[i])) i++;
      }
      return false;
    };
    const subsequenceScore = (text, query) => {
      const qLen = query.length;
      const tLen = text.length;
      if (!qLen || qLen > tLen) return null;
      let qi = 0;
      let spanStart = -1;
      let lastMatch = -1;
      let gaps = 0;
      let qch = query.charCodeAt(0);
      for (let i = 0; i < tLen && qi < qLen; i++) {
        if (text.charCodeAt(i) !== qch) continue;
        if (spanStart === -1) spanStart = i;
        if (lastMatch !== -1) gaps += i - lastMatch - 1;
        lastMatch = i;
        qi += 1;
        if (qi < qLen) qch = query.charCodeAt(qi);
      }
      if (qi !== qLen) return null;
      const span = lastMatch - spanStart + 1;
      return { spanStart, span, gaps };
    };
    const scoreFileMatch = (path, rawQuery) => {
      const query = (rawQuery || "").trim().toLowerCase();
      if (!query) return null;
      const pathKey = String(path || "");
      let inner = _scoreFileMatchCache.get(pathKey);
      if (inner) {
        const cachedScore = inner.get(query);
        if (cachedScore !== undefined) return cachedScore;
      }
      const full = pathKey.toLowerCase();
      const base = basename(full);
      const stem = fileStemFromBase(base);
      let score = null;
      if (base === query) score = 1000;
      else if (stem === query) score = 980;
      else if (base.startsWith(query)) score = 900 - (base.length - query.length);
      else if (stem.startsWith(query)) score = 880 - (stem.length - query.length);
      else {
        if (pathHasSegmentEqualTo(full, query)) score = 860;
        else {
          const baseIdx = base.indexOf(query);
          if (baseIdx !== -1) score = 760 - baseIdx;
          else {
            const stemIdx = stem.indexOf(query);
            if (stemIdx !== -1) score = 740 - stemIdx;
            else {
              const fullIdx = full.indexOf(query);
              if (fullIdx !== -1) score = 640 - Math.min(fullIdx, 200);
              else {
                const stemSubseq = subsequenceScore(stem, query);
                if (stemSubseq) score = 540 - stemSubseq.gaps * 3 - stemSubseq.spanStart * 2 - stemSubseq.span;
                else {
                  const baseSubseq = subsequenceScore(base, query);
                  if (baseSubseq) score = 520 - baseSubseq.gaps * 3 - baseSubseq.spanStart * 2 - baseSubseq.span;
                  else {
                    const fullSubseq = subsequenceScore(full, query);
                    if (fullSubseq) score = 360 - fullSubseq.gaps * 2 - fullSubseq.spanStart - fullSubseq.span;
                  }
                }
              }
            }
          }
        }
      }
      if (_scoreFileMatchCacheEntryCount >= SCORE_FILE_MATCH_CACHE_HARD_MAX) {
        clearFileAutocompleteScoreCache();
        inner = undefined;
      }
      if (!inner) {
        inner = new Map();
        _scoreFileMatchCache.set(pathKey, inner);
      }
      inner.set(query, score);
      _scoreFileMatchCacheEntryCount += 1;
      return score;
    };
    const FILE_SEARCH_PREFILTER_MIN_LIST = 500;
    const cheapPoolForFileSearch = (files, rawQuery) => {
      const q = String(rawQuery || "").trim().toLowerCase();
      if (!q || q.length < 2 || !Array.isArray(files) || files.length <= FILE_SEARCH_PREFILTER_MIN_LIST) {
        return files;
      }
      const out = [];
      for (let fi = 0; fi < files.length; fi++) {
        const entry = files[fi];
        const p = String(entry?.path || "").toLowerCase();
        if (!p) continue;
        if (p.includes(q)) {
          out.push(entry);
          continue;
        }
        const b = basename(p);
        if (b.includes(q)) out.push(entry);
      }
      return out.length ? out : files;
    };
    const findFileMatches = (files, query, limit = 30) => {
      const normalizedLimit = Math.max(1, Math.min(120, Number(limit) || 30));
      const pool = cheapPoolForFileSearch(files, query);
      const scored = [];
      for (let i = 0; i < pool.length; i += 1) {
        const entry = pool[i];
        const sc = scoreFileMatch(entry.path, query);
        if (sc !== null) scored.push({ entry, score: sc });
      }
      scored.sort((a, b) => b.score - a.score || a.entry.path.length - b.entry.path.length || a.entry.path.localeCompare(b.entry.path));
      return scored.slice(0, normalizedLimit).map((item) => item.entry);
    };
    const normalizedLooseFileToken = (value) => String(value || "").toLowerCase().replace(/[^a-z0-9]/g, "");
    const parseInlineCodeFileToken = (rawValue) => {
      let token = String(rawValue || "").trim();
      if (!token) return null;
      token = token
        .replace(/^[`"'([{<]+/, "")
        .replace(/[`"')\]}>.,;:!?]+$/g, "")
        .replace(/[、。]+$/g, "")
        .trim();
      if (!token || token.length > 220) return null;
      if (token.startsWith("@")) token = token.slice(1).trim();
      if (!token) return null;
      if (/^[a-z][a-z0-9+.-]*:\/\//i.test(token) && !token.toLowerCase().startsWith("file://")) return null;
      if (token.toLowerCase().startsWith("file://")) {
        try {
          token = decodeURIComponent(new URL(token).pathname || "").trim();
        } catch (_) {
          return null;
        }
      }
      token = token.replace(/\\/g, "/");
      let line = 0;
      const lineMatch = token.match(/^(.*?)(?:#L(\d+)|:(\d+)|\s+line\s+(\d+)|\s+L(\d+))$/i);
      if (lineMatch && lineMatch[1]) {
        const parsedLine = parseInt(lineMatch[2] || lineMatch[3] || lineMatch[4] || lineMatch[5] || "0", 10);
        if (parsedLine > 0) {
          token = lineMatch[1].trim();
          line = parsedLine;
        }
      }
      token = token.replace(/^\.\/+/, "").trim();
      if (!token || token === "." || token === ".." || /\s/.test(token)) return null;
      return { token, line };
    };
