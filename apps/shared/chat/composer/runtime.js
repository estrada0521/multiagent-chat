    const isMobileComposer = document.documentElement.dataset.mobile === "1";
    let composing = false;
    const messageInput = document.getElementById("message");
    const sendBtn = document.querySelector(".send-btn");
    const attachBtn = document.getElementById("attachBtn");
    attachBtn?.addEventListener("mousedown", (e) => {
      e.preventDefault();
      if (!isMobileComposer) attachBtn.classList.add("pressing");
    });
    if (!isMobileComposer) {
      const _clearPressing = () => attachBtn?.classList.remove("pressing");
      attachBtn?.addEventListener("mouseup", _clearPressing);
      attachBtn?.addEventListener("mouseleave", _clearPressing);
      attachBtn?.addEventListener("touchend", _clearPressing, { passive: true });
      attachBtn?.addEventListener("touchcancel", _clearPressing, { passive: true });
    }
    if (isMobileComposer) {
      let composerBlurCloseTimer = null;
      const clearComposerBlurCloseTimer = () => {
        if (composerBlurCloseTimer) {
          clearTimeout(composerBlurCloseTimer);
          composerBlurCloseTimer = null;
        }
      };
      messageInput?.addEventListener("focus", () => {
        clearComposerBlurCloseTimer();
      });
      messageInput?.addEventListener("blur", () => {
        clearComposerBlurCloseTimer();
        composerBlurCloseTimer = setTimeout(() => {
          if (!isComposerOverlayOpen()) return;
          const active = document.activeElement;
          if (active === messageInput) return;
          if (composerForm && active && composerForm.contains(active)) return;
          closeComposerOverlay();
        }, 140);
      });
    }

    const attachInput = document.getElementById("attachInput");
    const attachPreviewRow = document.getElementById("attachPreviewRow");
    const composerShellEl = document.querySelector(".composer-shell");
    if (attachBtn && attachInput && attachPreviewRow) {
      const addCard = (file, attachment) => {
        const card = document.createElement("button");
        card.type = "button";
        card.className = "attach-card";
        card.setAttribute("aria-label", `Remove ${file.name}`);
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
        card.addEventListener("click", () => {
          pendingAttachments = pendingAttachments.filter((a) => a !== attachment);
          card.remove();
          updateSendBtnVisibility();
          if (!attachPreviewRow.children.length) attachPreviewRow.style.display = "none";
          if (attachment.path) {
            fetch("/delete-upload", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ path: attachment.path }),
            }).catch(() => {});
          }
        });
        attachPreviewRow.appendChild(card);
        attachPreviewRow.style.display = "flex";
      };
