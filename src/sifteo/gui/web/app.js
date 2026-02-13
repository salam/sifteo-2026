/**
 * Sifteo Cube Manager -- Frontend application logic.
 *
 * Communicates with the Python bridge via pywebview.api.
 * Receives push events via window.onSifteoEvent().
 */

// ── State ────────────────────────────────────────────────────────

let state = {
    connected: false,
    dongle_plugged_in: false,
    is_root: false,
    cubes: [],
    games: [],
    installing: {},  // game_name -> {percent, done, ok, error}
    installed_apps: {},  // game_name -> [cube_ids]
    consoleOpen: false,
    settingsOpen: false,
};

let _trafficTimer = null;

function signalTraffic() {
    document.querySelectorAll(".cube-item .dot-online").forEach(d => d.classList.add("traffic"));
    clearTimeout(_trafficTimer);
    _trafficTimer = setTimeout(() => {
        document.querySelectorAll(".dot.traffic").forEach(d => d.classList.remove("traffic"));
    }, 800);
}

// ── DOM helpers ──────────────────────────────────────────────────

function el(tag, attrs, ...children) {
    const e = document.createElement(tag);
    if (attrs) {
        for (const [k, v] of Object.entries(attrs)) {
            if (k === "className") e.className = v;
            else if (k === "style" && typeof v === "object") Object.assign(e.style, v);
            else if (k.startsWith("on")) e.addEventListener(k.slice(2).toLowerCase(), v);
            else e.setAttribute(k, v);
        }
    }
    for (const c of children) {
        if (typeof c === "string") e.appendChild(document.createTextNode(c));
        else if (c) e.appendChild(c);
    }
    return e;
}

function clearChildren(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
}

// ── Console log ─────────────────────────────────────────────────

const MAX_LOG_ENTRIES = 500;

function consoleLog(level, msg) {
    const log = document.getElementById("console-log");
    if (!log) return;

    const now = new Date();
    const ts = now.toLocaleTimeString("en-GB", { hour12: false }) +
        "." + String(now.getMilliseconds()).padStart(3, "0");

    const entry = el("div", { className: "log-entry" },
        el("span", { className: "log-time" }, ts),
        el("span", { className: "log-level " + level }, level),
        el("span", { className: "log-msg" }, msg)
    );
    log.appendChild(entry);

    // Trim old entries
    while (log.children.length > MAX_LOG_ENTRIES) {
        log.removeChild(log.firstChild);
    }

    // Auto-scroll
    log.scrollTop = log.scrollHeight;
}

function toggleConsole() {
    const panel = document.getElementById("console-panel");
    const btn = document.getElementById("btn-console-toggle");
    state.consoleOpen = !state.consoleOpen;

    if (state.consoleOpen) {
        panel.classList.remove("collapsed");
        btn.textContent = "Hide";
        document.body.classList.add("console-open");
    } else {
        panel.classList.add("collapsed");
        btn.textContent = "Show";
        document.body.classList.remove("console-open");
    }
}

function clearConsole() {
    const log = document.getElementById("console-log");
    if (log) clearChildren(log);
}

// ── Settings ────────────────────────────────────────────────────

// Speed slider: logarithmic scale from 0.025 (default) down to 0.000001.
// Slider 0 = default (25 ms), 100 = very fast (1 µs).
// Maps linearly across exponents: 10^(-1.6) to 10^(-6)
// At slider=0: 0.025  (25 ms)
// At slider=33: ~0.001  (1 ms)
// At slider=66: ~0.00001  (10 µs)
// At slider=100: 0.000001  (1 µs)

function sliderToGap(val) {
    if (val === 0) return 0.025;
    // Logarithmic: exponent from -1.6 (0.025) to -6 (0.000001)
    const exp = -1.6 - (val / 100) * 4.4;
    return Math.pow(10, exp);
}

function gapToSlider(gap) {
    if (gap >= 0.025) return 0;
    const exp = Math.log10(gap);
    const val = (exp + 1.6) / -4.4 * 100;
    return Math.max(0, Math.min(100, Math.round(val)));
}

