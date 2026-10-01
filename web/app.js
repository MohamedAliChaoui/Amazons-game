/**
 * AMAZONS AI - Web Application Controller
 * Handles UI interactions, board rendering, Web Worker Pyodide orchestration,
 * sound effects via Web Audio API, and game lifecycle.
 */

// =====================================================================
// SVG Assets
// =====================================================================
const SVG_QUEEN_W = `
<svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="grad-w-body" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="60%" stop-color="#f8fafc"/>
      <stop offset="100%" stop-color="#e2e8f0"/>
    </linearGradient>
    <linearGradient id="grad-w-base" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#e2e8f0"/>
      <stop offset="50%" stop-color="#ffffff"/>
      <stop offset="100%" stop-color="#cbd5e1"/>
    </linearGradient>
    <filter id="shadow-w" x="-20%" y="-10%" width="140%" height="130%">
      <feDropShadow dx="0" dy="3" stdDeviation="3" flood-color="#000000" flood-opacity="0.3"/>
    </filter>
  </defs>
  <g filter="url(#shadow-w)">
    <!-- Base pedestal -->
    <path d="M16 82 Q50 88 84 82 L80 72 Q50 77 20 72 Z" fill="url(#grad-w-base)" stroke="#1e293b" stroke-width="2.5" stroke-linejoin="round"/>
    <ellipse cx="50" cy="74" rx="30" ry="3.5" fill="#f8fafc" stroke="#475569" stroke-width="1.5"/>
    <!-- Crown Spikes and Body -->
    <path d="M20 72 L13 36 L33 54 L50 20 L67 54 L87 36 L80 72 Z" fill="url(#grad-w-body)" stroke="#1e293b" stroke-width="2.5" stroke-linejoin="round"/>
    <!-- Crown Detail Lines -->
    <path d="M33 54 Q50 64 67 54" stroke="#64748b" stroke-width="1.8" fill="none"/>
    <line x1="50" y1="20" x2="50" y2="65" stroke="#94a3b8" stroke-width="1.8" stroke-dasharray="2 2"/>
    <!-- Pearls on Points -->
    <circle cx="13" cy="35" r="4.5" fill="#ffffff" stroke="#1e293b" stroke-width="2"/>
    <circle cx="33" cy="53" r="3.5" fill="#ffffff" stroke="#1e293b" stroke-width="2"/>
    <circle cx="50" cy="18" r="5.5" fill="#ffffff" stroke="#1e293b" stroke-width="2"/>
    <circle cx="67" cy="53" r="3.5" fill="#ffffff" stroke="#1e293b" stroke-width="2"/>
    <circle cx="87" cy="35" r="4.5" fill="#ffffff" stroke="#1e293b" stroke-width="2"/>
    <!-- Cross on Top -->
    <line x1="50" y1="8" x2="50" y2="15" stroke="#1e293b" stroke-width="2.5" stroke-linecap="round"/>
    <line x1="47" y1="11" x2="53" y2="11" stroke="#1e293b" stroke-width="2.5" stroke-linecap="round"/>
  </g>
</svg>`;

const SVG_QUEEN_B = `
<svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="grad-b-body" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#334155"/>
      <stop offset="35%" stop-color="#1e293b"/>
      <stop offset="100%" stop-color="#090d16"/>
    </linearGradient>
    <linearGradient id="grad-b-base" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#0f172a"/>
      <stop offset="50%" stop-color="#334155"/>
      <stop offset="100%" stop-color="#0f172a"/>
    </linearGradient>
    <filter id="shadow-b" x="-20%" y="-10%" width="140%" height="130%">
      <feDropShadow dx="0" dy="3" stdDeviation="3" flood-color="#000000" flood-opacity="0.45"/>
    </filter>
  </defs>
  <g filter="url(#shadow-b)">
    <!-- Base pedestal -->
    <path d="M16 82 Q50 88 84 82 L80 72 Q50 77 20 72 Z" fill="url(#grad-b-base)" stroke="#000000" stroke-width="2.5" stroke-linejoin="round"/>
    <ellipse cx="50" cy="74" rx="30" ry="3.5" fill="#1e293b" stroke="#64748b" stroke-width="1.5"/>
    <!-- Crown Spikes and Body -->
    <path d="M20 72 L13 36 L33 54 L50 20 L67 54 L87 36 L80 72 Z" fill="url(#grad-b-body)" stroke="#000000" stroke-width="2.5" stroke-linejoin="round"/>
    <!-- Silver highlight lines -->
    <path d="M33 54 Q50 64 67 54" stroke="#64748b" stroke-width="1.8" fill="none"/>
    <line x1="50" y1="20" x2="50" y2="65" stroke="#475569" stroke-width="1.8" stroke-dasharray="2 2"/>
    <!-- Pearls on Points -->
    <circle cx="13" cy="35" r="4.5" fill="#334155" stroke="#e2e8f0" stroke-width="1.5"/>
    <circle cx="33" cy="53" r="3.5" fill="#334155" stroke="#e2e8f0" stroke-width="1.5"/>
    <circle cx="50" cy="18" r="5.5" fill="#475569" stroke="#ffffff" stroke-width="1.8"/>
    <circle cx="67" cy="53" r="3.5" fill="#334155" stroke="#e2e8f0" stroke-width="1.5"/>
    <circle cx="87" cy="35" r="4.5" fill="#334155" stroke="#e2e8f0" stroke-width="1.5"/>
    <!-- Cross on Top -->
    <line x1="50" y1="8" x2="50" y2="15" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round"/>
    <line x1="47" y1="11" x2="53" y2="11" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round"/>
  </g>
</svg>`;

