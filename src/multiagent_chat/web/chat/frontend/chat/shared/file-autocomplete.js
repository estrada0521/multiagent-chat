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
    const basename = (path) => {
      const parts = String(path || "").split("/");
      return parts[parts.length - 1] || path;
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
    const subsequenceScore = (text, query) => {
      let qi = 0;
      let spanStart = -1;
      let lastMatch = -1;
      let gaps = 0;
      for (let i = 0; i < text.length && qi < query.length; i++) {
        if (text[i] !== query[qi]) continue;
        if (spanStart === -1) spanStart = i;
        if (lastMatch !== -1) gaps += i - lastMatch - 1;
        lastMatch = i;
        qi += 1;
      }
      if (qi !== query.length) return null;
      const span = lastMatch - spanStart + 1;
      return { spanStart, span, gaps };
    };
    const scoreFileMatch = (path, rawQuery) => {
      const query = (rawQuery || "").trim().toLowerCase();
      if (!query) return null;
      const full = String(path || "").toLowerCase();
      const base = basename(full);
      const stem = base.replace(/\.[^.]+$/, "");
      const segments = full.split(/[\\/._\\-\\s]+/).filter(Boolean);
      if (base === query) return 1000;
      if (stem === query) return 980;
      if (base.startsWith(query)) return 900 - (base.length - query.length);
      if (stem.startsWith(query)) return 880 - (stem.length - query.length);
      if (segments.includes(query)) return 860;
      const baseIdx = base.indexOf(query);
      if (baseIdx !== -1) return 760 - baseIdx;
      const stemIdx = stem.indexOf(query);
      if (stemIdx !== -1) return 740 - stemIdx;
      const fullIdx = full.indexOf(query);
      if (fullIdx !== -1) return 640 - Math.min(fullIdx, 200);
      const stemSubseq = subsequenceScore(stem, query);
      if (stemSubseq) return 540 - stemSubseq.gaps * 3 - stemSubseq.spanStart * 2 - stemSubseq.span;
      const baseSubseq = subsequenceScore(base, query);
      if (baseSubseq) return 520 - baseSubseq.gaps * 3 - baseSubseq.spanStart * 2 - baseSubseq.span;
      const fullSubseq = subsequenceScore(full, query);
      if (fullSubseq) return 360 - fullSubseq.gaps * 2 - fullSubseq.spanStart - fullSubseq.span;
      return null;
    };
    const findFileMatches = (files, query) => files
      .map((entry) => ({ entry, score: scoreFileMatch(entry.path, query) }))
      .filter((item) => item.score !== null)
      .sort((a, b) => b.score - a.score || a.entry.path.length - b.entry.path.length || a.entry.path.localeCompare(b.entry.path))
      .slice(0, 30)
      .map((item) => item.entry);
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
    const bestScoredFileMatch = (files, query) => {
      if (!Array.isArray(files) || !files.length) return null;
      let best = null;
      let second = null;
      for (const entry of files) {
        const path = String(entry?.path || "");
        if (!path) continue;
        const score = scoreFileMatch(path, query);
        if (score === null) continue;
        const candidate = { path, score };
        if (!best || score > best.score || (score === best.score && path.length < best.path.length)) {
          second = best;
          best = candidate;
          continue;
        }
        if (!second || score > second.score || (score === second.score && path.length < second.path.length)) {
          second = candidate;
        }
      }
      if (!best) return null;
      return { best, secondScore: second ? second.score : Number.NEGATIVE_INFINITY };
    };
    const resolveInlineFilePathFromList = (files, query) => {
      if (!Array.isArray(files) || !files.length) return "";
      const variants = new Set([query, query.replace(/^\.\/+/, "").replace(/\\/g, "/")]);
      if (query.startsWith("/")) variants.add(query.replace(/^\/+/, ""));
      if (query.startsWith("~/")) variants.add(query.slice(2));
      for (const variant of variants) {
        const lowered = String(variant || "").toLowerCase();
        if (!lowered) continue;
        const exact = files.find((entry) => String(entry?.path || "").toLowerCase() === lowered);
        if (exact?.path) return String(exact.path);
      }
      if (query.startsWith("/")) {
        const lowered = query.toLowerCase();
        const suffixMatches = files.filter((entry) => {
          const rel = String(entry?.path || "");
          if (!rel) return false;
          const relLower = rel.toLowerCase();
          return lowered === relLower || lowered.endsWith(`/${relLower}`);
        });
        if (suffixMatches.length === 1 && suffixMatches[0]?.path) return String(suffixMatches[0].path);
      }
      const queryBase = basename(query).toLowerCase();
      const queryStem = queryBase.replace(/\.[^.]+$/, "");
      const queryLoose = normalizedLooseFileToken(queryStem);
      const baseCandidates = files.filter((entry) => {
        const rel = String(entry?.path || "");
        if (!rel) return false;
        const relBase = basename(rel).toLowerCase();
        const relStem = relBase.replace(/\.[^.]+$/, "");
        if (relBase === queryBase || relStem === queryStem) return true;
        return queryLoose && normalizedLooseFileToken(relStem) === queryLoose;
      });
      if (baseCandidates.length === 1 && baseCandidates[0]?.path) return String(baseCandidates[0].path);
      const queryVariants = [query];
      const stemOnly = query.replace(/\.[^.]+$/, "");
      if (stemOnly && stemOnly !== query) queryVariants.push(stemOnly);
      if (query.includes("-")) queryVariants.push(query.replace(/-/g, "_"));
      if (query.includes("_")) queryVariants.push(query.replace(/_/g, "-"));
      let bestCandidate = null;
      const seenVariant = new Set();
      for (const variant of queryVariants) {
        const key = String(variant || "").trim().toLowerCase();
        if (!key || seenVariant.has(key)) continue;
        seenVariant.add(key);
        const scored = bestScoredFileMatch(files, variant);
        if (!scored) continue;
        if (
          !bestCandidate
          || scored.best.score > bestCandidate.best.score
          || (
            scored.best.score === bestCandidate.best.score
            && scored.best.path.length < bestCandidate.best.path.length
          )
        ) {
          bestCandidate = scored;
        }
      }
      if (!bestCandidate) return "";
      const loweredQuery = query.toLowerCase();
      const hasPathHints = /[\/._-]/.test(loweredQuery);
      if (!hasPathHints) return "";
      const bestScore = bestCandidate.best.score;
      const scoreGap = bestScore - bestCandidate.secondScore;
      const threshold = loweredQuery.includes("/")
        ? 620
        : loweredQuery.includes(".")
          ? 740
          : 860;
      const minGap = loweredQuery.includes("/") ? 70 : 110;
      if (bestScore >= threshold && (scoreGap >= minGap || bestScore >= 960)) {
        return bestCandidate.best.path;
      }
      return "";
    };
    const scheduleInlineFileListWarmup = () => {
      if (_inlineFileLinkWarmupStarted) return;
      _inlineFileLinkWarmupStarted = true;
      forceRefreshFileListForLinkify()
        .then(() => {
          if (_inlineFileLinkReplayQueued) return;
          _inlineFileLinkReplayQueued = true;
          requestAnimationFrame(() => {
            _inlineFileLinkReplayQueued = false;
            const root = document.getElementById("messages");
            linkifyInlineCodeFileRefs(root || document);
          });
        })