function formatGap(gap) {
    if (gap >= 0.025) return "Default (25 ms)";
    if (gap >= 0.001) return (gap * 1000).toFixed(1) + " ms";
    if (gap >= 0.000001) return (gap * 1000000).toFixed(1) + " \u00b5s";
    return gap.toExponential(1) + " s";
}

function toggleSettings() {
    state.settingsOpen = !state.settingsOpen;
    const panel = document.getElementById("settings-panel");
    const btn = document.getElementById("btn-settings");
    panel.style.display = state.settingsOpen ? "" : "none";
    btn.classList.toggle("active", state.settingsOpen);
}

function initSettings() {
    const speedSlider = document.getElementById("speed-slider");
    const speedValue = document.getElementById("speed-value");
    const retriesSlider = document.getElementById("retries-slider");
    const retriesValue = document.getElementById("retries-value");

    speedSlider.addEventListener("input", function() {
        const gap = sliderToGap(Number(this.value));
        speedValue.textContent = formatGap(gap);
    });

    speedSlider.addEventListener("change", async function() {
        const gap = sliderToGap(Number(this.value));
        consoleLog("info", "Setting write gap: " + formatGap(gap) + " (" + gap.toExponential(2) + " s)");
        await pywebview.api.set_write_speed(gap);
    });

    retriesSlider.addEventListener("input", function() {
        retriesValue.textContent = this.value;
    });

    retriesSlider.addEventListener("change", async function() {
        const retries = Number(this.value);
        consoleLog("info", "Setting write retries: " + retries);
        await pywebview.api.set_write_retries(retries);
    });
}

async function loadSettings() {
    try {
        const settings = await pywebview.api.get_settings();
        const speedSlider = document.getElementById("speed-slider");
        const speedValue = document.getElementById("speed-value");
        const retriesSlider = document.getElementById("retries-slider");
        const retriesValue = document.getElementById("retries-value");

        speedSlider.value = gapToSlider(settings.write_min_gap);
        speedValue.textContent = formatGap(settings.write_min_gap);
        retriesSlider.value = settings.write_max_retries;
        retriesValue.textContent = String(settings.write_max_retries);
    } catch {
        // Bridge may not be ready yet
    }
}

// ── Init ─────────────────────────────────────────────────────────

window.addEventListener("pywebviewready", async () => {
    initSettings();

    consoleLog("info", "Bridge ready, fetching status...");
    const status = await pywebview.api.get_status();
    updateStatus(status);
    consoleLog("info", "Dongle: " + (status.dongle_plugged_in ? "detected" : "not found") +
        ", Root: " + (status.is_root ? "yes" : "no") +
        ", Connected: " + (status.connected ? "yes" : "no"));

    const games = await pywebview.api.get_games();
    state.games = games;
    consoleLog("info", "Loaded " + games.length + " game(s) from catalog");

    await loadSettings();

    if (status.connected) {
        showDashboard();
    } else {
        showLanding();
    }
});

// ── Event handler (called from Python via evaluate_js) ───────────

window.onSifteoEvent = function(event) {
    const { type, data } = event;

    if (type === "status_update") {
        updateStatus(data);
        if (data.connected && !state.connected) {
            state.connected = true;
            consoleLog("ok", "Connected with " + (data.cubes || []).length + " cube(s)");
            showDashboard();
        } else if (!data.connected && state.connected) {
            state.connected = false;
            consoleLog("warn", "Disconnected");
            showLanding();
        } else if (!data.connected) {
            showLanding();
        }
        if (data.connected) {
            renderCubeBar(data.cubes);
            updateCubeSelect(data.cubes);
        }
    }

    if (type === "install_progress") {
        const key = data.game;
        state.installing[key] = state.installing[key] || {};
        state.installing[key].percent = data.percent;
        state.installing[key].cube_id = data.cube_id;
        signalTraffic();
        renderCardAction(key);
    }

    if (type === "install_done") {
        const key = data.game;
        state.installing[key] = {
            done: true,
            ok: data.ok,
            error: data.error,
            percent: 100,
        };
        renderCardAction(key);

        if (data.ok) {
            consoleLog("ok", "Installed " + key + " on cube " + data.cube_id);
            // Update installed_apps optimistically
            if (!state.installed_apps[key]) state.installed_apps[key] = [];
            if (!state.installed_apps[key].includes(data.cube_id)) {
                state.installed_apps[key].push(data.cube_id);
            }
        } else {
            consoleLog("error", "Failed to install " + key + " on cube " + data.cube_id + ": " + (data.error || "unknown error"));
        }

        // Reset card after 4 seconds
        setTimeout(() => {
            delete state.installing[key];
            renderCardAction(key);
        }, 4000);
    }

    if (type === "log") {
        consoleLog(data.level || "info", data.message);
    }
};