const SVG_ARROW = `
<svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <radialGradient id="grad-fire" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#fef08a"/>
      <stop offset="40%" stop-color="#f87171"/>
      <stop offset="100%" stop-color="#dc2626"/>
    </radialGradient>
    <filter id="shadow-arrow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#dc2626" flood-opacity="0.4"/>
    </filter>
  </defs>
  <!-- Flame Core Barrier -->
  <circle cx="50" cy="50" r="28" fill="url(#grad-fire)" stroke="#991b1b" stroke-width="2.5" filter="url(#shadow-arrow)"/>
  <!-- Blocked Star Spikes -->
  <path d="M50 14 L55 36 L78 30 L62 48 L84 62 L60 64 L66 86 L50 70 L34 86 L40 64 L16 62 L38 48 L22 30 L45 36 Z" fill="#ffffff" opacity="0.95" stroke="#b91c1c" stroke-width="1.5"/>
  <!-- Center Core -->
  <circle cx="50" cy="50" r="9" fill="#7f1d1d"/>
  <circle cx="50" cy="50" r="4" fill="#ffffff"/>
</svg>`;

// =====================================================================
// Audio Synthesizer (Zero External Assets)
// =====================================================================
class SoundEffects {
  constructor() {
    this.ctx = null;
    this.enabled = true;
  }

  init() {
    if (!this.ctx && typeof AudioContext !== "undefined") {
      this.ctx = new AudioContext();
    }
    if (this.ctx && this.ctx.state === "suspended") {
      this.ctx.resume();
    }
  }

  playTone(freq, type = "sine", duration = 0.12, gainVal = 0.15) {
    if (!this.enabled) return;
    try {
      this.init();
      if (!this.ctx) return;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = type;
      osc.frequency.setValueAtTime(freq, this.ctx.currentTime);
      gain.gain.setValueAtTime(gainVal, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + duration);

      osc.connect(gain);
      gain.connect(this.ctx.destination);

      osc.start();
      osc.stop(this.ctx.currentTime + duration);
    } catch (e) {
      // Audio autoplay policy fallback
    }
  }

  select() {
    this.playTone(520, "sine", 0.08, 0.1);
  }

  moveQueen() {
    this.playTone(380, "triangle", 0.16, 0.18);
  }

  shootArrow() {
    this.playTone(220, "sawtooth", 0.22, 0.14);
  }

  victory() {
    if (!this.enabled) return;
    const notes = [440, 554, 659, 880];
    notes.forEach((freq, idx) => {
      setTimeout(() => this.playTone(freq, "sine", 0.25, 0.2), idx * 120);
    });
  }
}

const sfx = new SoundEffects();

// =====================================================================
// Pure JS Fast Game Mirror & Rules Engine
// Ensures 0ms instant UI validation & previews
// =====================================================================
class AmazonsRulesEngine {
  constructor(size = 6) {
    this.size = size;
    this.grid = Array(size * size).fill(".");
    this.initBoard();
  }

  initBoard() {
    const n = this.size;
    this.grid = Array(n * n).fill(".");
    let whites = [];
    if (n === 4) {
      whites = [[0, 0], [0, n - 1]];
    } else if (n === 5) {
      const mid = Math.floor(n / 2);
      const off = Math.max(1, Math.floor(n / 4));
      whites = [[0, mid - off], [0, mid + off], [off, mid]];
    } else {
      const third = Math.floor(n / 3);
      whites = [
        [third, 0],
        [third, n - 1],
        [0, third],
        [0, n - 1 - third]
      ];
    }

    whites.forEach(([r, c]) => {
      const posW = r * n + c;
      const posB = (n - 1 - r) * n + (n - 1 - c);
      this.grid[posW] = "W";
      this.grid[posB] = "B";
    });
  }

  getQueenDestinations(startPos) {
    const res = [];
    const n = this.size;
    const rStart = Math.floor(startPos / n);
    const cStart = startPos % n;
    const dirs = [
      [-1, 0], [1, 0], [0, -1], [0, 1],
      [-1, -1], [-1, 1], [1, -1], [1, 1]
    ];

    for (const [dr, dc] of dirs) {
      let r = rStart + dr;
      let c = cStart + dc;
      while (r >= 0 && r < n && c >= 0 && c < n) {
        const p = r * n + c;
        if (this.grid[p] !== ".") break;
        res.push(p);
        r += dr;
        c += dc;
      }
    }
    return res;
  }

  getArrowDestinations(endPos, startPos) {
    // Square at startPos becomes temporarily empty
    const origStart = this.grid[startPos];
    const origEnd = this.grid[endPos];
    this.grid[startPos] = ".";
    this.grid[endPos] = origStart;

    const res = this.getQueenDestinations(endPos);

    this.grid[startPos] = origStart;
    this.grid[endPos] = origEnd;
    return res;
  }

  hasLegalMoves(color) {
    const n = this.size;
    for (let p = 0; p < n * n; p++) {
      if (this.grid[p] === color) {
        const qMoves = this.getQueenDestinations(p);
        if (qMoves.length > 0) return true;
      }
    }
    return false;
  }

  applyMove(startPos, endPos, arrowPos, color) {
    this.grid[startPos] = ".";
    this.grid[endPos] = color;
    this.grid[arrowPos] = "X";
  }

  undoMove(startPos, endPos, arrowPos, color) {
    this.grid[arrowPos] = ".";
    this.grid[endPos] = ".";
    this.grid[startPos] = color;
  }

