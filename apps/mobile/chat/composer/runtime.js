    const scheduleComposerCloseFromKeyboardDismiss = () => {
      clearComposerBlurCloseTimer();
      composerBlurCloseTimer = setTimeout(() => {
        if (!isComposerOverlayOpen()) return;
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

    } else {
      if (micBtn) micBtn.classList.add("no-speech");
    }

    const cameraBtn = document.getElementById("cameraBtn");
    const cameraInput = document.getElementById("cameraInput");
    const attachPreviewRow = document.getElementById("attachPreviewRow");
    const composerShellEl = document.querySelector(".composer-shell");
    if (cameraBtn && cameraInput && attachPreviewRow) {
      const addCard = (file, attachment) => {
        const card = document.createElement("div");
        card.className = "attach-card";
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
        attachPreviewRow.appendChild(card);
        attachPreviewRow.style.display = "flex";
      };
      const uploadAttachedFiles = async (fileList) => {
        const files = Array.from(fileList || []).filter((f) => f && typeof f.name === "string");
        if (!files.length) return false;
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
            const attachment = { path: data.path, name: file.name };
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
        closeComposerOverlay();
        cameraInput.click();
      });
      cameraInput.addEventListener("change", async () => {
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
      if (!sessionActive) {
        if (sendBtn) sendBtn.classList.remove("visible");
        if (micBtn) micBtn.classList.remove("hidden");
        return;
      }
      const hasText = messageInput.value.trim().length > 0;
      if (sendBtn) sendBtn.classList.toggle("visible", hasText);
      if (micBtn) micBtn.classList.toggle("hidden", hasText);
    };
    messageInput.addEventListener("input", updateSendBtnVisibility);