// ── Status update ────────────────────────────────────────────────

function updateStatus(s) {
    state.dongle_plugged_in = s.dongle_plugged_in;
    state.is_root = s.is_root;
    state.connected = s.connected;
    state.cubes = s.cubes || [];

    const dot = document.getElementById("status-dot");
    const label = document.getElementById("status-label");
    const countEl = document.getElementById("cube-count");

    if (s.connected) {
        dot.className = "dot dot-online";
        label.textContent = "Connected";
        countEl.textContent = s.cubes.length + " cube" + (s.cubes.length !== 1 ? "s" : "");
    } else if (s.dongle_plugged_in) {
        dot.className = "dot dot-dongle";
        label.textContent = "Dongle found";
        countEl.textContent = "";
    } else {
        dot.className = "dot dot-offline";
        label.textContent = "Offline";
        countEl.textContent = "";
    }
}

// ── Landing screen ───────────────────────────────────────────────

function showLanding() {
    document.getElementById("landing").style.display = "";
    document.getElementById("dashboard").style.display = "none";

    const msg = document.getElementById("landing-msg");
    const btn = document.getElementById("btn-connect");
    const hint = document.getElementById("root-hint");
    const icon = document.getElementById("dongle-icon");
    const errEl = document.getElementById("connect-error");
    errEl.style.display = "none";

    if (!state.dongle_plugged_in) {
        msg.textContent = "Plug in your Sifteo dongle";
        btn.style.display = "none";
        hint.style.display = "none";
        icon.classList.remove("found");
    } else if (!state.is_root) {
        msg.textContent = "Dongle detected!";
        btn.style.display = "none";
        hint.style.display = "";
        icon.classList.add("found");
    } else {
        msg.textContent = "Dongle detected!";
        btn.style.display = "";
        btn.disabled = false;
        btn.textContent = "Connect";
        hint.style.display = "none";
        icon.classList.add("found");
        btn.onclick = doConnect;
    }
}

async function doConnect() {
    const btn = document.getElementById("btn-connect");
    const errEl = document.getElementById("connect-error");
    btn.disabled = true;
    btn.textContent = "Connecting...";
    errEl.style.display = "none";
    consoleLog("info", "Connecting to dongle...");

    const result = await pywebview.api.connect();

    if (result.ok) {
        state.connected = true;
        state.cubes = result.cubes || [];
        consoleLog("ok", "Connected, " + state.cubes.length + " cube(s) discovered");
        showDashboard();
        loadSettings();
    } else {
        btn.disabled = false;
        btn.textContent = "Connect";
        errEl.textContent = result.error || "Connection failed.";
        errEl.style.display = "";
        consoleLog("error", "Connect failed: " + (result.error || "unknown error"));
    }
}

async function doDisconnect() {
    consoleLog("info", "Disconnecting...");
    await pywebview.api.disconnect();
    state.connected = false;
    state.cubes = [];
    consoleLog("info", "Disconnected");
    showLanding();
}

// ── Dashboard ────────────────────────────────────────────────────

function showDashboard() {
    document.getElementById("landing").style.display = "none";
    document.getElementById("dashboard").style.display = "";

    renderGameGrid();
    renderCubeBar(state.cubes);
    updateCubeSelect(state.cubes);
    scanInstalledApps();
}