  toAlgebraic(pos) {
    const row = Math.floor(pos / this.size);
    const col = pos % this.size;
    const letter = String.fromCharCode(97 + col);
    const num = this.size - row;
    return `${letter}${num}`;
  }

  calculateTerritory() {
    const n = this.size;
    const getReachable = (color) => {
      const visited = new Set();
      const queue = [];
      for (let p = 0; p < n * n; p++) {
        if (this.grid[p] === color) {
          queue.push(p);
        }
      }

      while (queue.length > 0) {
        const curr = queue.shift();
        const r = Math.floor(curr / n);
        const c = curr % n;

        for (let dr = -1; dr <= 1; dr++) {
          for (let dc = -1; dc <= 1; dc++) {
            if (dr === 0 && dc === 0) continue;
            const nr = r + dr;
            const nc = c + dc;
            if (nr >= 0 && nr < n && nc >= 0 && nc < n) {
              const np = nr * n + nc;
              if (this.grid[np] === "." && !visited.has(np)) {
                visited.add(np);
                queue.push(np);
              }
            }
          }
        }
      }
      return visited;
    };

    const wSet = getReachable("W");
    const bSet = getReachable("B");

    let wScore = 0;
    let bScore = 0;
    for (let p = 0; p < n * n; p++) {
      if (this.grid[p] === ".") {
        const inW = wSet.has(p);
        const inB = bSet.has(p);
        if (inW && !inB) wScore++;
        else if (inB && !inW) bScore++;
      }
    }
    return [wScore, bScore];
  }
}

// =====================================================================
// Main Game Controller
// =====================================================================
class AmazonsGame {
  constructor() {
    this.size = 6;
    this.gameMode = "human_vs_ai";
    this.aiEngine = "minimax";
    this.aiDepth = 2;
    this.aiEvaluator = "hybrid";
    this.aiTime = 1.0;

    this.rules = new AmazonsRulesEngine(this.size);
    this.currentPlayer = "W";
    this.step = "SELECT_QUEEN"; // "SELECT_QUEEN" | "MOVE_QUEEN" | "SHOOT_ARROW"
    this.selectedQueenPos = null;
    this.selectedEndPos = null;
    this.legalQueenMoves = new Set();
    this.legalArrowTargets = new Set();
    this.lastMove = null;

    this.history = [];
    this.redoStack = [];
    this.isAutoplayActive = false;
    this.isAiComputing = false;

    // Timers
    this.timers = { W: 0, B: 0 };
    this.clockInterval = null;

    // Pyodide Worker
    this.worker = null;
    this.workerReady = false;
    this.workerMsgId = 1;
    this.workerCallbacks = new Map();

    this.initElements();
    this.initWorker();
    this.bindEvents();
    this.resetGame();
  }

  initElements() {
    this.boardEl = document.getElementById("game-board");
    this.coordTopEl = document.getElementById("coord-top");
    this.coordBottomEl = document.getElementById("coord-bottom");
    this.coordLeftEl = document.getElementById("coord-left");
    this.coordRightEl = document.getElementById("coord-right");

    this.turnBannerEl = document.getElementById("turn-banner");
    this.turnAvatarEl = document.getElementById("turn-avatar");
    this.turnPlayerTitleEl = document.getElementById("turn-player-title");
    this.turnStepDescEl = document.getElementById("turn-step-desc");
    this.turnTimerEl = document.getElementById("turn-timer");

    this.cardPlayerWEl = document.getElementById("card-player-w");
    this.cardPlayerBEl = document.getElementById("card-player-b");
    this.namePlayerWEl = document.getElementById("name-player-w");
    this.namePlayerBEl = document.getElementById("name-player-b");
    this.territoryWEl = document.getElementById("territory-w");
    this.territoryBEl = document.getElementById("territory-b");
    this.gaugeFillWEl = document.getElementById("gauge-fill-w");
    this.gaugeFillBEl = document.getElementById("gauge-fill-b");
    this.territoryPctTextEl = document.getElementById("territory-pct-text");

    this.aiMonitorCardEl = document.getElementById("ai-monitor-card");
    this.currentAiBadgeEl = document.getElementById("current-ai-badge");
    this.aiStatusRowEl = document.getElementById("ai-status-row");
    this.aiStatusTextEl = document.getElementById("ai-status-text");
    this.detailSizeEl = document.getElementById("detail-size");
    this.detailDepthEl = document.getElementById("detail-depth");
    this.detailEvalEl = document.getElementById("detail-eval");

    this.historyCountEl = document.getElementById("history-count");
    this.historyTbodyEl = document.getElementById("history-tbody");

    this.btnUndoEl = document.getElementById("btn-undo");
    this.btnRedoEl = document.getElementById("btn-redo");
    this.btnHintEl = document.getElementById("btn-hint");
    this.btnAutoplayEl = document.getElementById("btn-autoplay");
    this.iconPlayEl = document.getElementById("icon-play");
    this.iconPauseEl = document.getElementById("icon-pause");
    this.textAutoplayEl = document.getElementById("text-autoplay");
    this.btnResetEl = document.getElementById("btn-reset");

    this.btnSoundToggleEl = document.getElementById("btn-sound-toggle");
    this.btnRulesEl = document.getElementById("btn-rules");
    this.btnSettingsEl = document.getElementById("btn-settings");
    this.engineStatusBadgeEl = document.getElementById("engine-status-badge");
    this.engineStatusTextEl = document.getElementById("engine-status-text");

    // Modals
    this.modalSettingsEl = document.getElementById("modal-settings");
    this.btnCloseSettingsEl = document.getElementById("btn-close-settings");
    this.btnCancelSettingsEl = document.getElementById("btn-cancel-settings");
    this.btnApplySettingsEl = document.getElementById("btn-apply-settings");

    this.modalRulesEl = document.getElementById("modal-rules");
    this.btnCloseRulesEl = document.getElementById("btn-close-rules");
    this.btnCloseRulesOkEl = document.getElementById("btn-close-rules-ok");

    this.modalGameOverEl = document.getElementById("modal-gameover");
    this.btnReplayEl = document.getElementById("btn-replay");
    this.gameOverTitleEl = document.getElementById("gameover-title");
    this.gameOverMessageEl = document.getElementById("gameover-message");
    this.goMovesCountEl = document.getElementById("go-moves-count");
    this.goWTerritoryEl = document.getElementById("go-w-territory");
    this.goBTerritoryEl = document.getElementById("go-b-territory");

    // Form inputs
    this.selectBoardSizeEl = document.getElementById("select-board-size");
    this.selectGameModeEl = document.getElementById("select-game-mode");
    this.selectAiEngineEl = document.getElementById("select-ai-engine");
    this.selectMinimaxDepthEl = document.getElementById("select-minimax-depth");
    this.selectMinimaxEvalEl = document.getElementById("select-minimax-eval");
    this.selectMctsTimeEl = document.getElementById("select-mcts-time");
    this.minimaxOptionsBoxEl = document.getElementById("minimax-options-box");
    this.mctsOptionsBoxEl = document.getElementById("mcts-options-box");
  }

