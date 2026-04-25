    const HUB_EMBED = document.documentElement.dataset.hubEmbed === "1";
    const VIEW_VARIANT = document.documentElement.dataset.viewVariant || "";
    const isMobileView = VIEW_VARIANT === "mobile";

    // ── Bold mode reflected on Settings page ──
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

    // ── Apply chat text size to Settings page ──
    const textSizeInput = isMobileView
      ? document.querySelector('#settingsFormMobile [name="message_text_size"]')
      : document.querySelector('#settingsFormDesktop [name="message_text_size"]');
    if (textSizeInput) {
      const initial = Math.max(
        11,
        Math.min(18, parseInt(textSizeInput.dataset.initialSize || textSizeInput.value, 10) || 15)
      );
      textSizeInput.value = String(initial);
      const applyTextSize = () => {
        const sz = Math.max(11, Math.min(18, parseInt(textSizeInput.value, 10) || 15));
        document.documentElement.style.setProperty('--settings-text-size', sz + 'px');
        if (isMobileView) {
          const valDisplay = document.getElementById('textSizeValue');
          if (valDisplay) valDisplay.textContent = sz;
        }
      };
      applyTextSize();
      textSizeInput.addEventListener('input', applyTextSize);
      textSizeInput.addEventListener('change', applyTextSize);

      if (isMobileView) {
        const minusBtn = document.getElementById('textSizeMinus');
        const plusBtn = document.getElementById('textSizePlus');
        if (minusBtn && plusBtn) {
          const triggerAutoSave = () => {
            if (typeof _doAutoSave === 'function') {
              clearTimeout(_autoSaveTimer);
              _autoSaveTimer = setTimeout(_doAutoSave, 350);
            }
          };
          minusBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const cur = parseInt(textSizeInput.value, 10) || 15;
            const next = Math.max(11, cur - 1);
            if (cur !== next) {
              textSizeInput.value = next;
              applyTextSize();
              triggerAutoSave();
            }
          });
          plusBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const cur = parseInt(textSizeInput.value, 10) || 15;
            const next = Math.min(18, cur + 1);
            if (cur !== next) {
              textSizeInput.value = next;
              applyTextSize();
              triggerAutoSave();
            }
          });
        }
      }
    }

    // ── Form submit ──
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

    // ── Audio preview (sound toggle) ──
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

    // ── Audio preview (awake toggle) ──
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

    // ── App install ──
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