function renderGameGrid() {
    const grid = document.getElementById("game-grid");
    clearChildren(grid);

    for (const game of state.games) {
        const initials = gameInitials(game.display_name);

        const icon = el("div", { className: "game-icon", style: { background: game.color } }, initials);
        const name = el("div", { className: "game-name" }, game.display_name);
        const cat = el("div", { className: "game-category" }, game.category);
        const action = el("div", { className: "game-action", id: "action-" + game.name });

        const installBtn = el("button", {
            className: "btn-install",
            onClick: () => installGame(game.name),
        }, "Install");
        action.appendChild(installBtn);

        const infoBtn = el("button", {
            className: "btn-info",
            onClick: (e) => toggleGameInfo(game.name, e),
        }, "i");

        const card = el("div", { className: "game-card", "data-game": game.name },
            infoBtn, icon, name, cat, action);

        grid.appendChild(card);
    }
}

function renderCardAction(gameName) {
    const container = document.getElementById("action-" + gameName);
    if (!container) return;

    clearChildren(container);
    const info = state.installing[gameName];

    if (!info) {
        // Default: install button
        container.appendChild(
            el("button", {
                className: "btn-install",
                onClick: () => installGame(gameName),
            }, "Install")
        );
        return;
    }

    if (info.done) {
        const msg = info.ok ? "Installed" : (info.error || "Failed");
        const cls = "install-done " + (info.ok ? "success" : "error");
        container.appendChild(el("div", { className: cls }, msg));
        return;
    }

    // Progress bar
    const pct = info.percent || 0;
    const bar = el("div", { className: "progress-bar", style: { width: pct + "%" } });
    const label = el("div", { className: "progress-label" }, pct + "%");
    const badge = info.cube_id != null
        ? el("div", { className: "progress-cube-badge" }, "Cube " + info.cube_id)
        : null;
    const wrap = el("div", { className: "progress-wrap" }, bar, label, badge);
    container.appendChild(wrap);
}

async function installGame(name) {
    if (state.installing[name]) return;

    state.installing[name] = { percent: 0 };
    renderCardAction(name);

    // Determine target cube(s) from dropdown
    const sel = document.getElementById("cube-select");
    let cubeIds = null;
    if (sel.value !== "all") {
        cubeIds = [parseInt(sel.value)];
    }

    const target = cubeIds ? "cube " + cubeIds.join(", ") : "all cubes";
    consoleLog("info", "Installing " + name + " on " + target + "...");

    await pywebview.api.install_game(name, cubeIds);
}

// ── Cube bar / select ────────────────────────────────────────────

function renderCubeBar(cubes) {
    const list = document.getElementById("cube-list");
    if (!list) return;

    clearChildren(list);

    for (const c of cubes) {
        const dot = el("span", { className: "dot " + (c.online ? "dot-online" : "dot-offline") });
        const label = el("span", {}, "Cube " + c.id);
        const fw = el("span", { className: "cube-fw" }, "FW " + c.firmware_version);
        const item = el("div", {
            className: "cube-item clickable",
            onClick: (e) => toggleCubePopup(c, e),
        }, dot, label, fw);

        if (c.battery_low) {
            item.appendChild(el("span", { style: { color: "var(--error)" } }, "Low battery"));
        }

        list.appendChild(item);
    }
}

// ── Cube info popup ─────────────────────────────────────────────

let _openCubePopup = null;
let _cubePopupInterval = null;
let _cubePopupId = null;

function closeCubePopup() {
    if (_openCubePopup) {
        _openCubePopup.remove();
        _openCubePopup = null;
    }
    if (_cubePopupInterval) {
        clearInterval(_cubePopupInterval);
        _cubePopupInterval = null;
    }
    _cubePopupId = null;
}

