    const loadOlderMessages = async () => {
      if (olderLoading || !latestPayloadData) return;
      const loadedCount = displayEntriesForData(latestPayloadData).length;
      if (!loadedCount) {
        olderHasMore = false;
        rerenderCurrentMessages();
        return;
      }
      olderLoading = true;
      const prevHeight = timeline.scrollHeight;
      const prevTop = timeline.scrollTop;
      try {
        const res = await fetchWithTimeout(messagesFetchUrl({ offset: loadedCount }));
        if (!res.ok) throw new Error("older messages unavailable");
        const data = await res.json();
        const olderBatch = Array.isArray(data?.entries) ? data.entries : [];
        olderHasMore = !!data?.has_older;
        if (olderBatch.length) {
          olderEntries = mergeEntriesById(olderBatch, olderEntries);
        }
      } catch (err) {
        setStatus(err?.message || String(err), true);
      } finally {
        olderLoading = false;
        render(latestPayloadData, { suppressEntryAnimation: true });
        if (!lastRenderPrepended) {
          const delta = timeline.scrollHeight - prevHeight;
          _programmaticScroll = true;
          timeline.scrollTop = prevTop + delta;
          _pollScrollLockTop = timeline.scrollTop;
          queueMicrotask(() => { _programmaticScroll = false; });
        }
        updateScrollBtn();
      }
    };
