    let _fileImportInProgress = false;
    let _fileImportClearTimer = null;
    const scheduleComposerCloseFromKeyboardDismiss = () => {
      if (_fileImportInProgress) return;
      clearComposerBlurCloseTimer();
      composerBlurCloseTimer = setTimeout(() => {
        if (!isComposerOverlayOpen()) return;
        if (_fileImportInProgress) return;
        const active = document.activeElement;
        if (active === messageInput) return;
        if (composerForm && active && composerForm.contains(active)) return;
        closeComposerOverlay();
      }, 140);
    };
    messageInput?.addEventListener("focus", () => {
      clearComposerBlurCloseTimer();
    });
    messageInput?.addEventListener("blur", () => {
      scheduleComposerCloseFromKeyboardDismiss();
    });

    // Web Speech API setup
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const checkMicrophonePermission = (onDenied) => {
        if (!(navigator.permissions && navigator.permissions.query)) return;
        navigator.permissions.query({ name: "microphone" }).then((result) => {
          if (result.state === "denied") onDenied();
        }).catch(() => { });
      };

      if (micBtn) {
        const recognition = new SpeechRecognition();
        recognition.lang = "ja-JP";
        recognition.continuous = false;
        recognition.interimResults = true;
        let isListening = false;
        let finalTranscript = "";

        const toggleRecognition = () => {
          if (isListening) {
            recognition.stop();
            return;
          }
          finalTranscript = messageInput.value;
          checkMicrophonePermission(() => {
            setStatus("マイクがブロックされています。アドレスバー左のアイコン → サイトの設定 → マイクを「許可」に変更してください");
            setTimeout(() => setStatus(""), 8000);
          });
          try {
            recognition.start();
          } catch (err) {
            console.error("[mic] recognition.start() threw:", err);
            setStatus("音声認識の開始に失敗: " + err.message);
            setTimeout(() => setStatus(""), 5000);
          }
        };
        micBtn.addEventListener("click", toggleRecognition);
        micBtn.addEventListener("touchend", (e) => {
          e.preventDefault();
          e.stopPropagation();
          toggleRecognition();
        }, { passive: false });

        recognition.onstart = () => {
          isListening = true;
          micBtn.classList.add("listening");
        };
        recognition.onresult = (event) => {
          let interim = "";
          for (let i = event.resultIndex; i < event.results.length; i++) {
            if (event.results[i].isFinal) {
              finalTranscript += event.results[i][0].transcript;
            } else {
              interim += event.results[i][0].transcript;
            }
          }
          messageInput.value = finalTranscript + interim;
          updateSendBtnVisibility();
          messageInput.dispatchEvent(new Event("input"));
        };
        recognition.onend = () => {
          isListening = false;
          micBtn.classList.remove("listening");
          messageInput.value = finalTranscript;
          updateSendBtnVisibility();
          if (finalTranscript.trim()) {
            setTimeout(() => submitMessage(), 100);
          }
        };
        recognition.onerror = (e) => {
          console.error("[mic] recognition error:", e.error, e);
          isListening = false;
          micBtn.classList.remove("listening");
          if (e.error === "not-allowed") {
            setStatus("マイクのアクセスが拒否されています。設定 > プライバシー > マイクで許可してください。");
          } else if (e.error === "service-not-allowed") {
            setStatus("このモード（ホーム画面アプリ）では音声認識が使えません。Safariで開いてください。");
          } else if (e.error === "network") {
            setStatus("音声認識サービスに接続できません（ネットワークエラー）");
          } else if (e.error === "aborted") {
            setStatus("音声認識が中断されました");
          } else {
            setStatus("音声認識エラー: " + (e.error || "unknown"));
          }
          setTimeout(() => setStatus(""), 5000);
        };
      }

      if (cameraModeMicBtn) {
        const cameraRecognition = new SpeechRecognition();
        cameraRecognition.lang = "ja-JP";
        cameraRecognition.continuous = false;
        cameraRecognition.interimResults = true;
        let isListening = false;
        let suppressCommit = false;
        let finalTranscript = "";
        let audioVisualizerCtx = null;
        let audioVisualizerSource = null;
        let audioVisualizerStream = null;
        let audioVisualizerAnalyser = null;
        let audioVisualizerRafId = 0;
        let audioVisualizerLiveFrames = 0;

        const waveformEl = () => cameraModeHint?.querySelector(".camera-waveform");
        const waveformBars = () => Array.from(cameraModeHint?.querySelectorAll(".camera-waveform-bar") || []);
        const resetAudioVisualizerBars = () => {
          waveformEl()?.classList.remove("is-live");
          waveformBars().forEach((bar) => {
            bar.style.removeProperty("--camera-wave-scale");
            bar.style.removeProperty("--camera-wave-opacity");
          });
        };

        const ensureAudioVisualizerContext = async () => {
          const AudioContext = window.AudioContext || window.webkitAudioContext;
          if (!AudioContext) return null;
          if (!audioVisualizerCtx || audioVisualizerCtx.state === "closed") {
            audioVisualizerCtx = new AudioContext();
          }
          if (audioVisualizerCtx.state === "suspended") {
            await audioVisualizerCtx.resume();
          }
          return audioVisualizerCtx;
        };

        const stopAudioVisualizer = () => {
          if (audioVisualizerRafId) cancelAnimationFrame(audioVisualizerRafId);
          audioVisualizerRafId = 0;
          audioVisualizerLiveFrames = 0;
          if (audioVisualizerSource) {
            try { audioVisualizerSource.disconnect(); } catch (_) { }
            audioVisualizerSource = null;
          }
          if (audioVisualizerAnalyser) {
            try { audioVisualizerAnalyser.disconnect(); } catch (_) { }
          }
          if (audioVisualizerStream) {
            audioVisualizerStream.getTracks().forEach(t => t.stop());
            audioVisualizerStream = null;
          }
          audioVisualizerAnalyser = null;
          resetAudioVisualizerBars();
        };

        const startAudioVisualizer = async () => {
          try {
            if (audioVisualizerStream) stopAudioVisualizer();

            // Best-effort only. If a second mic consumer is not allowed on this
            // browser, keep the CSS fallback waveform running instead.
            audioVisualizerStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const ctx = await ensureAudioVisualizerContext();
            if (!ctx) return;

            const src = ctx.createMediaStreamSource(audioVisualizerStream);
            audioVisualizerSource = src;
            audioVisualizerAnalyser = ctx.createAnalyser();
            audioVisualizerAnalyser.fftSize = 32;
            audioVisualizerAnalyser.smoothingTimeConstant = 0.72;
            src.connect(audioVisualizerAnalyser);

            const dataArray = new Uint8Array(audioVisualizerAnalyser.frequencyBinCount);
            const bars = waveformBars();
            const wave = waveformEl();

            const renderWaveform = () => {
              if (!audioVisualizerAnalyser) return;
              audioVisualizerRafId = requestAnimationFrame(renderWaveform);
              audioVisualizerAnalyser.getByteFrequencyData(dataArray);

              let energy = 0;
              for (let i = 0; i < dataArray.length; i++) energy += dataArray[i];
              energy = energy / (dataArray.length * 255);
              if (energy > 0.018) {
                audioVisualizerLiveFrames = Math.min(audioVisualizerLiveFrames + 1, 4);
              } else {
                audioVisualizerLiveFrames = Math.max(audioVisualizerLiveFrames - 1, 0);
              }
              wave?.classList.toggle("is-live", audioVisualizerLiveFrames >= 2);
              if (audioVisualizerLiveFrames < 2) return;

              bars.forEach((bar, i) => {
                const val = dataArray[i % dataArray.length] / 255.0;
                const scale = 0.2 + (val * 1.5);
                const opacity = 0.3 + (val * 0.7);
                bar.style.setProperty("--camera-wave-scale", scale.toFixed(2));
                bar.style.setProperty("--camera-wave-opacity", opacity.toFixed(2));
              });
            };
            renderWaveform();
          } catch (err) {
            console.warn("[mic] could not start audio visualizer:", err);
            resetAudioVisualizerBars();
          }
        };

        const clearCameraMicUi = () => {
          isListening = false;
          cameraModeMicListening = false;
          cameraModeMicBtn.classList.remove("listening");
          stopAudioVisualizer();
          syncCameraModeBusyState();
          setCameraModeHint("");
        };
        cancelCameraModeMicRecognition = () => {
          suppressCommit = true;
          finalTranscript = "";
          clearCameraMicUi();
          if (!cameraModeBusy) setCameraModeHint("");
          if (!isListening) return;
          try {
            cameraRecognition.abort();
          } catch (_) {
            try { cameraRecognition.stop(); } catch (_) { }
          }
        };
        const toggleCameraRecognition = async () => {
          if (isListening) {
            suppressCommit = false;
            cameraRecognition.stop();
            return;
          }
          if (cameraModeBusy || !cameraMode || cameraMode.hidden) return;
          const target = syncCameraModeTarget();
          if (!target) {
            setCameraModeHint("No available agent target.", true);
            return;
          }
          finalTranscript = "";
          suppressCommit = false;
          checkMicrophonePermission(() => {
            setCameraModeHint("Microphone access is blocked.", true);
          });
          try {
            await ensureAudioVisualizerContext().catch(() => { });
            cameraRecognition.start();
          } catch (err) {
            setCameraModeHint("Voice input failed to start.", true);
          }
        };
        cameraModeMicBtn.addEventListener("click", () => {
          void toggleCameraRecognition();
        });
        cameraModeMicBtn.addEventListener("touchend", (e) => {
          e.preventDefault();
          e.stopPropagation();
          void toggleCameraRecognition();
        }, { passive: false });
        cameraRecognition.onstart = () => {
          isListening = true;
          cameraModeMicListening = true;
          cameraModeMicBtn.classList.add("listening");
          syncCameraModeBusyState();
          setCameraModeHint("Listening...", false, true);
          void startAudioVisualizer();
        };
        cameraRecognition.onresult = (event) => {
          let interim = "";
          for (let i = event.resultIndex; i < event.results.length; i++) {
            if (event.results[i].isFinal) {
              finalTranscript += event.results[i][0].transcript;
            } else {
              interim += event.results[i][0].transcript;
            }
          }
          const preview = `${finalTranscript}${interim}`.trim();
          setCameraModeHint(preview || "Listening...", false, true);
        };
        cameraRecognition.onend = () => {
          isListening = false;
          clearCameraMicUi();
          if (suppressCommit) {
            suppressCommit = false;
            finalTranscript = "";
            if (!cameraModeBusy) setCameraModeHint("");
            return;
          }
          const transcript = String(finalTranscript || "").trim();
          finalTranscript = "";
          if (!transcript) {
            if (!cameraModeBusy) setCameraModeHint("");
            return;
          }
          void (async () => {
            const target = syncCameraModeTarget();
            if (!target) {
              setCameraModeHint("No available agent target.", true);
              return;
            }
            try {
              setCameraModeBusy(true);
              await sendCameraModeText(transcript, target);
              await refresh({ forceScroll: true });
              setCameraModeBusy(false);
              setCameraModeHint("");
            } catch (err) {
              setCameraModeBusy(false, err?.message || "voice send failed", true);
            }
          })();
        };
        cameraRecognition.onerror = (e) => {
          console.error("[camera-mic] recognition error:", e.error, e);
          isListening = false;
          clearCameraMicUi();
          if (suppressCommit || e.error === "aborted") {
            suppressCommit = false;
            if (!cameraModeBusy) setCameraModeHint("");
            return;
          }
          if (e.error === "not-allowed") {
            setCameraModeHint("Microphone access denied.", true);
          } else if (e.error === "service-not-allowed") {
            setCameraModeHint("Voice input is unavailable here.", true);
          } else if (e.error === "network") {
            setCameraModeHint("Speech recognition network error.", true);
          } else if (e.error === "no-speech") {
            setCameraModeHint("No speech detected.", true);
          } else {
            setCameraModeHint("Voice input error.", true);
          }
          setTimeout(() => {
            if (!cameraModeMicListening && !cameraModeBusy) setCameraModeHint("");
          }, 3200);
        };
      }
    } else {
      if (micBtn) micBtn.classList.add("no-speech");
      if (cameraModeMicBtn) cameraModeMicBtn.classList.add("no-speech");
    }

    // Import / file attach
    const cameraBtn = document.getElementById("cameraBtn");
    const cameraInput = document.getElementById("cameraInput");
    const attachPreviewRow = document.getElementById("attachPreviewRow");
    const composerShellEl = document.querySelector(".composer-shell");
    if (cameraBtn && cameraInput && attachPreviewRow) {
      const attachmentBaseName = (value) => {
        const parts = String(value || "").split(/[\\/]/);
        return parts[parts.length - 1] || String(value || "");
      };
      const attachmentExt = (value) => {
        const base = attachmentBaseName(value);
        const dot = base.lastIndexOf(".");
        return dot > 0 ? base.slice(dot) : "";
      };
      const attachmentStem = (value) => {
        const base = attachmentBaseName(value);
        const dot = base.lastIndexOf(".");
        return dot > 0 ? base.slice(0, dot) : base;
      };
      const attachmentDisplayNameFromPath = (path, fallback = "") => {
        const base = attachmentBaseName(path);
        const ext = attachmentExt(base);
        const stem = ext ? base.slice(0, -ext.length) : base;
        const parts = stem.split("_");
        if (parts.length >= 3) {
          const label = parts.slice(2).join("_");
          if (label) return `${label}${ext}`;
        }
        return fallback || base;
      };
      const syncAttachmentCard = (card, attachment) => {
        if (!card || !attachment) return;
        card.dataset.path = attachment.path || "";
        card.setAttribute("aria-label", attachment.name ? `Rename attachment ${attachment.name}` : "Rename attachment");
        card.title = attachment.name ? `Rename ${attachment.name}` : "Rename attachment";
        const nameEl = card.querySelector(".attach-card-name");
        if (nameEl) {
          nameEl.textContent = attachment.name || attachmentDisplayNameFromPath(attachment.path, "Attachment");
        }
        const img = card.querySelector(".attach-card-thumb");
        if (img && attachment.name) img.alt = attachment.name;
      };
      const openAttachmentRenameModal = (attachment, card) => {
        if (!attachment || !pendingAttachments.includes(attachment)) return;
        let overlay = document.getElementById("attachRenameOverlay");
        if (overlay) overlay.remove();
        overlay = document.createElement("div");
        overlay.id = "attachRenameOverlay";
        overlay.className = "add-agent-overlay attach-rename-overlay";
        const currentName = attachment.name || attachmentDisplayNameFromPath(attachment.path, "attachment");
        const ext = attachmentExt(currentName) || attachmentExt(attachment.path);
        const initialLabel = (attachment.label || attachmentStem(currentName)).trim();
        const hint = ext ? `The ${escapeHtml(ext)} extension stays unchanged.` : "The file extension stays unchanged.";
        overlay.innerHTML = `<div class="add-agent-panel attach-rename-panel"><h3>Rename Attachment</h3><p class="attach-rename-copy">${escapeHtml(currentName)}</p><label class="attach-rename-label" for="attachRenameInput">Name</label><input id="attachRenameInput" class="attach-rename-input" type="text" placeholder="attachment name" maxlength="80" autocapitalize="off" autocorrect="off" spellcheck="false"><p class="attach-rename-hint">${hint}</p><div class="attach-rename-error" aria-live="polite"></div><div class="add-agent-actions"><button type="button" class="add-agent-cancel">Cancel</button><button type="button" class="add-agent-confirm">Rename</button></div></div>`;
        document.body.appendChild(overlay);
        requestAnimationFrame(() => overlay.classList.add("visible"));
        const input = overlay.querySelector("#attachRenameInput");
        input.value = initialLabel;
        const errorEl = overlay.querySelector(".attach-rename-error");
        const cancelBtn = overlay.querySelector(".add-agent-cancel");
        const confirmBtn = overlay.querySelector(".add-agent-confirm");
        const closeModal = ({ restoreFocus = true } = {}) => {
          overlay.classList.remove("visible");
          setTimeout(() => overlay.remove(), 420);
          if (restoreFocus) {
            try { card?.focus?.(); } catch (_) { }
          }
        };
        const syncConfirmState = () => {
          confirmBtn.disabled = !input.value.trim();
        };
        overlay.addEventListener("click", (e) => {
          if (e.target === overlay) closeModal();
        });
        cancelBtn.addEventListener("click", () => closeModal());
        input.addEventListener("input", () => {
          errorEl.textContent = "";
          syncConfirmState();
        });
        input.addEventListener("keydown", async (e) => {
          if (e.key === "Escape") {
            e.preventDefault();
            closeModal();
            return;
          }
          if (e.key === "Enter" && !confirmBtn.disabled) {
            e.preventDefault();
            confirmBtn.click();
          }
        });
        confirmBtn.addEventListener("click", async () => {
          const label = input.value.trim();
          if (!label) {
            syncConfirmState();
            return;
          }
          if (!pendingAttachments.includes(attachment)) {
            closeModal({ restoreFocus: false });
            return;
          }
          confirmBtn.disabled = true;
          cancelBtn.disabled = true;
          errorEl.textContent = "";
          try {
            const res = await fetch("/rename-upload", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ path: attachment.path, label }),
            });
            const data = await res.json();
            if (!res.ok || !data.ok || !data.path) {
              throw new Error(data.error || "rename failed");
            }
            const nextName = attachmentDisplayNameFromPath(data.path, `${label}${ext}`);
            attachment.path = data.path;
            attachment.name = nextName;
            attachment.label = attachmentStem(nextName);
            syncAttachmentCard(card, attachment);
            setStatus("");
            closeModal();
          } catch (err) {
            errorEl.textContent = err?.message || "rename failed";
            confirmBtn.disabled = false;
            cancelBtn.disabled = false;
          }
        });
        syncConfirmState();
        setTimeout(() => {
          try {
            input.focus();
            input.select();
          } catch (_) { }
        }, 40);
      };
      const addCard = (file, attachment) => {
        const card = document.createElement("div");
        card.className = "attach-card";
        card.tabIndex = 0;
        card.setAttribute("role", "button");
        if (file.type.startsWith("image/")) {
          const img = document.createElement("img");
          img.className = "attach-card-thumb";
          img.src = URL.createObjectURL(file);
          img.alt = file.name;
          card.appendChild(img);
        } else {
          const ext = document.createElement("div");
          ext.className = "attach-card-ext";
          ext.textContent = file.name.split(".").pop().slice(0, 5) || "FILE";
          card.appendChild(ext);
        }
        const nameEl = document.createElement("div");
        nameEl.className = "attach-card-name";
        nameEl.textContent = attachment.name || file.name;
        card.appendChild(nameEl);
        const rmBtn = document.createElement("button");
        rmBtn.type = "button";
        rmBtn.className = "attach-card-remove";
        rmBtn.setAttribute("aria-label", "Remove");
        rmBtn.textContent = "\u2715";
        rmBtn.addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation();
          pendingAttachments = pendingAttachments.filter((a) => a !== attachment);
          card.remove();
          if (!attachPreviewRow.children.length) attachPreviewRow.style.display = "none";
          if (attachment.path) {
            fetch("/delete-upload", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ path: attachment.path }),
            }).catch(() => {});
          }
        });
        card.appendChild(rmBtn);
        card.addEventListener("click", () => openAttachmentRenameModal(attachment, card));
        card.addEventListener("keydown", (e) => {
          if (e.key !== "Enter" && e.key !== " ") return;
          e.preventDefault();
          openAttachmentRenameModal(attachment, card);
        });
        syncAttachmentCard(card, attachment);
        attachPreviewRow.appendChild(card);
        attachPreviewRow.style.display = "flex";
      };
      const uploadAttachedFiles = async (fileList) => {
        const files = Array.from(fileList || []).filter((f) => f && typeof f.name === "string");
        if (!files.length) return false;
        /* iOS: 最初の await 前にフォーカス（非同期続きではキーボードが出にくい）。 */
        if (messageInput && isComposerOverlayOpen()) {
          focusComposerTextarea({ sync: true });
        }
        setStatus(files.length > 1 ? `uploading ${files.length} files...` : `uploading ${files[0].name}...`);
        try {
          await Promise.all(files.map(async (file) => {
            const res = await fetch("/upload", {
              method: "POST",
              headers: {
                "Content-Type": file.type || "application/octet-stream",
                "X-Filename": encodeURIComponent(file.name || "upload.bin"),
              },
              body: file,
            });
            const data = await res.json();
            if (!res.ok || !data.ok) throw new Error(data.error || "upload failed");
            const attachment = { path: data.path, name: file.name, label: "" };
            pendingAttachments.push(attachment);
            addCard(file, attachment);
          }));
          setStatus("");
          return true;
        } catch (err) {
          setStatus("upload failed: " + err.message, true);
          setTimeout(() => setStatus(""), 3000);
          return false;
        }
      };
      const dtHasFiles = (dt) => dt && [...dt.types].includes("Files");
      const isOnFileInputDrop = (t) => !!(t && t.closest && t.closest("input[type=file]"));
      const maybeOpenComposerForAttachDrag = () => {
        if (!isComposerOverlayOpen()) openComposerOverlay({ immediateFocus: false });
      };
      cameraBtn.addEventListener("click", () => {
        closePlusMenu();
        _fileImportInProgress = true;
        if (_fileImportClearTimer) clearTimeout(_fileImportClearTimer);
        _fileImportClearTimer = setTimeout(() => {
          _fileImportInProgress = false;
          _fileImportClearTimer = null;
        }, 20000);
        cameraInput.click();
      });
      cameraInput.addEventListener("change", async () => {
        _fileImportInProgress = false;
        if (_fileImportClearTimer) {
          clearTimeout(_fileImportClearTimer);
          _fileImportClearTimer = null;
        }
        const files = Array.from(cameraInput.files);
        cameraInput.value = "";
        await uploadAttachedFiles(files);
      });
      document.addEventListener("dragenter", (e) => {
        if (!dtHasFiles(e.dataTransfer) || isOnFileInputDrop(e.target)) return;
        maybeOpenComposerForAttachDrag();
        composerOverlay?.classList.add("composer-attach-drag");
      }, true);
      document.addEventListener("dragover", (e) => {
        if (!dtHasFiles(e.dataTransfer) || isOnFileInputDrop(e.target)) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "copy";
      }, true);
      document.addEventListener("dragleave", (e) => {
        if (!composerOverlay?.classList.contains("composer-attach-drag")) return;
        if (!dtHasFiles(e.dataTransfer)) return;
        const related = e.relatedTarget;
        if (!related || !document.documentElement.contains(related)) {
          composerOverlay.classList.remove("composer-attach-drag");
        }
      }, true);
      document.addEventListener("dragend", () => {
        composerOverlay?.classList.remove("composer-attach-drag");
      }, true);
      document.addEventListener("drop", async (e) => {
        if (!dtHasFiles(e.dataTransfer) || isOnFileInputDrop(e.target)) return;
        e.preventDefault();
        e.stopPropagation();
        composerOverlay?.classList.remove("composer-attach-drag");
        maybeOpenComposerForAttachDrag();
        await uploadAttachedFiles(e.dataTransfer.files);
      }, true);
    }

    const updateSendBtnVisibility = () => {
      if (sessionLaunchPending || !sessionActive) {
        if (sendBtn) sendBtn.classList.remove("visible");
        if (micBtn) micBtn.classList.remove("hidden");
        return;
      }
      const hasText = messageInput.value.trim().length > 0;
      if (sendBtn) sendBtn.classList.toggle("visible", hasText);
      if (micBtn) micBtn.classList.toggle("hidden", hasText);
    };
    messageInput.addEventListener("input", updateSendBtnVisibility);