function toggleCubePopup(cube, event) {
    event.stopPropagation();

    const wasOpen = _cubePopupId === cube.id;
    closeCubePopup();
    if (wasOpen) return;

    _cubePopupId = cube.id;

    const popup = el("div", {
        className: "cube-popup",
        "data-cube-id": String(cube.id),
        onClick: (e) => e.stopPropagation(),
    });

    // Position above the clicked item
    const rect = event.currentTarget.getBoundingClientRect();
    popup.style.left = rect.left + "px";
    popup.style.bottom = (window.innerHeight - rect.top + 8) + "px";

    document.body.appendChild(popup);
    _openCubePopup = popup;

    // Initial render + start live refresh
    refreshCubePopup();
    _cubePopupInterval = setInterval(refreshCubePopup, 500);
}

function refreshCubePopup() {
    if (!_openCubePopup || _cubePopupId == null) return;

    const cube = state.cubes.find(c => c.id === _cubePopupId);
    if (!cube) return;

    const popup = _openCubePopup;
    clearChildren(popup);

    // Title
    popup.appendChild(el("div", { className: "cube-popup-title" }, "Cube " + cube.id));

    // Static info rows
    if (cube.device_id) {
        popup.appendChild(cubeInfoRow("Device ID", cube.device_id));
    }
    popup.appendChild(cubeInfoRow("Firmware", cube.firmware_version || "unknown"));
    popup.appendChild(cubeInfoRow("Battery", cube.battery_low ? "Low" : "OK",
        cube.battery_low ? "var(--error)" : "var(--success)"));

    // Live rows
    let statusText = cube.online ? "Online" : "Offline";
    if (cube.docked) {
        statusText = "Docked" + (cube.dock_location != null ? " (slot " + cube.dock_location + ")" : "");
    }
    popup.appendChild(cubeInfoRow("Status", statusText,
        cube.docked ? "#f0c040" : (cube.online ? "var(--success)" : "var(--text-dim)")));

    if (cube.button_pressed) {
        popup.appendChild(cubeInfoRow("Button", "Pressed", "var(--success)"));
    }

    if (cube.tilt) {
        popup.appendChild(cubeInfoRow("Tilt", cube.tilt.join(", ")));
    }

    // Neighbors
    const sideNames = ["Top", "Left", "Bottom", "Right"];
    const neighborParts = [];
    if (cube.neighbors) {
        cube.neighbors.forEach((n, i) => {
            if (n) neighborParts.push(sideNames[i] + ": Cube " + n.cube);
        });
    }
    if (neighborParts.length > 0) {
        popup.appendChild(cubeInfoRow("Neighbors", neighborParts.join(", "), "#e080d0"));
    }

    // Last event
    if (cube.last_event) {
        const ev = cube.last_event;
        const ago = Math.round((Date.now() / 1000) - ev.time);
        const agoText = ago < 2 ? "just now" : ago + "s ago";
        const detail = ev.detail ? ev.type + " " + ev.detail : ev.type;
        popup.appendChild(cubeInfoRow("Last event", detail + " (" + agoText + ")", evTypeColor(ev.type)));
    }

    if (cube.last_seen) {
        const ago = Math.round((Date.now() / 1000) - cube.last_seen);
        popup.appendChild(cubeInfoRow("Last seen", ago < 5 ? "just now" : ago + "s ago"));
    }

    // Apps section
    const apps = [];
    for (const [gameName, cubeIds] of Object.entries(state.installed_apps)) {
        if (cubeIds.includes(cube.id)) {
            const game = state.games.find(g => g.name === gameName);
            apps.push(game ? game.display_name : gameName);
        }
    }
    popup.appendChild(el("div", { className: "cube-popup-section" }, "Installed Apps"));
    if (apps.length > 0) {
        popup.appendChild(el("div", { className: "cube-popup-apps" },
            ...apps.map(name => el("span", { className: "cube-popup-app-tag" }, name))));
    } else {
        popup.appendChild(el("div", { className: "cube-popup-none" }, "No apps found"));
    }

    // Adjust horizontal position if off-screen
    const popupRect = popup.getBoundingClientRect();
    if (popupRect.right > window.innerWidth - 8) {
        popup.style.left = (window.innerWidth - popupRect.width - 8) + "px";
    }
}