__CHAT_INCLUDE:../transcript-refresh.js__
__CHAT_INCLUDE:../shortcut-commands.js__
    const blurComposerOnMobile = (message) => {
      if (document.documentElement.dataset.mobile === "1") message.blur();
    };
    const applySessionActivation = (data) => {
      if (!data?.activated) return;
      sessionActive = true;
      if (Array.isArray(data.targets) && data.targets.length) {
        availableTargets = normalizedSessionTargets(data.targets);
        selectedTargets = data.targets.filter((t) => availableTargets.includes(t));
        saveTargetSelection(currentSessionName, selectedTargets);
        renderTargetPicker(availableTargets);
      }
    };
    const postShortcutCommand = async ({ command_id, arg = "", path = "/shortcut-command" }) => {
      if (sendLocked) {
        return false;
      }
      sendLocked = true;
      const target = selectedTargets.join(",");
      if (!target.trim()) {
        setStatus("select at least one target", true);
        sendLocked = false;
        return false;
      }
      setStatus(`running ${command_id}...`);
      try {
        const res = await fetch(path, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            command_id,
            arg,
            target,
            client: document.documentElement.dataset.mobile === "1" ? "mobile" : "desktop",
          }),
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          throw new Error(data.error || "shortcut failed");
        }
        applySessionActivation(data);
        setStatus(data.status_message || "done");
        void refresh();
        if (data.activated) {
          void refreshSessionState();
        }
        return true;
      } catch (error) {
        setStatus(error.message, true);
        return false;
      } finally {
        sendLocked = false;
      }
    };
    const submitMessage = async ({ closeOverlayOnStart = false, forcedText = null } = {}) => {
      if (sendLocked) {
        return false;
      }
      sendLocked = true;
      const message = document.getElementById("message");
      const rawInput = (forcedText != null ? forcedText : message.value).trim();
      const clearComposerDraft = () => {
        message.value = "";
        clearStoredComposerDraft();
        updateSendBtnVisibility();
        autoResizeTextarea();
      };
      if (rawInput.startsWith("/")) {
        let list;
        try {
          list = await loadShortcutCommandsOnce();
        } catch (err) {
          setStatus(err?.message || "shortcut commands unavailable", true);
          sendLocked = false;
          return false;
        }
        const parsed = parseSlashCommandInput(rawInput, list);
        if (parsed) {
          if (parsed.insert) {
            // Not a backend command: drop the token into the composer (like an
            // @-mention) and leave it for the user to send.
            message.value = parsed.insert + " ";
            updateSendBtnVisibility();
            autoResizeTextarea();
            focusMessageInputWithoutScroll(message.value.length);
            sendLocked = false;
            return false;
          }
          const arg = parsed.arg;
          if (closeOverlayOnStart && isComposerOverlayOpen()) {
            blurComposerOnMobile(message);
            // Read by the close-start Fit Height refit: the transcript is
            // about to change (refresh() below), so that refit should wait
            // for it instead of measuring the stale last message.
            document.documentElement.dataset.sendInFlight = "1";
            closeComposerOverlay();
          }
          try {
            const res = await fetch(parsed.path || "/shortcut-command", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                command_id: parsed.id,
                arg,
                target: selectedTargets.join(","),
                client: document.documentElement.dataset.mobile === "1" ? "mobile" : "desktop",
              }),
            });
            const data = await res.json();
            if (!res.ok || !data.ok) {
              throw new Error(data.error || "shortcut failed");
            }
            applySessionActivation(data);
            clearComposerDraft();
            blurComposerOnMobile(message);
            if (pendingAttachments.length) {
              pendingAttachments = [];
              const row = document.getElementById("attachPreviewRow");
              if (row) { row.innerHTML = ""; row.style.display = "none"; }
            }
            closeComposerOverlay();
            setStatus(data.status_message || "done");
            void refresh();
            if (data.activated) {
              void refreshSessionState();
            }
            return true;
          } catch (error) {
            setStatus(error.message, true);
            return false;
          } finally {
            sendLocked = false;
            delete document.documentElement.dataset.sendInFlight;
          }
        }
        // ショートカット未一致 → 通常メッセージとして送信
      }
      let target = selectedTargets.join(",");
      const isNote = !target;
      const attachSuffix =
        pendingAttachments.length
          ? pendingAttachments.map((a) => "\n[Attached: " + a.path + "]").join("")
          : "";
      const messageBody = rawInput + attachSuffix;
      if (!messageBody.trim()) {
        setStatus("message is required", true);
        sendLocked = false;
        return false;
      }
      if (closeOverlayOnStart && isComposerOverlayOpen()) {
        blurComposerOnMobile(message);
        // Read by the close-start Fit Height refit: the just-sent message
        // hasn't rendered yet (that happens after the /send round trip
        // below), so that refit should wait for it instead of measuring the
        // previous last message.
        document.documentElement.dataset.sendInFlight = "1";
        closeComposerOverlay();
      }
      setStatus(isNote ? "saving note..." : `sending to ${target}...`);
      try {
        const res = await fetch("/send", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target,
            message: messageBody,
            client: document.documentElement.dataset.mobile === "1" ? "mobile" : "desktop",
          }),
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          throw new Error(data.error || "send failed");
        }
        applySessionActivation(data);
        clearComposerDraft();
        blurComposerOnMobile(message);
        if (pendingAttachments.length) {
          pendingAttachments = [];
          const row = document.getElementById("attachPreviewRow");
          if (row) { row.innerHTML = ""; row.style.display = "none"; }
        }
        closeComposerOverlay();
        setStatus(isNote ? "note saved" : `sent to ${target}`);
        // Mark the target agents running *before* rendering the sent message so
        // render() draws the running indicator in the same pass -- otherwise it
        // arrives a session-state round-trip later and forces a second resize
        // that flashes the message off-screen in Fit Height mode.
        // markAgentOptimisticallyRunning holds it through racing session-state
        // updates until the server confirms.
        if (!isNote) {
          for (const t of selectedTargets) {
            if (agentBaseName(t) !== "user") markAgentOptimisticallyRunning(t);
          }
        }
        applyLocalEntry(data.entry);
        if (data.activated) {
          void refreshSessionState();
        }
        return true;
      } catch (error) {
        setStatus(error.message, true);
        return false;
      } finally {
        sendLocked = false;
        delete document.documentElement.dataset.sendInFlight;
      }
    };
    document.getElementById("composer").addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!canComposeInSession()) return;  // statusline already shows the read-only label
      const submitter = event.submitter;
      const closeOverlayOnStart = !!(submitter && submitter.classList && submitter.classList.contains("send-btn"));
      await submitMessage({ closeOverlayOnStart });
    });