  initWorker() {
    try {
      this.worker = new Worker("worker.js");
      this.worker.onmessage = (e) => this.handleWorkerMessage(e.data);
      this.worker.onerror = (err) => {
        console.warn("Worker error, running in fast client-engine fallback:", err);
        this.updateEngineBadge(true, "Moteur JS Actif (Fallback)");
      };
    } catch (e) {
      console.warn("Web Worker unavailable, client fallback:", e);
      this.updateEngineBadge(true, "Moteur Client Actif");
    }
  }

  handleWorkerMessage(data) {
    if (data.type === "STATUS") {
      this.updateEngineBadge(false, data.text);
    } else if (data.type === "READY") {
      this.workerReady = true;
      this.updateEngineBadge(true, "Prêt · Python 3.12 (WASM)");
      this.callWorker("RESET", { size: this.size });
    } else if (data.id) {
      const cb = this.workerCallbacks.get(data.id);
      if (cb) {
        this.workerCallbacks.delete(data.id);
        cb(data);
      }
    }
  }

  callWorker(type, payload = {}) {
    return new Promise((resolve) => {
      if (!this.worker || !this.workerReady) {
        resolve({ success: false, fallback: true });
        return;
      }
      const id = this.workerMsgId++;
      this.workerCallbacks.set(id, resolve);
      this.worker.postMessage({ id, type, payload });
    });
  }

  updateEngineBadge(ready, text) {
    if (ready) {
      this.engineStatusBadgeEl.className = "badge badge-ready";
      this.engineStatusBadgeEl.innerHTML = `<span class="pulse-dot"></span><span>${text}</span>`;
    } else {
      this.engineStatusBadgeEl.className = "badge badge-loading";
      this.engineStatusBadgeEl.innerHTML = `<span class="pulse-dot"></span><span>${text}</span>`;
    }
  }

  bindEvents() {
    this.btnResetEl.addEventListener("click", () => this.resetGame());
    this.btnUndoEl.addEventListener("click", () => this.undoMove());
    this.btnRedoEl.addEventListener("click", () => this.redoMove());
    this.btnHintEl.addEventListener("click", () => this.requestHint());
    this.btnAutoplayEl.addEventListener("click", () => this.toggleAutoplay());

    // Sound toggle
    this.btnSoundToggleEl.addEventListener("click", () => {
      sfx.enabled = !sfx.enabled;
      document.querySelector(".icon-sound-on").classList.toggle("hidden", !sfx.enabled);
      document.querySelector(".icon-sound-off").classList.toggle("hidden", sfx.enabled);
    });

    // Modals
    this.btnRulesEl.addEventListener("click", () => this.openRulesModal());
    this.btnCloseRulesEl.addEventListener("click", () => this.closeRulesModal());
    this.btnCloseRulesOkEl.addEventListener("click", () => this.closeRulesModal());

    this.btnSettingsEl.addEventListener("click", () => this.openSettingsModal());
    this.btnCloseSettingsEl.addEventListener("click", () => this.closeSettingsModal());
    this.btnCancelSettingsEl.addEventListener("click", () => this.closeSettingsModal());
    this.btnApplySettingsEl.addEventListener("click", () => this.applySettings());

    this.selectAiEngineEl.addEventListener("change", () => this.updateSettingsFormVisibility());

    this.btnReplayEl.addEventListener("click", () => {
      this.modalGameOverEl.classList.add("hidden");
      this.resetGame();
    });

    // Keyboard shortcuts
    window.addEventListener("keydown", (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
      if (e.key === "u" || e.key === "U") this.undoMove();
      if (e.key === "r" || e.key === "R") this.redoMove();
      if (e.key === "h" || e.key === "H") this.requestHint();
      if (e.key === "Escape") {
        this.closeRulesModal();
        this.closeSettingsModal();
        this.clearSelection();
        this.renderBoard();
      }
    });
  }