__CHAT_INCLUDE:../upload-attached-files.js__
      const dtHasFiles = (dt) => dt && [...dt.types].includes("Files");
      const isOnFileInputDrop = (t) => !!(t && t.closest && t.closest("input[type=file]"));
      const maybeOpenComposerForAttachDrag = () => {
        if (!isComposerOverlayOpen()) openComposerOverlay({ immediateFocus: false });
      };
      let attachDragClearTimer = 0;
      const showComposerAttachDrag = () => {
        if (attachDragClearTimer) {
          clearTimeout(attachDragClearTimer);
          attachDragClearTimer = 0;
        }
        maybeOpenComposerForAttachDrag();
        composerOverlay?.classList.add("composer-attach-drag");
      };
      const hideComposerAttachDrag = ({ immediate = false } = {}) => {
        if (attachDragClearTimer) {
          clearTimeout(attachDragClearTimer);
          attachDragClearTimer = 0;
        }
        if (immediate) {
          composerOverlay?.classList.remove("composer-attach-drag");
          return;
        }
        attachDragClearTimer = setTimeout(() => {
          composerOverlay?.classList.remove("composer-attach-drag");
          attachDragClearTimer = 0;
        }, 120);
      };
      if (!isMobileComposer) {
        window.addEventListener("message", async (event) => {
          if (event.source !== window.parent || !(event.data && event.data.type)) return;
          if (event.data.type === "parent-attach-drag") {
            if (event.data.active) {
              showComposerAttachDrag();
            } else {
              hideComposerAttachDrag();
            }
            return;
          }
          if (event.data.type !== "parent-drop-files") return;
          const forwardedFiles = Array.isArray(event.data.files)
            ? event.data.files.filter((file) => file && typeof file.name === "string")
            : [];
          hideComposerAttachDrag({ immediate: true });
          if (!forwardedFiles.length) return;
          maybeOpenComposerForAttachDrag();
          await uploadAttachedFiles(forwardedFiles);
        });
        attachBtn.addEventListener("click", () => {
          attachInput.click();
        });
        attachInput.addEventListener("change", async () => {
          const files = Array.from(attachInput.files);
          attachInput.value = "";
          await uploadAttachedFiles(files);
        });
      } else {
        attachBtn.addEventListener("click", () => {
          closeComposerOverlay();
          attachInput.click();
        });
        attachInput.addEventListener("change", async () => {
          const files = Array.from(attachInput.files);
          attachInput.value = "";
          await uploadAttachedFiles(files);
        });
      }
      document.addEventListener("dragenter", (e) => {
        if (!dtHasFiles(e.dataTransfer) || isOnFileInputDrop(e.target)) return;
        showComposerAttachDrag();
      }, true);
      document.addEventListener("dragover", (e) => {
        if (!dtHasFiles(e.dataTransfer) || isOnFileInputDrop(e.target)) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "copy";
        showComposerAttachDrag();
      }, true);
      document.addEventListener("dragleave", (e) => {
        if (!composerOverlay?.classList.contains("composer-attach-drag")) return;
        if (!dtHasFiles(e.dataTransfer)) return;
        const related = e.relatedTarget;
        if (!related || !document.documentElement.contains(related)) {
          hideComposerAttachDrag();
        }
      }, true);
      document.addEventListener("dragend", () => {
        hideComposerAttachDrag({ immediate: true });
      }, true);
      document.addEventListener("drop", async (e) => {
        if (!dtHasFiles(e.dataTransfer) || isOnFileInputDrop(e.target)) return;
        e.preventDefault();
        e.stopPropagation();
        hideComposerAttachDrag({ immediate: true });
        maybeOpenComposerForAttachDrag();
        await uploadAttachedFiles(e.dataTransfer.files);
      }, true);
      messageInput.addEventListener("paste", async (e) => {
        if (!dtHasFiles(e.clipboardData)) return;
        e.preventDefault();
        maybeOpenComposerForAttachDrag();
        await uploadAttachedFiles(e.clipboardData.files);
      });
    }

    const updateSendBtnVisibility = () => {
      if (!sessionActive) {
        if (sendBtn) sendBtn.classList.remove("visible");
        return;
      }
      const hasContent = messageInput.value.trim().length > 0 || pendingAttachments.length > 0;
      if (sendBtn) sendBtn.classList.toggle("visible", hasContent);
    };
    messageInput.addEventListener("input", updateSendBtnVisibility);
    messageInput.addEventListener("input", saveComposerDraft);
    window.addEventListener("pagehide", saveComposerDraft);
    messageInput.addEventListener("compositionstart", () => {
      composing = true;
    });
    messageInput.addEventListener("compositionend", () => {
      composing = false;
      setTimeout(updateFileAutocomplete, 10);
    });
    if (!isMobileComposer) {
      messageInput.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" || event.shiftKey) {
          return;
        }
        if (composing || event.isComposing || event.keyCode === 229) {
          return;
        }
        event.preventDefault();
        document.getElementById("composer").requestSubmit();
      });
    }
    restoreComposerDraft();
    queueMicrotask(() => {
      if (typeof autoResizeTextarea === "function") autoResizeTextarea();
    });
