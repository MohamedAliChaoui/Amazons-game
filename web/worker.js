/**
 * Web Worker for Pyodide Amazons Engine.
 * Runs Python WebAssembly in the background without blocking the UI.
 */

/* global importScripts, loadPyodide, AMAZONS_PYTHON_CODE */

importScripts("engine_source.js");
importScripts("https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js");

let pyodide = null;
let isReady = false;

async function setup() {
  try {
    postMessage({ type: "STATUS", text: "Initialisation de WebAssembly (Pyodide 0.26)..." });

    pyodide = await loadPyodide({
      indexURL: "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/"
    });

    postMessage({ type: "STATUS", text: "Chargement du moteur Python Amazons (Bitboards & IA)..." });

    // Execute the bundled Python engine code
    await pyodide.runPythonAsync(AMAZONS_PYTHON_CODE);

    isReady = true;
    postMessage({ type: "READY" });
  } catch (err) {
    console.error("Worker Pyodide Error:", err);
    postMessage({ type: "ERROR", error: String(err) });
  }
}

self.onmessage = async function(event) {
  const { id, type, payload } = event.data;

  if (!isReady && type !== "PING") {
    postMessage({ id, success: false, error: "Pyodide not ready yet" });
    return;
  }

  try {
    let result = null;

    switch (type) {
      case "RESET": {
        const pyCall = `web_reset(${payload.size || 6})`;
        const resStr = pyodide.runPython(pyCall);
        result = JSON.parse(resStr);
        break;
      }

      case "GET_STATE": {
        const resStr = pyodide.runPython("web_get_state()");
        result = JSON.parse(resStr);
        break;
      }

      case "GET_QUEEN_MOVES": {
        const pyCall = `web_get_queen_moves(${payload.start_pos})`;
        const resStr = pyodide.runPython(pyCall);
        result = JSON.parse(resStr);
        break;
      }

      case "GET_ARROW_MOVES": {
        const pyCall = `web_get_arrow_moves(${payload.end_pos}, ${payload.start_pos})`;
        const resStr = pyodide.runPython(pyCall);
        result = JSON.parse(resStr);
        break;
      }

      case "PLAY_MOVE": {
        const pyCall = `web_play_move(${payload.start_pos}, ${payload.end_pos}, ${payload.arrow_pos})`;
        const resStr = pyodide.runPython(pyCall);
        result = JSON.parse(resStr);
        break;
      }

      case "UNDO": {
        const resStr = pyodide.runPython("web_undo()");
        result = JSON.parse(resStr);
        break;
      }

      case "REDO": {
        const resStr = pyodide.runPython("web_redo()");
        result = JSON.parse(resStr);
        break;
      }

      case "COMPUTE_AI_MOVE": {
        const mode = payload.ai_mode || "minimax";
        const timeLimit = payload.ai_time || 1.0;
        const depth = payload.depth || 2;
        const evaluator = payload.evaluator || "hybrid";

        const pyCall = `web_compute_ai_move('${mode}', ${timeLimit}, ${depth}, '${evaluator}')`;
        const resStr = pyodide.runPython(pyCall);
        result = JSON.parse(resStr);
        break;
      }

      default:
        throw new Error(`Unknown command type: ${type}`);
    }

    postMessage({ id, success: true, result });
  } catch (err) {
    console.error("Worker command error:", err);
    postMessage({ id, success: false, error: String(err) });
  }
};

setup();