  openSettingsModal() {
    this.selectBoardSizeEl.value = String(this.size);
    this.selectGameModeEl.value = this.gameMode;
    this.selectAiEngineEl.value = this.aiEngine;
    this.selectMinimaxDepthEl.value = String(this.aiDepth);
    this.selectMinimaxEvalEl.value = this.aiEvaluator;
    this.selectMctsTimeEl.value = String(this.aiTime);
    this.updateSettingsFormVisibility();
    this.modalSettingsEl.classList.remove("hidden");
  }

  closeSettingsModal() {
    this.modalSettingsEl.classList.add("hidden");
  }

  updateSettingsFormVisibility() {
    const engine = this.selectAiEngineEl.value;
    this.minimaxOptionsBoxEl.classList.toggle("hidden", engine !== "minimax" && engine !== "iterative");
    this.mctsOptionsBoxEl.classList.toggle("hidden", engine !== "mcts");
  }

  applySettings() {
    this.size = parseInt(this.selectBoardSizeEl.value, 10);
    this.gameMode = this.selectGameModeEl.value;
    this.aiEngine = this.selectAiEngineEl.value;
    this.aiDepth = parseInt(this.selectMinimaxDepthEl.value, 10);
    this.aiEvaluator = this.selectMinimaxEvalEl.value;
    this.aiTime = parseFloat(this.selectMctsTimeEl.value);

    this.closeSettingsModal();
    this.resetGame();
  }

  openRulesModal() {
    this.modalRulesEl.classList.remove("hidden");
  }

  closeRulesModal() {
    this.modalRulesEl.classList.add("hidden");
  }

  resetGame() {
    this.isAutoplayActive = false;
    this.updateAutoplayButtonUI();
    this.clearSelection();

    this.rules = new AmazonsRulesEngine(this.size);
    this.currentPlayer = "W";
    this.step = "SELECT_QUEEN";
    this.history = [];
    this.redoStack = [];
    this.lastMove = null;

    this.timers = { W: 0, B: 0 };
    this.startClock();

    if (this.workerReady) {
      this.callWorker("RESET", { size: this.size });
    }

    this.updatePlayerCardsMeta();
    this.updateAiMonitorDetails();
    this.renderCoordinates();
    this.renderBoard();
    this.updateTurnBanner();
    this.updateHistoryTable();
    this.updateTerritoryScores();

    // Check if AI plays first (AI vs Human or AI vs AI)
    this.checkTriggerAiTurn();
  }

  updatePlayerCardsMeta() {
    const isW_AI = this.gameMode === "ai_vs_human" || this.gameMode === "ai_vs_ai";
    const isB_AI = this.gameMode === "human_vs_ai" || this.gameMode === "ai_vs_ai";

    const aiLabel = this.aiEngine === "mcts" ? "MCTS UCT" : (this.aiEngine === "random" ? "Random" : "Minimax");
    this.namePlayerWEl.textContent = isW_AI ? `Blancs (IA ${aiLabel})` : "Blancs (Humain)";
    this.namePlayerBEl.textContent = isB_AI ? `Noirs (IA ${aiLabel})` : "Noirs (Humain)";
  }

  updateAiMonitorDetails() {
    const labelMap = {
      minimax: `Minimax Alpha-Bêta (${this.aiEvaluator})`,
      mcts: `MCTS UCT (${this.aiTime}s)`,
      iterative: `Approfondissement Itératif`,
      random: `Aléatoire (Baseline)`
    };
    this.currentAiBadgeEl.textContent = labelMap[this.aiEngine] || "Minimax";
    this.detailSizeEl.textContent = `${this.size} × ${this.size}`;
    this.detailDepthEl.textContent = this.aiEngine === "mcts" ? `${this.aiTime}s budget` : `Prof. ${this.aiDepth}`;
    this.detailEvalEl.textContent = this.aiEngine === "mcts" ? "Simulations UCT" : (
      this.aiEvaluator === "territory" ? "Territoire pur" : (
        this.aiEvaluator === "mobility" ? "Mobilité pure" : "Territoire + Mobilité"
      )
    );
  }

  startClock() {
    if (this.clockInterval) clearInterval(this.clockInterval);
    this.clockInterval = setInterval(() => {
      this.timers[this.currentPlayer]++;
      this.updateClockUI();
    }, 1000);
  }

  updateClockUI() {
    const fmt = (sec) => {
      const m = String(Math.floor(sec / 60)).padStart(2, "0");
      const s = String(sec % 60).padStart(2, "0");
      return `${m}:${s}`;
    };
    document.getElementById("clock-w").textContent = fmt(this.timers.W);
    document.getElementById("clock-b").textContent = fmt(this.timers.B);
    this.turnTimerEl.textContent = fmt(this.timers[this.currentPlayer]);
  }

  renderCoordinates() {
    const letters = Array.from({ length: this.size }, (_, i) => String.fromCharCode(65 + i));
    const numbers = Array.from({ length: this.size }, (_, i) => String(this.size - i));

    this.coordTopEl.style.gridTemplateColumns = `repeat(${this.size}, 1fr)`;
    this.coordBottomEl.style.gridTemplateColumns = `repeat(${this.size}, 1fr)`;
    this.coordLeftEl.style.gridTemplateRows = `repeat(${this.size}, 1fr)`;
    this.coordRightEl.style.gridTemplateRows = `repeat(${this.size}, 1fr)`;

    this.coordTopEl.innerHTML = letters.map(l => `<span>${l}</span>`).join("");
    this.coordBottomEl.innerHTML = letters.map(l => `<span>${l}</span>`).join("");
    this.coordLeftEl.innerHTML = numbers.map(n => `<span>${n}</span>`).join("");
    this.coordRightEl.innerHTML = numbers.map(n => `<span>${n}</span>`).join("");
  }

