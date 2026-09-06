      const uploadAttachedFiles = async (fileList) => {
        // Archived / read-only session: the attach button is disabled, but a
        // drop or paste would otherwise still reach here.
        if (!canComposeInSession()) return false;
        const files = Array.from(fileList || []).filter((f) => f && typeof f.name === "string");
        if (!files.length) return false;
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
            updateSendBtnVisibility();
          }));
          return true;
        } catch (err) {
          setStatus("upload failed: " + err.message, true);
          setTimeout(() => setStatus(""), STATUS_TOAST_MS);
          return false;
        }
      };
