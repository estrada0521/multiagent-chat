    const renderTargetPicker = (targets) => {
      const root = document.getElementById("targetPicker");
      root.classList.toggle("target-picker-readonly", !canComposeInSession());
      const selectedSet = new Set(selectedTargets);
      const targetsSig = JSON.stringify(targets);
      const selectionSig = JSON.stringify([...selectedSet].sort());
      const renderSig = `${targetsSig}|${selectionSig}`;
      if (root.dataset.renderSig === renderSig) return;

      if (root.dataset.targetsSig !== targetsSig) {
        root.dataset.targetsSig = targetsSig;
        root.innerHTML = targets.map((target) => {
          return `<button type="button" class="target-chip" data-target="${target}" data-base-agent="${agentBaseName(target)}" title="${escapeHtml(target)}"><span class="agent-icon-slot agent-icon-slot--chip"><span class="target-icon" aria-hidden="true" style="--agent-icon-mask:url('${escapeHtml(agentIconSrc(target))}')"></span>${agentIconInstanceSubHtml(target)}</span></button>`;
        }).join("");
        root.querySelectorAll(".target-chip").forEach((node) => {
          node.addEventListener("mousedown", (e) => e.preventDefault());
          node.addEventListener("click", () => {
            if (!canComposeInSession()) return;  // archived session: chips show, selection is frozen
            const target = node.dataset.target;
            if (selectedTargets.includes(target)) {
              selectedTargets = selectedTargets.filter((item) => item !== target);
            } else {
              selectedTargets = [...selectedTargets, target];
            }
            saveTargetSelection(currentSessionName, selectedTargets);
            renderTargetPicker(availableTargets);
          });
        });
      }
      root.querySelectorAll(".target-chip").forEach((node) => {
        node.classList.toggle("active", selectedSet.has(node.dataset.target));
      });
      root.dataset.renderSig = renderSig;
    };
