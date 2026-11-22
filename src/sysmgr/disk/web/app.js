/**
 * DaisyDisk-style Interactive Disk Space Visualizer
 * Powered by D3.js v7 and Starlette REST/SSE Backend
 */

(function () {
  "use strict";

  // Application State
  const state = {
    currentTree: null,
    rootNode: null,
    focusedNode: null,
    activeScanPath: "",
    eventSource: null,
    selectedContextItem: null,
    colorScale: null,
  };

  // DaisyDisk Vibrant Color Palette
  const DAISY_PALETTE = [
    "#29b6f6", // Vivid Sky Blue
    "#ab47bc", // Magenta / Purple
    "#26a69a", // Teal / Turquoise
    "#ffa726", // Amber / Warm Gold
    "#ec407a", // Neon Pink
    "#42a5f5", // Electric Blue
    "#7e57c2", // Deep Lilac
    "#66bb6a", // Mint Green
    "#ff7043", // Coral Orange
    "#8d6e63", // Sand
    "#26c6da", // Cyan
    "#ef5350", // Crimson
  ];

  // DOM Elements
  const elements = {
    drivesView: document.getElementById("drives-view"),
    visualizerView: document.getElementById("visualizer-view"),
    drivesList: document.getElementById("drives-list"),
    customPathForm: document.getElementById("custom-path-form"),
    customPathInput: document.getElementById("custom-path-input"),
    btnRescan: document.getElementById("btn-rescan"),
    btnChangeSource: document.getElementById("btn-change-source"),
    breadcrumbContainer: document.getElementById("breadcrumb-container"),
    breadcrumb: document.getElementById("breadcrumb"),
    sunburstContainer: document.getElementById("sunburst-container"),
    sunburstSvg: document.getElementById("sunburst-svg"),
    sunburstCenter: document.getElementById("sunburst-center"),
    centerName: document.getElementById("center-name"),
    centerSize: document.getElementById("center-size"),
    centerMeta: document.getElementById("center-meta"),
    topList: document.getElementById("top-list"),
    topListCount: document.getElementById("top-list-count"),
    scanOverlay: document.getElementById("scan-overlay"),
    scanCurrentPath: document.getElementById("scan-current-path"),
    scanProgressBar: document.getElementById("scan-progress-bar"),
    scanFilesScanned: document.getElementById("scan-files-scanned"),
    scanBytesScanned: document.getElementById("scan-bytes-scanned"),
    scanElapsed: document.getElementById("scan-elapsed"),
    btnCancelScan: document.getElementById("btn-cancel-scan"),
    contextMenu: document.getElementById("context-menu"),
    contextMenuPath: document.getElementById("context-menu-path"),
    propertiesModal: document.getElementById("properties-modal"),
    propTitle: document.getElementById("prop-title"),
    propBody: document.getElementById("prop-body"),
    btnCloseProperties: document.getElementById("btn-close-properties"),
    btnPropertiesOk: document.getElementById("btn-properties-ok"),
    toastContainer: document.getElementById("toast-container"),
  };

  // HTML Sanitization Utility for XSS Prevention
  function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Human-Readable Byte Formatter
  function formatBytes(bytes, decimals = 1) {
    if (!bytes || bytes <= 0) return "0 B";
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ["B", "KB", "MB", "GB", "TB", "PB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    const val = parseFloat((bytes / Math.pow(k, i)).toFixed(dm));
    return `${val} ${sizes[i]}`;
  }

  function formatNumber(num) {
    return (num || 0).toLocaleString();
  }

  // Toast Notifications
  function showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    elements.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(10px)";
      setTimeout(() => toast.remove(), 300);
    }, 3200);
  }

  // API Call Helpers
  async function fetchDrives() {
    try {
      const res = await fetch("/api/drives");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const drives = await res.json();
      renderDrives(drives);
    } catch (err) {
      elements.drivesList.innerHTML = `<div class="loading-spinner">Failed to load drives: ${escapeHtml(err.message)}</div>`;
    }
  }

  function renderDrives(drives) {
    if (!drives || drives.length === 0) {
      elements.drivesList.innerHTML = `<div class="loading-spinner">No system drives found.</div>`;
      return;
    }

    elements.drivesList.innerHTML = "";
    drives.forEach((drive) => {
      const card = document.createElement("div");
      card.className = "drive-card";
      const pct = drive.percent_used.toFixed(1);

      // Color progress based on usage
      let barColor = "var(--accent-blue)";
      if (pct > 90) barColor = "var(--accent-red)";
      else if (pct > 75) barColor = "var(--accent-amber)";

      const safeMount = escapeHtml(drive.mountpoint);
      const safeLabel = escapeHtml(drive.label || drive.fstype);

      card.innerHTML = `
        <div class="drive-header">
          <span class="drive-mount">${safeMount}</span>
          <span class="drive-label" title="${safeLabel}">${safeLabel}</span>
        </div>
        <div class="drive-capacity-track">
          <div class="drive-capacity-fill" style="width: ${pct}%; background: ${barColor};"></div>
        </div>
        <div class="drive-stats">
          <span>${pct}% used</span>
          <span>${formatBytes(drive.free_bytes)} free of ${formatBytes(drive.total_bytes)}</span>
        </div>
      `;

      card.addEventListener("click", () => {
        startScan(drive.mountpoint);
      });

      elements.drivesList.appendChild(card);
    });
  }

  // Scanning Traversal & SSE
  async function startScan(targetPath) {
    if (!targetPath || !targetPath.trim()) {
      showToast("Please enter a valid directory path", "error");
      return;
    }

    state.activeScanPath = targetPath;
    showScanOverlay(targetPath);

    try {
      const res = await fetch("/api/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: targetPath }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || `HTTP ${res.status}`);
      }

      connectProgressSSE();
    } catch (err) {
      hideScanOverlay();
      showToast(`Scan failed: ${err.message}`, "error");
    }
  }

  function connectProgressSSE() {
    if (state.eventSource) {
      state.eventSource.close();
    }

    state.eventSource = new EventSource("/api/scan/progress");

    state.eventSource.onmessage = (event) => {
      try {
        const progress = JSON.parse(event.data);
        updateScanProgress(progress);

        if (progress.status === "completed") {
          // Close event source immediately to prevent auto-reconnect loops
          state.eventSource.close();
          state.eventSource = null;
          onScanComplete();
        } else if (progress.status === "failed") {
          state.eventSource.close();
          state.eventSource = null;
          hideScanOverlay();
          showToast(`Scan error: ${progress.error_message || "Unknown error"}`, "error");
        }
      } catch (e) {
        console.error("Error parsing progress SSE:", e);
      }
    };

    state.eventSource.onerror = () => {
      if (state.eventSource) {
        state.eventSource.close();
        state.eventSource = null;
        hideScanOverlay();
        showToast("Connection to scan progress stream lost", "error");
      }
    };
  }

  function updateScanProgress(progress) {
    if (!progress) return;
    elements.scanCurrentPath.textContent = progress.current_path || state.activeScanPath;
    elements.scanFilesScanned.textContent = `${formatNumber(progress.files_scanned)} files`;
    elements.scanBytesScanned.textContent = formatBytes(progress.total_bytes);
    elements.scanElapsed.textContent = `${(progress.elapsed_seconds || 0).toFixed(1)}s`;

    // Estimate progress bar pulse
    elements.scanProgressBar.style.width = progress.status === "completed" ? "100%" : "65%";
  }

  async function cancelScan() {
    if (state.eventSource) {
      state.eventSource.close();
      state.eventSource = null;
    }
    try {
      await fetch("/api/scan/cancel", { method: "POST" });
    } catch (_) {}
    hideScanOverlay();
    showToast("Scan cancelled", "info");
  }

  async function onScanComplete() {
    hideScanOverlay();
    try {
      const res = await fetch("/api/scan/tree");
      if (!res.ok) throw new Error(`Failed to load scan tree (HTTP ${res.status})`);
      const tree = await res.json();
      if (!tree) throw new Error("Empty scan result");

      state.currentTree = tree;
      switchToVisualizer();
      initSunburst(tree);
      showToast("Scan completed successfully", "success");
    } catch (err) {
      showToast(`Failed to render visualizer: ${err.message}`, "error");
    }
  }

  function showScanOverlay(path) {
    elements.scanCurrentPath.textContent = path;
    elements.scanProgressBar.style.width = "5%";
    elements.scanFilesScanned.textContent = "0 files";
    elements.scanBytesScanned.textContent = "0 B";
    elements.scanElapsed.textContent = "0.0s";
    elements.scanOverlay.classList.add("active");
  }

  function hideScanOverlay() {
    elements.scanOverlay.classList.remove("active");
  }

  function switchToVisualizer() {
    elements.drivesView.classList.remove("active");
    elements.visualizerView.classList.add("active");
    elements.btnRescan.style.display = "inline-flex";
    elements.btnChangeSource.style.display = "inline-flex";
    elements.breadcrumbContainer.style.display = "flex";
  }

  function switchToDrives() {
    elements.visualizerView.classList.remove("active");
    elements.drivesView.classList.add("active");
    elements.btnRescan.style.display = "none";
    elements.btnChangeSource.style.display = "none";
    elements.breadcrumbContainer.style.display = "none";
    fetchDrives();
  }

  // Interactive Sunburst Layout (D3.js v7)
  function initSunburst(rootData) {
    elements.sunburstSvg.innerHTML = "";

    const containerRect = elements.sunburstContainer.getBoundingClientRect();
    const size = Math.min(containerRect.width, containerRect.height, 750) || 600;
    const radius = size / 2;

    const svg = d3
      .select("#sunburst-svg")
      .attr("viewBox", `-${radius} -${radius} ${size} ${size}`)
      .attr("width", size)
      .attr("height", size);

    // Group for all radial arcs
    const g = svg.append("g");

    // Partition hierarchy
    const partition = (data) => {
      const root = d3
        .hierarchy(data)
        .sum((d) => (d.children && d.children.length > 0 ? 0 : d.size_bytes || 0))
        .sort((a, b) => (b.value || 0) - (a.value || 0));

      return d3.partition().size([2 * Math.PI, root.height + 1])(root);
    };

    const root = partition(rootData);
    root.each((d) => (d.current = d));

    state.rootNode = root;
    state.focusedNode = root;

    // Vibrant DaisyDisk Palette assignment
    const colorScale = d3.scaleOrdinal(DAISY_PALETTE);
    state.colorScale = (d) => {
      if (d.depth === 0) return "rgba(255, 255, 255, 0.08)";
      if (d.data.name === "Other files") return "#546e7a";
      // Derive color from root branch ancestor
      let ancestor = d;
      while (ancestor.depth > 1) {
        ancestor = ancestor.parent;
      }
      const baseColor = d3.hsl(colorScale(ancestor.data.name || ancestor.data.path));
      // Modulate lightness slightly with depth
      baseColor.l = Math.max(0.3, Math.min(0.75, baseColor.l + (d.depth - 1) * 0.07));
      return baseColor.toString();
    };

    // Arc Generator
    const arc = d3
      .arc()
      .startAngle((d) => d.x0)
      .endAngle((d) => d.x1)
      .padAngle((d) => Math.min((d.x1 - d.x0) / 2, 0.005))
      .padRadius(radius / 2)
      .innerRadius((d) => (d.y0 * radius) / (root.height + 1))
      .outerRadius((d) => Math.max((d.y0 * radius) / (root.height + 1), (d.y1 * radius) / (root.height + 1) - 1));

    // Render Arcs
    const path = g
      .append("g")
      .selectAll("path")
      .data(root.descendants().slice(1)) // omit center root circle (rendered via HTML badge)
      .join("path")
      .attr("class", "sunburst-arc")
      .attr("fill", (d) => state.colorScale(d))
      .attr("fill-opacity", (d) => (isArcVisible(d.current) ? 1 : 0))
      .attr("pointer-events", (d) => (isArcVisible(d.current) ? "auto" : "none"))
      .attr("d", (d) => arc(d.current));

    // Arc Hover & Tooltip Events
    path
      .on("mouseenter", function (event, d) {
        highlightItem(d);
        updateCenterBadge(d.data.name, d.value, d.data.path);
      })
      .on("mouseleave", function () {
        resetHighlight();
        resetCenterBadge();
      })
      .on("click", function (event, p) {
        event.stopPropagation();
        if (p.children && p.children.length > 0) {
          zoomToNode(p);
        } else {
          showItemContextMenu(event, p.data);
        }
      })
      .on("contextmenu", function (event, d) {
        event.preventDefault();
        showItemContextMenu(event, d.data);
      });

    // Zoom & Drilldown Handler
    function zoomToNode(targetNode) {
      state.focusedNode = targetNode;

      root.each((d) => {
        d.target = {
          x0: Math.max(0, Math.min(1, (d.x0 - targetNode.x0) / (targetNode.x1 - targetNode.x0))) * 2 * Math.PI,
          x1: Math.max(0, Math.min(1, (d.x1 - targetNode.x0) / (targetNode.x1 - targetNode.x0))) * 2 * Math.PI,
          y0: Math.max(0, d.y0 - targetNode.y0),
          y1: Math.max(0, d.y1 - targetNode.y0),
        };
      });

      const t = g.transition().duration(750);

      path
        .transition(t)
        .tween("data", (d) => {
          const i = d3.interpolate(d.current || d, d.target);
          return (t) => (d.current = i(t));
        })
        .filter(function (d) {
          return +this.getAttribute("fill-opacity") || isArcVisible(d.target);
        })
        .attr("fill-opacity", (d) => (isArcVisible(d.target) ? 1 : 0))
        .attr("pointer-events", (d) => (isArcVisible(d.target) ? "auto" : "none"))
        .attrTween("d", (d) => () => arc(d.current));

      renderBreadcrumb();
      renderTopList();
      resetCenterBadge();
    }

    function isArcVisible(d) {
      return d.y1 <= radius && d.y0 >= 0 && d.x1 > d.x0;
    }

    // Attach zoom to state for external caller
    state.zoomTo = zoomToNode;

    // Initial Badge and Sidebar Display
    resetCenterBadge();
    renderBreadcrumb();
    renderTopList();
  }

  // Center Badge Updaters
  function updateCenterBadge(name, sizeBytes, subtitle) {
    elements.centerName.textContent = name || "Selected";
    elements.centerSize.textContent = formatBytes(sizeBytes);
    elements.centerMeta.textContent = subtitle ? subtitle.slice(-28) : "Click slice to drill down";
  }

  function resetCenterBadge() {
    if (!state.focusedNode) return;
    const node = state.focusedNode;
    elements.centerName.textContent = node.data.name || "Root";
    elements.centerSize.textContent = formatBytes(node.data.size_bytes || node.value);
    elements.centerMeta.textContent = node.parent ? "Click center to go up" : "Directory Root";
  }

  // Center Circle Click -> Drill Up
  elements.sunburstCenter.addEventListener("click", () => {
    if (state.focusedNode && state.focusedNode.parent && state.zoomTo) {
      state.zoomTo(state.focusedNode.parent);
    }
  });

  // Breadcrumb Navigation
  function renderBreadcrumb() {
    if (!state.focusedNode) return;
    elements.breadcrumb.innerHTML = "";

    // Ancestor chain from root to current focused
    const chain = state.focusedNode.ancestors().reverse();

    chain.forEach((node, idx) => {
      if (idx > 0) {
        const sep = document.createElement("span");
        sep.className = "breadcrumb-separator";
        sep.textContent = "›";
        elements.breadcrumb.appendChild(sep);
      }

      const pill = document.createElement("button");
      pill.className = `breadcrumb-item ${node === state.focusedNode ? "active" : ""}`;
      pill.textContent = node.data.name || node.data.path;
      pill.title = node.data.path;

      pill.addEventListener("click", () => {
        if (state.zoomTo && node !== state.focusedNode) {
          state.zoomTo(node);
        }
      });

      elements.breadcrumb.appendChild(pill);
    });

    // Auto-scroll breadcrumbs to right end
    elements.breadcrumbContainer.scrollLeft = elements.breadcrumbContainer.scrollWidth;
  }

  // Top List Ranked Sidebar
  function renderTopList() {
    if (!state.focusedNode) return;
    const curr = state.focusedNode;
    elements.topList.innerHTML = "";

    const items = curr.children ? [...curr.children] : [];
    items.sort((a, b) => (b.data.size_bytes || b.value || 0) - (a.data.size_bytes || a.value || 0));

    elements.topListCount.textContent = `${items.length} items`;

    if (items.length === 0) {
      elements.topList.innerHTML = `<div class="loading-spinner">No subdirectories or files.</div>`;
      return;
    }

    const totalCurrentSize = curr.data.size_bytes || curr.value || 1;

    items.forEach((child) => {
      const row = document.createElement("div");
      row.className = "top-list-row";
      row.dataset.path = child.data.path;

      const bulletColor = state.colorScale ? state.colorScale(child) : "var(--accent-blue)";
      const itemBytes = child.data.size_bytes || child.value || 0;
      const pct = Math.round((itemBytes / totalCurrentSize) * 100);
      const isDir = child.data.is_dir || (child.children && child.children.length > 0);

      const safeName = escapeHtml(child.data.name);
      const safePath = escapeHtml(child.data.path);

      row.innerHTML = `
        <span class="item-bullet" style="background: ${bulletColor};"></span>
        <span class="item-icon">${isDir ? "📁" : "📄"}</span>
        <div class="item-info">
          <div class="item-name" title="${safePath}">${safeName}</div>
          <div class="item-subtext">${pct}% of current</div>
        </div>
        <span class="item-size">${formatBytes(itemBytes)}</span>
        <button class="item-actions-btn" title="Actions">⋮</button>
      `;

      // Hover linking to sunburst arc
      row.addEventListener("mouseenter", () => {
        highlightItem(child);
        updateCenterBadge(child.data.name, itemBytes, child.data.path);
      });

      row.addEventListener("mouseleave", () => {
        resetHighlight();
        resetCenterBadge();
      });

      // Click row
      row.addEventListener("click", (e) => {
        if (e.target.closest(".item-actions-btn")) {
          e.stopPropagation();
          showItemContextMenu(e, child.data);
          return;
        }
        if (isDir && state.zoomTo) {
          state.zoomTo(child);
        } else {
          showItemContextMenu(e, child.data);
        }
      });

      // Right click context menu
      row.addEventListener("contextmenu", (e) => {
        e.preventDefault();
        showItemContextMenu(e, child.data);
      });

      elements.topList.appendChild(row);
    });
  }

  // Bidirectional Highlighting
  function highlightItem(targetNode) {
    // Dim other arcs
    d3.selectAll(".sunburst-arc").classed("dimmed", true).classed("highlighted", false);

    // Highlight target arc and its ancestors/descendants
    d3.selectAll(".sunburst-arc")
      .filter((d) => d && d.data.path === targetNode.data.path)
      .classed("dimmed", false)
      .classed("highlighted", true);

    // Highlight Top List row
    document.querySelectorAll(".top-list-row").forEach((row) => {
      if (row.dataset.path === targetNode.data.path) {
        row.classList.add("highlighted");
        row.scrollIntoView({ block: "nearest", behavior: "smooth" });
      } else {
        row.classList.remove("highlighted");
      }
    });
  }

  function resetHighlight() {
    d3.selectAll(".sunburst-arc").classed("dimmed", false).classed("highlighted", false);
    document.querySelectorAll(".top-list-row").forEach((row) => {
      row.classList.remove("highlighted");
    });
  }

  // Context Menu & File Actions
  function showItemContextMenu(event, itemData) {
    state.selectedContextItem = itemData;
    elements.contextMenuPath.textContent = itemData.path;

    const x = Math.min(event.clientX, window.innerWidth - 240);
    const y = Math.min(event.clientY, window.innerHeight - 280);

    elements.contextMenu.style.left = `${x}px`;
    elements.contextMenu.style.top = `${y}px`;
    elements.contextMenu.style.display = "block";
  }

  function hideContextMenu() {
    elements.contextMenu.style.display = "none";
  }

  document.addEventListener("click", (e) => {
    if (!e.target.closest("#context-menu")) {
      hideContextMenu();
    }
  });

  // Keyboard accessibility: dismiss context menu on Escape key
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      hideContextMenu();
    }
  });

  // Action Menu Handler
  elements.contextMenu.addEventListener("click", async (e) => {
    const li = e.target.closest("li[data-action]");
    if (!li || !state.selectedContextItem) return;

    const action = li.dataset.action;
    const targetPath = state.selectedContextItem.path;
    hideContextMenu();

    if (action === "copy_path") {
      try {
        await navigator.clipboard.writeText(targetPath);
        showToast("Path copied to clipboard", "success");
      } catch (_) {
        showToast(`Path: ${targetPath}`, "info");
      }
      return;
    }

    if (action === "recycle") {
      if (!confirm(`Are you sure you want to move this to the Recycle Bin?\n\n${targetPath}`)) {
        return;
      }
    }

    await executeAction(action, targetPath);
  });

  async function executeAction(action, targetPath) {
    try {
      const res = await fetch("/api/actions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: action, path: targetPath }),
      });

      const result = await res.json();
      if (!res.ok || !result.success) {
        throw new Error(result.message || `Action '${action}' failed`);
      }

      if (action === "properties") {
        showPropertiesModal(result.details || { path: targetPath });
      } else {
        showToast(result.message || `Action ${action} succeeded`, "success");
      }

      if (action === "recycle" && state.activeScanPath) {
        // Rescan after file removal
        startScan(state.activeScanPath);
      }
    } catch (err) {
      showToast(`Action error: ${err.message}`, "error");
    }
  }

  // Properties Modal
  function showPropertiesModal(details) {
    const safeTitle = escapeHtml(details.name || "File Details");
    const safePath = escapeHtml(details.path || "");

    elements.propTitle.textContent = `Properties: ${safeTitle}`;
    elements.propBody.innerHTML = `
      <div class="prop-row">
        <span class="prop-label">Path:</span>
        <span class="prop-value" title="${safePath}">${safePath}</span>
      </div>
      <div class="prop-row">
        <span class="prop-label">Type:</span>
        <span class="prop-value">${details.is_dir ? "Directory" : "File"}</span>
      </div>
      <div class="prop-row">
        <span class="prop-label">Size:</span>
        <span class="prop-value">${formatBytes(details.size_bytes)} (${formatNumber(details.size_bytes)} bytes)</span>
      </div>
      ${details.created_time ? `
      <div class="prop-row">
        <span class="prop-label">Created:</span>
        <span class="prop-value">${escapeHtml(new Date(details.created_time * 1000).toLocaleString())}</span>
      </div>` : ""}
      ${details.modified_time ? `
      <div class="prop-row">
        <span class="prop-label">Modified:</span>
        <span class="prop-value">${escapeHtml(new Date(details.modified_time * 1000).toLocaleString())}</span>
      </div>` : ""}
    `;
    elements.propertiesModal.showModal();
  }

  elements.btnCloseProperties.addEventListener("click", () => elements.propertiesModal.close());
  elements.btnPropertiesOk.addEventListener("click", () => elements.propertiesModal.close());

  // Top Buttons & Forms
  elements.customPathForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const path = elements.customPathInput.value.trim();
    if (path) {
      startScan(path);
    }
  });

  elements.btnRescan.addEventListener("click", () => {
    if (state.activeScanPath) {
      startScan(state.activeScanPath);
    }
  });

  elements.btnChangeSource.addEventListener("click", () => {
    switchToDrives();
  });

  elements.btnCancelScan.addEventListener("click", () => {
    cancelScan();
  });

  // Window Resize: re-center / re-render sunburst
  window.addEventListener("resize", () => {
    if (state.currentTree && elements.visualizerView.classList.contains("active")) {
      initSunburst(state.currentTree);
    }
  });

  // Initialization
  fetchDrives();
})();