  renderBoard() {
    const n = this.size;
    this.boardEl.style.gridTemplateColumns = `repeat(${n}, 1fr)`;
    this.boardEl.style.gridTemplateRows = `repeat(${n}, 1fr)`;
    this.boardEl.innerHTML = "";

    for (let p = 0; p < n * n; p++) {
      const r = Math.floor(p / n);
      const c = p % n;
      const isLight = (r + c) % 2 === 0;

      const cell = document.createElement("div");
      cell.className = `cell ${isLight ? "tile-light" : "tile-dark"}`;
      cell.dataset.pos = p;

      // Selection state
      if (this.selectedQueenPos === p) {
        cell.classList.add("selected-queen");
      }

      // Legal queen moves
      if (this.step === "MOVE_QUEEN" && this.legalQueenMoves.has(p)) {
        cell.classList.add("valid-queen-move");
      }

      // Legal arrow targets
      if (this.step === "SHOOT_ARROW" && this.legalArrowTargets.has(p)) {
        cell.classList.add("valid-arrow-target");
      }

      // Last move highlight
      if (this.lastMove && (this.lastMove.start === p || this.lastMove.end === p || this.lastMove.arrow === p)) {
        cell.classList.add("last-move-cell");
      }

      // Token display
      const pieceVal = this.rules.grid[p];
      if (pieceVal === "W") {
        const piece = document.createElement("div");
        piece.className = "piece piece-queen-w";
        piece.innerHTML = SVG_QUEEN_W;
        cell.appendChild(piece);
      } else if (pieceVal === "B") {
        const piece = document.createElement("div");
        piece.className = "piece piece-queen-b";
        piece.innerHTML = SVG_QUEEN_B;
        cell.appendChild(piece);
      } else if (pieceVal === "X") {
        const piece = document.createElement("div");
        piece.className = "piece piece-arrow";
        piece.innerHTML = SVG_ARROW;
        cell.appendChild(piece);
      }

      cell.addEventListener("click", () => this.handleCellClick(p));
      this.boardEl.appendChild(cell);
    }

    this.btnUndoEl.disabled = this.history.length === 0;
    this.btnRedoEl.disabled = this.redoStack.length === 0;
  }

  clearSelection() {
    this.selectedQueenPos = null;
    this.selectedEndPos = null;
    this.legalQueenMoves.clear();
    this.legalArrowTargets.clear();
    if (this.step !== "GAME_OVER") {
      this.step = "SELECT_QUEEN";
    }
  }

  isCurrentPlayerHuman() {
    if (this.gameMode === "human_vs_human") return true;
    if (this.gameMode === "ai_vs_ai") return false;
    if (this.gameMode === "human_vs_ai" && this.currentPlayer === "W") return true;
    if (this.gameMode === "ai_vs_human" && this.currentPlayer === "B") return true;
    return false;
  }

  handleCellClick(pos) {
    if (this.step === "GAME_OVER" || this.isAiComputing) return;
    if (!this.isCurrentPlayerHuman()) return;

    const cellVal = this.rules.grid[pos];

    // Phase 1: Select Queen
    if (this.step === "SELECT_QUEEN" || this.step === "MOVE_QUEEN") {
      if (cellVal === this.currentPlayer) {
        // Select or switch queen
        this.selectedQueenPos = pos;
        this.step = "MOVE_QUEEN";
        this.legalQueenMoves = new Set(this.rules.getQueenDestinations(pos));
        this.legalArrowTargets.clear();
        sfx.select();
        this.renderBoard();
        this.updateTurnBanner();
        return;
      }

      // If clicked on empty reachable destination
      if (this.step === "MOVE_QUEEN" && this.legalQueenMoves.has(pos)) {
        this.selectedEndPos = pos;
        this.step = "SHOOT_ARROW";
        this.legalArrowTargets = new Set(this.rules.getArrowDestinations(pos, this.selectedQueenPos));
        this.legalQueenMoves.clear();
        sfx.moveQueen();
        this.renderBoard();
        this.updateTurnBanner();
        return;
      }
    }

    // Phase 2: Shoot Arrow
    if (this.step === "SHOOT_ARROW") {
      if (this.legalArrowTargets.has(pos)) {
        // Complete the move!
        this.executeMove(this.selectedQueenPos, this.selectedEndPos, pos);
        return;
      }

      // Cancel selection if clicked elsewhere
      if (cellVal === this.currentPlayer) {
        this.selectedQueenPos = pos;
        this.step = "MOVE_QUEEN";
        this.legalQueenMoves = new Set(this.rules.getQueenDestinations(pos));
        this.legalArrowTargets.clear();
        sfx.select();
        this.renderBoard();
        this.updateTurnBanner();
        return;
      }
    }
  }