function evTypeColor(type) {
    switch (type) {
        case "tilt": return "var(--accent)";
        case "click": return "var(--success)";
        case "shake": return "#f0c040";
        case "neighbor": return "#e080d0";
        case "dock": return "#f0c040";
        case "battery": return "var(--error)";
        default: return null;
    }
}

function cubeInfoRow(label, value, color) {
    const valAttrs = { className: "cube-popup-value" };
    if (color) valAttrs.style = { color: color };
    return el("div", { className: "cube-popup-row" },
        el("span", { className: "cube-popup-label" }, label),
        el("span", valAttrs, value)
    );
}

// Close cube popup on outside click
document.addEventListener("click", () => closeCubePopup());

function updateCubeSelect(cubes) {
    const sel = document.getElementById("cube-select");
    if (!sel) return;

    const prev = sel.value;
    clearChildren(sel);

    const allOpt = el("option", { value: "all" }, "All cubes");
    sel.appendChild(allOpt);

    for (const c of cubes) {
        const opt = el("option", { value: String(c.id) }, "Cube " + c.id);
        sel.appendChild(opt);
    }

    // Restore previous selection if still valid
    if ([...sel.options].some(o => o.value === prev)) {
        sel.value = prev;
    }
}

// ── Installed apps scan ──────────────────────────────────────────

async function scanInstalledApps() {
    try {
        consoleLog("info", "Scanning cubes for installed apps...");
        const installed = await pywebview.api.scan_installed_apps();
        state.installed_apps = installed || {};
    } catch {
        consoleLog("warn", "Failed to scan installed apps");
    }
}

// ── Game info overlay ───────────────────────────────────────────

let _openInfoGame = null;

function toggleGameInfo(gameName, event) {
    event.stopPropagation();

    // Close existing overlay
    const existing = document.querySelector(".game-info-overlay");
    if (existing) {
        existing.remove();
        if (_openInfoGame === gameName) {
            _openInfoGame = null;
            return;
        }
    }
    _openInfoGame = gameName;

    const game = state.games.find(g => g.name === gameName);
    if (!game) return;

    const cubes = state.installed_apps[gameName] || [];

    const desc = el("div", { className: "info-desc" }, game.description || "No description.");

    const sizeRow = el("div", { className: "info-row" },
        el("span", { className: "info-label" }, "Size"),
        el("span", { className: "info-value" }, game.size_kb + " KB")
    );

    const cubeValue = cubes.length > 0
        ? cubes.map(c => "Cube " + c).join(", ")
        : "Not installed";
    const cubeRow = el("div", { className: "info-row" },
        el("span", { className: "info-label" }, "Installed"),
        el("span", { className: "info-value " + (cubes.length > 0 ? "installed" : "") }, cubeValue)
    );

    const overlay = el("div", {
        className: "game-info-overlay",
        onClick: (e) => e.stopPropagation(),
    }, desc, sizeRow, cubeRow);

    const card = event.target.closest(".game-card");
    card.appendChild(overlay);
}

// Close info overlay on outside click
document.addEventListener("click", () => {
    const existing = document.querySelector(".game-info-overlay");
    if (existing) {
        existing.remove();
        _openInfoGame = null;
    }
});

// ── Helpers ──────────────────────────────────────────────────────

function gameInitials(name) {
    const words = name.split(/\s+/);
    if (words.length >= 2) {
        return (words[0][0] + words[1][0]).toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
}

// ── Global actions (called from HTML onclick) ────────────────────

async function copySudoCmd() {
    const cmd = document.getElementById("sudo-cmd").textContent;
    try {
        await navigator.clipboard.writeText(cmd);
    } catch {
        // Fallback: select the text
        const range = document.createRange();
        range.selectNodeContents(document.getElementById("sudo-cmd"));
        window.getSelection().removeAllRanges();
        window.getSelection().addRange(range);
    }
}

async function relaunchAsRoot() {
    await pywebview.api.relaunch_as_root();
}
