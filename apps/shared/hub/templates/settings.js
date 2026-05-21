    const HUB_EMBED = document.documentElement.dataset.hubEmbed === "1";
    const VIEW_VARIANT = document.documentElement.dataset.viewVariant || "";
    const isMobileView = VIEW_VARIANT === "mobile";

    const boldMobileToggle = isMobileView
      ? document.querySelector('#settingsFormMobile input[name="bold_mode_mobile"]')
      : document.querySelector('#settingsFormDesktop input[name="bold_mode_mobile"]');
    const boldDesktopToggle = isMobileView
      ? document.querySelector('#settingsFormMobile input[name="bold_mode_desktop"]')
      : document.querySelector('#settingsFormDesktop input[name="bold_mode_desktop"]');
    const applyBoldMode = () => {
      const html = document.documentElement;
      const mobileBold = boldMobileToggle?.checked;
      const desktopBold = boldDesktopToggle?.checked;
      const active = (isMobileView && mobileBold) || (!isMobileView && desktopBold);
      if (active) {
        html.dataset.boldMode = '1';
      } else {
        delete html.dataset.boldMode;
      }
    };
    boldMobileToggle?.addEventListener('change', applyBoldMode);
    boldDesktopToggle?.addEventListener('change', applyBoldMode);
    applyBoldMode();

    const _makeNumberStepper = (input, minusBtnId, plusBtnId, valueDisplayId, onApply, options = {}) => {
      if (!input) return;
      const min = Number.isFinite(options.min) ? options.min : 11;
      const max = Number.isFinite(options.max) ? options.max : 18;
      const fallback = Number.isFinite(options.fallback) ? options.fallback : min;
      input.value = String(Math.max(min, Math.min(max, parseInt(input.value, 10) || fallback)));
      const apply = () => {
        const sz = Math.max(min, Math.min(max, parseInt(input.value, 10) || fallback));
        input.value = String(sz);
        const disp = valueDisplayId ? document.getElementById(valueDisplayId) : null;
        if (disp) disp.textContent = sz;
        if (onApply) onApply(sz);
      };
      apply();
      input.addEventListener('input', apply);
      input.addEventListener('change', apply);
      const minus = minusBtnId ? document.getElementById(minusBtnId) : null;
      const plus = plusBtnId ? document.getElementById(plusBtnId) : null;
      const triggerSave = () => { if (typeof _doAutoSave === 'function') { clearTimeout(_autoSaveTimer); _autoSaveTimer = setTimeout(_doAutoSave, 350); } };
      if (minus) minus.addEventListener('click', (e) => { e.preventDefault(); const v = parseInt(input.value, 10) || fallback; const n = Math.max(min, v - 1); if (v !== n) { input.value = n; apply(); triggerSave(); } });
      if (plus) plus.addEventListener('click', (e) => { e.preventDefault(); const v = parseInt(input.value, 10) || fallback; const n = Math.min(max, v + 1); if (v !== n) { input.value = n; apply(); triggerSave(); } });
    };
    const _makeTextSizeStepper = (input, minusBtnId, plusBtnId, valueDisplayId, onApply) => {
      _makeNumberStepper(input, minusBtnId, plusBtnId, valueDisplayId, onApply, { min: 8, max: 18, fallback: 13 });
    };
    let activeTextSizeInput = null;
    if (isMobileView) {
      activeTextSizeInput = document.getElementById('textSizeMobileInput');
      _makeTextSizeStepper(
        activeTextSizeInput,
        'textSizeMobileMinus', 'textSizeMobilePlus', 'textSizeMobileValue',
        (sz) => document.documentElement.style.setProperty('--settings-text-size', sz + 'px')
      );
      _makeTextSizeStepper(
        document.getElementById('textSizeDesktopInput'),
        'textSizeDesktopMinus', 'textSizeDesktopPlus', 'textSizeDesktopValue',
        null
      );
      _makeNumberStepper(document.getElementById('themeBgInput'), 'themeBgMinus', 'themeBgPlus', 'themeBgValue', null, { min: 0, max: 40, fallback: 20 });
      _makeNumberStepper(document.getElementById('themeFgInput'), 'themeFgMinus', 'themeFgPlus', 'themeFgValue', null, { min: 220, max: 255, fallback: 252 });
    } else {
      const desktopInput = document.querySelector('#settingsFormDesktop [name="message_text_size_desktop"]');
      activeTextSizeInput = desktopInput;
      _makeTextSizeStepper(desktopInput, null, null, null,
        (sz) => document.documentElement.style.setProperty('--settings-text-size', sz + 'px')
      );
      const mobileInput = document.querySelector('#settingsFormDesktop [name="message_text_size_mobile"]');
      _makeTextSizeStepper(mobileInput, null, null, null, null);

      const _parentRoot = () => {
        try { return window.self !== window.top ? window.parent.document.documentElement : null; } catch (_) { return null; }
      };
      const sidebarOpacityInput = document.querySelector('#settingsFormDesktop [name="sidebar_opacity"]');
      const chatGlassBlurInput = document.querySelector('#settingsFormDesktop [name="chat_glass_blur"]');
      const chatBgOpacityInput = document.querySelector('#settingsFormDesktop [name="chat_bg_opacity"]');
      _makeNumberStepper(sidebarOpacityInput, null, null, null, (v) => {
        const sidebarShell = window.parent?.document?.querySelector('.desk-sidebar-shell');
        if (sidebarShell) sidebarShell.style.background = `rgba(0,0,0,${(v / 100).toFixed(2)})`;
      }, { min: 0, max: 100, fallback: 90 });
      _makeNumberStepper(chatGlassBlurInput, null, null, null, () => {}, { min: 0, max: 40, fallback: 0 });
      const _applyChatBg = () => {
        const chatShell = window.parent?.document?.querySelector('.desk-chat-shell');
        const chatFrame = window.parent?.document?.querySelector('.desk-chat-frame');
        if (!chatShell) return;
        const opacity = Math.max(0, Math.min(100, parseInt(chatBgOpacityInput?.value, 10) || 100));
        if (opacity < 100) {
          chatShell.style.background = `rgba(0,0,0,${(opacity / 100).toFixed(2)})`;
          if (chatFrame) chatFrame.style.background = 'transparent';
        } else {
          chatShell.style.background = '';
          if (chatFrame) chatFrame.style.background = '';
        }
      };
      _makeNumberStepper(chatBgOpacityInput, null, null, null, _applyChatBg, { min: 0, max: 100, fallback: 100 });
    }

    const activeForm = isMobileView
      ? document.getElementById('settingsFormMobile')
      : document.getElementById('settingsFormDesktop');
    const settingsForm = activeForm;
    if (HUB_EMBED && settingsForm) {
      settingsForm.action = "/settings?embed=1";
    }
    const closeSettingsPage = () => {
      if (HUB_EMBED && window.self !== window.top) {
        window.parent.postMessage({ type: "multiagent-hub-close-sidebar-page" }, "*");
        return;
      }
      if (window.history.length > 1) {
        window.history.back();
        return;
      }
      window.location.href = "/";
    };
    let _autoSaveTimer = null;
    const _doAutoSave = async () => {
      if (!settingsForm || settingsForm.dataset.saving === "1") return;
      settingsForm.dataset.saving = "1";
      const payload = new URLSearchParams();
      const formData = new FormData(settingsForm);
      for (const [key, value] of formData.entries()) {
        payload.append(key, String(value));
      }
      if (activeTextSizeInput) {
        payload.set("message_text_size", String(activeTextSizeInput.value || ""));
      }
      try {
        await fetch(settingsForm.action || "/settings", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8" },
          body: payload.toString(),
          cache: "no-store",
        });
      } catch (_) {}
      settingsForm.dataset.saving = "0";
    };
    if (settingsForm) {
      settingsForm.addEventListener("change", () => {
        clearTimeout(_autoSaveTimer);
        _autoSaveTimer = setTimeout(_doAutoSave, 350);
      });
    }
    const hubRestartForm = document.querySelector(".hub-restart-form");
    if (hubRestartForm) {
      hubRestartForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const btn = e.currentTarget.querySelector("button");
        if (btn.classList.contains("restarting")) return;
        btn.classList.add("restarting");
        btn.disabled = true;
        btn.textContent = "Restarting…";
        try { await fetch("/restart-hub", { method: "POST" }); } catch (_) {}
        const started = Date.now();
        const poll = async () => {
          try {
            const res = await fetch(`/sessions?ts=${Date.now()}`, { cache: "no-store" });
            if (res.ok) { window.location.replace(window.location.pathname); return; }
          } catch (_) {}
          if (Date.now() - started < 20000) { setTimeout(poll, 500); } else { window.location.reload(); }
        };
        setTimeout(poll, 700);
      });
    }

    const chatSoundToggles = document.querySelectorAll('input[name="chat_sound"]');
    if (chatSoundToggles.length > 0) {
      const previewAudio = new Audio('/notify-sound?name=mictest.ogg');
      previewAudio.preload = 'auto';
      const previewMeter = isMobileView ? document.getElementById('soundPreviewMeter') : document.getElementById('soundPreviewMeterD');
      const previewMeterBars = previewMeter ? Array.from(previewMeter.querySelectorAll('.audio-preview-meter-bar')) : [];
      let previewAudioCtx = null;
      let previewAnalyser = null;
      let previewSource = null;
      let previewMeterFrame = 0;
      let previewMeterData = null;
      const resetPreviewMeter = () => {
        if (previewMeter) previewMeter.classList.remove('is-playing');
        previewMeterBars.forEach((bar) => { bar.style.height = '2px'; });
      };
      const stopPreviewMeter = () => {
        if (previewMeterFrame) { cancelAnimationFrame(previewMeterFrame); previewMeterFrame = 0; }
        resetPreviewMeter();
      };
      const ensurePreviewMeterAudio = async () => {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx || previewAnalyser) return;
        previewAudioCtx = new AudioCtx();
        previewAnalyser = previewAudioCtx.createAnalyser();
        previewAnalyser.fftSize = 64;
        previewAnalyser.smoothingTimeConstant = 0.82;
        previewMeterData = new Uint8Array(previewAnalyser.frequencyBinCount);
        previewSource = previewAudioCtx.createMediaElementSource(previewAudio);
        previewSource.connect(previewAnalyser);
        previewAnalyser.connect(previewAudioCtx.destination);
      };
      const drawPreviewMeter = () => {
        if (!previewAnalyser || !previewMeterData || previewAudio.paused || previewAudio.ended) {
          stopPreviewMeter(); return;
        }
        previewAnalyser.getByteFrequencyData(previewMeterData);
        const groups = [previewMeterData.slice(1, 4), previewMeterData.slice(4, 10), previewMeterData.slice(10, 18)];
        if (previewMeter) previewMeter.classList.add('is-playing');
        previewMeterBars.forEach((bar, index) => {
          const group = groups[index] || [];
          const avg = group.length ? group.reduce((sum, value) => sum + value, 0) / group.length : 0;
          bar.style.height = `${Math.max(2, Math.min(8, Math.round((avg / 255) * 6) + 2))}px`;
        });
        previewMeterFrame = requestAnimationFrame(drawPreviewMeter);
      };
      const playSoundPreview = () => {
        try {
          previewAudio.pause();
          previewAudio.currentTime = 0;
          ensurePreviewMeterAudio().then(async () => {
            if (previewAudioCtx && previewAudioCtx.state === 'suspended') { try { await previewAudioCtx.resume(); } catch (_) {} }
            stopPreviewMeter();
            const result = previewAudio.play();
            if (result && typeof result.catch === 'function') { result.catch(() => { stopPreviewMeter(); }); }
            drawPreviewMeter();
          }).catch(() => { resetPreviewMeter(); });
        } catch (_) {}
      };
      previewAudio.addEventListener('ended', stopPreviewMeter);
      previewAudio.addEventListener('pause', () => { if (!previewAudio.ended) stopPreviewMeter(); });
      chatSoundToggles.forEach(chatSoundToggle => {
        chatSoundToggle.addEventListener('change', () => {
          if (chatSoundToggle.checked) playSoundPreview();
        });
      });
    }

    const chatAwakeToggles = document.querySelectorAll('input[name="chat_awake"]');
    if (chatAwakeToggles.length > 0) {
      const awakeAudio = new Audio('/notify-sound?name=awake.ogg');
      awakeAudio.preload = 'auto';
      const awakeMeter = isMobileView ? document.getElementById('awakePreviewMeter') : document.getElementById('awakePreviewMeterD');
      const awakeMeterBars = awakeMeter ? Array.from(awakeMeter.querySelectorAll('.audio-preview-meter-bar')) : [];
      let awakeAudioCtx = null;
      let awakeAnalyser = null;
      let awakeSource = null;
      let awakeMeterFrame = 0;
      let awakeMeterData = null;
      const resetAwakeMeter = () => {
        if (awakeMeter) awakeMeter.classList.remove('is-playing');
        awakeMeterBars.forEach((bar) => { bar.style.height = '2px'; });
      };
      const stopAwakeMeter = () => {
        if (awakeMeterFrame) { cancelAnimationFrame(awakeMeterFrame); awakeMeterFrame = 0; }
        resetAwakeMeter();
      };
      const ensureAwakeMeterAudio = async () => {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx || awakeAnalyser) return;
        awakeAudioCtx = new AudioCtx();
        awakeAnalyser = awakeAudioCtx.createAnalyser();
        awakeAnalyser.fftSize = 64;
        awakeAnalyser.smoothingTimeConstant = 0.82;
        awakeMeterData = new Uint8Array(awakeAnalyser.frequencyBinCount);
        awakeSource = awakeAudioCtx.createMediaElementSource(awakeAudio);
        awakeSource.connect(awakeAnalyser);
        awakeAnalyser.connect(awakeAudioCtx.destination);
      };
      const drawAwakeMeter = () => {
        if (!awakeAnalyser || !awakeMeterData || awakeAudio.paused || awakeAudio.ended) {
          stopAwakeMeter(); return;
        }
        awakeAnalyser.getByteFrequencyData(awakeMeterData);
        const groups = [awakeMeterData.slice(1, 4), awakeMeterData.slice(4, 10), awakeMeterData.slice(10, 18)];
        if (awakeMeter) awakeMeter.classList.add('is-playing');
        awakeMeterBars.forEach((bar, index) => {
          const group = groups[index] || [];
          const avg = group.length ? group.reduce((sum, value) => sum + value, 0) / group.length : 0;
          bar.style.height = `${Math.max(2, Math.min(8, Math.round((avg / 255) * 6) + 2))}px`;
        });
        awakeMeterFrame = requestAnimationFrame(drawAwakeMeter);
      };
      awakeAudio.addEventListener('ended', stopAwakeMeter);
      awakeAudio.addEventListener('pause', () => { if (!awakeAudio.ended) stopAwakeMeter(); });
      chatAwakeToggles.forEach(chatAwakeToggle => {
        chatAwakeToggle.addEventListener('change', () => {
          const anySoundOn = Array.from(document.querySelectorAll('input[name="chat_sound"]')).some(t => t.checked);
          if (chatAwakeToggle.checked && anySoundOn) {
            try {
              awakeAudio.pause(); awakeAudio.currentTime = 0;
              ensureAwakeMeterAudio().then(async () => {
                if (awakeAudioCtx && awakeAudioCtx.state === 'suspended') { try { await awakeAudioCtx.resume(); } catch (_) {} }
                stopAwakeMeter();
                const result = awakeAudio.play();
                if (result && typeof result.catch === 'function') { result.catch(() => { stopAwakeMeter(); }); }
                drawAwakeMeter();
              }).catch(() => { resetAwakeMeter(); });
            } catch (_) {}
          }
        });
      });
    }

    const installAppBtn = document.getElementById('installAppBtn');
    const installStatus = document.getElementById('installStatus');
    const installHelp = document.getElementById('installHelp');
    let deferredInstallPrompt = null;
    const isStandaloneApp = () => window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
    const isIOS = /iphone|ipad|ipod/i.test(window.navigator.userAgent || "");
    const isSafari = /^((?!chrome|android).)*safari/i.test(window.navigator.userAgent || "");
    const setInstallStatus = (_) => { if (installStatus) installStatus.textContent = ""; };
    const updateInstallUi = () => {
      if (!installAppBtn) return;
      if (installHelp) installHelp.hidden = true;
      if (isStandaloneApp()) {
        installAppBtn.disabled = true;
        installAppBtn.querySelector('.set-row-name').textContent = 'Installed';
        setInstallStatus(""); return;
      }
      installAppBtn.disabled = false;
      if (deferredInstallPrompt) {
        installAppBtn.querySelector('.set-row-name').textContent = 'Install This App';
        setInstallStatus(""); return;
      }
      if (isIOS && isSafari) {
        installAppBtn.querySelector('.set-row-name').textContent = 'Show iPhone Steps';
        setInstallStatus(""); return;
      }
      installAppBtn.querySelector('.set-row-name').textContent = 'Show Install Help';
      setInstallStatus("");
    };
    if (installAppBtn) {
      installAppBtn.addEventListener('click', async () => {
        if (deferredInstallPrompt) {
          try { deferredInstallPrompt.prompt(); await deferredInstallPrompt.userChoice; } catch (_) {}
          deferredInstallPrompt = null;
          updateInstallUi(); return;
        }
        if (installHelp) {
          installHelp.hidden = false;
          installHelp.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        } else if (installStatus) {
          setInstallStatus("");
        }
      });
    }
    window.addEventListener('beforeinstallprompt', (event) => {
      event.preventDefault();
      deferredInstallPrompt = event;
      updateInstallUi();
    });
    window.addEventListener('appinstalled', () => {
      deferredInstallPrompt = null;
      updateInstallUi();
    });
    updateInstallUi();
  __HUB_HEADER_JS__