  executeMove(startPos, endPos, arrowPos, isAiMove = false) {
    sfx.shootArrow();

    const color = this.currentPlayer;
    this.rules.applyMove(startPos, endPos, arrowPos, color);

    const notation = `${this.rules.toAlgebraic(startPos)}-${this.rules.toAlgebraic(endPos)}/${this.rules.toAlgebraic(arrowPos)}`;
    const moveData = { start: startPos, end: endPos, arrow: arrowPos, color, notation };

    this.lastMove = moveData;
    this.history.push(moveData);
    this.redoStack = [];

    // Sync move to worker in background
    if (this.workerReady) {
      this.callWorker("PLAY_MOVE", { start_pos: startPos, end_pos: endPos, arrow_pos: arrowPos });
    }

    this.clearSelection();
    this.updateHistoryTable();
    this.updateTerritoryScores();

    // Check game over
    const nextPlayer = color === "W" ? "B" : "W";
    if (!this.rules.hasLegalMoves(nextPlayer)) {
      this.handleGameOver(color);
      return;
    }

    // Switch player
    this.currentPlayer = nextPlayer;
    this.step = "SELECT_QUEEN";
    this.renderBoard();
    this.updateTurnBanner();

    // Trigger AI if next turn is AI
    this.checkTriggerAiTurn();
  }

  undoMove() {
    if (this.history.length === 0 || this.isAiComputing) return;

    // In Human vs AI, undo twice to revert full round
    const stepsToUndo = (this.gameMode === "human_vs_ai" || this.gameMode === "ai_vs_human") && this.history.length >= 2 ? 2 : 1;

    for (let i = 0; i < stepsToUndo; i++) {
      if (this.history.length === 0) break;
      const last = this.history.pop();
      this.rules.undoMove(last.start, last.end, last.arrow, last.color);
      this.currentPlayer = last.color;
      this.redoStack.push(last);
    }

    this.lastMove = this.history.length > 0 ? this.history[this.history.length - 1] : null;
    this.clearSelection();

    if (this.workerReady) {
      for (let i = 0; i < stepsToUndo; i++) this.callWorker("UNDO");
    }

    this.renderBoard();
    this.updateTurnBanner();
    this.updateHistoryTable();
    this.updateTerritoryScores();
  }

  redoMove() {
    if (this.redoStack.length === 0 || this.isAiComputing) return;
    const nxt = this.redoStack.pop();
    this.rules.applyMove(nxt.start, nxt.end, nxt.arrow, nxt.color);
    this.lastMove = nxt;
    this.history.push(nxt);
    this.currentPlayer = nxt.color === "W" ? "B" : "W";

    if (this.workerReady) {
      this.callWorker("REDO");
    }

    this.clearSelection();
    this.renderBoard();
    this.updateTurnBanner();
    this.updateHistoryTable();
    this.updateTerritoryScores();
  }

  async checkTriggerAiTurn() {
    if (this.step === "GAME_OVER") return;
    if (this.isCurrentPlayerHuman()) return;

    this.isAiComputing = true;
    this.setAiComputingUI(true);

    const startTime = performance.now();
    let move = null;

    if (this.workerReady) {
      const resp = await this.callWorker("COMPUTE_AI_MOVE", {
        ai_mode: this.aiEngine,
        ai_time: this.aiTime,
        depth: this.aiDepth,
        evaluator: this.aiEvaluator
      });

      if (resp.success && resp.result && resp.result.success) {
        move = resp.result.move;
      }
    }

    // Client fallback if worker failed or taking too long
    if (!move) {
      move = this.computeFallbackAiMove();
    }

    const elapsed = performance.now() - startTime;
    const minDelay = this.isAutoplayActive ? 400 : Math.max(300, 800 - elapsed);
    setTimeout(() => {
      this.isAiComputing = false;
      this.setAiComputingUI(false);
      if (move) {
        this.executeMove(move.start_pos !== undefined ? move.start_pos : move.start,
                         move.end_pos !== undefined ? move.end_pos : move.end,
                         move.arrow_pos !== undefined ? move.arrow_pos : move.arrow,
                         true);
      }
    }, minDelay);
  }

  computeFallbackAiMove() {
    const color = this.currentPlayer;
    const n = this.size;
    const candidates = [];

    for (let p = 0; p < n * n; p++) {
      if (this.rules.grid[p] === color) {
        const qMoves = this.rules.getQueenDestinations(p);
        for (const qEnd of qMoves) {
          const aMoves = this.rules.getArrowDestinations(qEnd, p);
          for (const aPos of aMoves) {
            candidates.push({ start_pos: p, end_pos: qEnd, arrow_pos: aPos });
          }
        }
      }
    }

    if (candidates.length === 0) return null;

    // Pick move prioritizing central queen destination
    const center = n / 2;
    candidates.sort((a, b) => {
      const distA = Math.abs(Math.floor(a.end_pos / n) - center) + Math.abs((a.end_pos % n) - center);
      const distB = Math.abs(Math.floor(b.end_pos / n) - center) + Math.abs((b.end_pos % n) - center);
      return distA - distB;
    });

    const topPool = candidates.slice(0, Math.min(10, candidates.length));
    return topPool[Math.floor(Math.random() * topPool.length)];
  }

  async requestHint() {
    if (this.isAiComputing || this.step === "GAME_OVER") return;
    this.isAiComputing = true;
    this.setAiComputingUI(true, "Calcul du meilleur coup conseillé...");

    let move = null;
    if (this.workerReady) {
      const resp = await this.callWorker("COMPUTE_AI_MOVE", {
        ai_mode: "minimax",
        ai_time: 1.0,
        depth: 2,
        evaluator: "hybrid"
      });
      if (resp.success && resp.result && resp.result.success) {
        move = resp.result.move;
      }
    }

    if (!move) move = this.computeFallbackAiMove();

    this.isAiComputing = false;
    this.setAiComputingUI(false);

    if (move) {
      const start = move.start_pos !== undefined ? move.start_pos : move.start;
      const end = move.end_pos !== undefined ? move.end_pos : move.end;
      const arrow = move.arrow_pos !== undefined ? move.arrow_pos : move.arrow;

      const not = `${this.rules.toAlgebraic(start)}-${this.rules.toAlgebraic(end)}/${this.rules.toAlgebraic(arrow)}`;
      alert(`💡 Conseil de l'IA Amazons : Coup recommandé : ${not}\n(Déplacez l'amazone en ${this.rules.toAlgebraic(start)} vers ${this.rules.toAlgebraic(end)} et tirez en ${this.rules.toAlgebraic(arrow)})`);
    }
  }

