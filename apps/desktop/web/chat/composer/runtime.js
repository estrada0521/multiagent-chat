    let _fileImportInProgress = false;
    let _fileImportClearTimer = null;

    const attachBtn = document.getElementById("attachBtn");
    const attachInput = document.getElementById("attachInput");
    const attachPreviewRow = document.getElementById("attachPreviewRow");
    const composerShellEl = document.querySelector(".composer-shell");
    if (attachBtn && attachInput && attachPreviewRow) {
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
            try { card?.focus?.(); } catch (_) {}
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
          } catch (_) {}
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
      window.addEventListener("message", async (event) => {
        if (event.source !== window.parent || !(event.data && event.data.type)) return;
        if (event.data.type === "multiagent-parent-attach-drag") {
          if (event.data.active) {
            maybeOpenComposerForAttachDrag();
            composerOverlay?.classList.add("composer-attach-drag");
          } else {
            composerOverlay?.classList.remove("composer-attach-drag");
          }
          return;
        }
        if (event.data.type !== "multiagent-parent-drop-files") return;
        const forwardedFiles = Array.isArray(event.data.files)
          ? event.data.files.filter((file) => file && typeof file.name === "string")
          : [];
        composerOverlay?.classList.remove("composer-attach-drag");
        if (!forwardedFiles.length) return;
        maybeOpenComposerForAttachDrag();
        await uploadAttachedFiles(forwardedFiles);
      });
      attachBtn.addEventListener("click", () => {
        closePlusMenu();
        _fileImportInProgress = true;
        if (_fileImportClearTimer) clearTimeout(_fileImportClearTimer);
        _fileImportClearTimer = setTimeout(() => {
          _fileImportInProgress = false;
          _fileImportClearTimer = null;
        }, 20000);
        attachInput.click();
      });
      attachInput.addEventListener("change", async () => {
        _fileImportInProgress = false;
        if (_fileImportClearTimer) {
          clearTimeout(_fileImportClearTimer);
          _fileImportClearTimer = null;
        }
        const files = Array.from(attachInput.files);
        attachInput.value = "";
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

    delete document.documentElement.dataset.mobile;

    messageInput.addEventListener("keydown", async (event) => {
      if (event.key !== "Enter" || event.shiftKey || composing) {
        return;
      }
      event.preventDefault();
      await submitMessage();
    });
    messageInput.addEventListener("compositionstart", () => {
      composing = true;
    });
    messageInput.addEventListener("compositionend", () => {
      composing = false;
      setTimeout(updateFileAutocomplete, 10);
    });
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