  toggleAutoplay() {
    this.isAutoplayActive = !this.isAutoplayActive;
    if (this.isAutoplayActive) {
      this.gameMode = "ai_vs_ai";
      this.updatePlayerCardsMeta();
    }
    this.updateAutoplayButtonUI();
    if (this.isAutoplayActive && !this.isAiComputing) {
      this.checkTriggerAiTurn();
    }
  }

  updateAutoplayButtonUI() {
    this.iconPlayEl.classList.toggle("hidden", this.isAutoplayActive);
    this.iconPauseEl.classList.toggle("hidden", !this.isAutoplayActive);
    this.textAutoplayEl.textContent = this.isAutoplayActive ? "Pause" : "Auto IA";
  }

  setAiComputingUI(isComputing, customText = null) {
    this.aiStatusRowEl.classList.toggle("computing", isComputing);
    if (isComputing) {
      this.aiStatusTextEl.textContent = customText || `IA (${this.aiEngine.toUpperCase()}) réfléchit au meilleur coup...`;
    } else {
      this.aiStatusTextEl.textContent = this.isCurrentPlayerHuman() ? "En attente de votre coup..." : "Coup joué.";
    }
  }

  updateTurnBanner() {
    const isW = this.currentPlayer === "W";
    this.turnBannerEl.classList.toggle("white-active", isW);
    this.turnBannerEl.classList.toggle("black-active", !isW);

    this.cardPlayerWEl.classList.toggle("active", isW);
    this.cardPlayerBEl.classList.toggle("active", !isW);

    this.turnAvatarEl.innerHTML = `<span class="player-token-badge ${isW ? 'token-w' : 'token-b'}"></span>`;
    this.turnPlayerTitleEl.textContent = isW ? "Au tour des Blancs" : "Au tour des Noirs";

    if (this.isCurrentPlayerHuman()) {
      if (this.step === "SELECT_QUEEN") {
        this.turnStepDescEl.textContent = "Étape 1/3 : Cliquez sur une de vos amazones";
      } else if (this.step === "MOVE_QUEEN") {
        this.turnStepDescEl.textContent = "Étape 2/3 : Cliquez sur une case illuminée en cyan";
      } else if (this.step === "SHOOT_ARROW") {
        this.turnStepDescEl.textContent = "Étape 3/3 : Visez une case pour tirer la flèche";
      }
    } else {
      this.turnStepDescEl.textContent = "L'ordinateur calcule sa trajectoire...";
    }
  }

  updateTerritoryScores() {
    const [wScore, bScore] = this.rules.calculateTerritory();
    this.territoryWEl.textContent = wScore;
    this.territoryBEl.textContent = bScore;

    const total = wScore + bScore || 1;
    const wPct = Math.round((wScore / total) * 100);
    const bPct = 100 - wPct;

    this.gaugeFillWEl.style.width = `${wPct}%`;
    this.gaugeFillBEl.style.width = `${bPct}%`;
    this.territoryPctTextEl.textContent = `${wPct}% / ${bPct}%`;
  }

  updateHistoryTable() {
    this.historyCountEl.textContent = `${this.history.length} coup${this.history.length > 1 ? "s" : ""}`;

    if (this.history.length === 0) {
      this.historyTbodyEl.innerHTML = `
        <tr class="empty-row">
          <td colspan="3">Aucun coup joué pour le moment</td>
        </tr>`;
      return;
    }

    let rowsHtml = "";
    for (let i = 0; i < this.history.length; i += 2) {
      const turnNum = Math.floor(i / 2) + 1;
      const wMove = this.history[i] ? this.history[i].notation : "-";
      const bMove = this.history[i + 1] ? this.history[i + 1].notation : "-";

      rowsHtml += `
        <tr>
          <td><strong>${turnNum}.</strong></td>
          <td>${wMove}</td>
          <td>${bMove}</td>
        </tr>`;
    }

    this.historyTbodyEl.innerHTML = rowsHtml;
    const container = document.getElementById("history-container");
    container.scrollTop = container.scrollHeight;
  }

  handleGameOver(winnerColor) {
    this.step = "GAME_OVER";
    if (this.clockInterval) clearInterval(this.clockInterval);
    sfx.victory();

    const winnerName = winnerColor === "W" ? "Blancs" : "Noirs";
    this.gameOverTitleEl.textContent = `Victoire des ${winnerName} !`;
    this.gameOverMessageEl.textContent = `L'adversaire n'a plus aucun coup légal disponible. Les ${winnerName} dominent le plateau !`;

    const [wScore, bScore] = this.rules.calculateTerritory();
    this.goMovesCountEl.textContent = this.history.length;
    this.goWTerritoryEl.textContent = wScore;
    this.goBTerritoryEl.textContent = bScore;

    this.modalGameOverEl.classList.remove("hidden");
  }
}

// Start application when DOM is ready
window.addEventListener("DOMContentLoaded", () => {
  window.amazonsApp = new AmazonsGame();
});
