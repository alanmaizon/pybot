/* PyBot is loaded from this repository's source and executed by Pyodide in the browser. */
const PYBOT_REPOSITORY = "alanmaizon/pybot";
const PYBOT_BRANCH = "main";
const PYBOT_TREE =
  `https://api.github.com/repos/${PYBOT_REPOSITORY}/git/trees/${PYBOT_BRANCH}?recursive=1`;
const PYBOT_RAW_ROOT =
  `https://raw.githubusercontent.com/${PYBOT_REPOSITORY}/${PYBOT_BRANCH}/`;
const MEMORY_STORAGE_KEY = "pybot.conversation.v1";
const MAX_STORED_MEMORY_BYTES = 1_500_000;

const form = document.querySelector("#chat-form");
const input = document.querySelector("#message-input");
const sendButton = document.querySelector("#send-button");
const resetButton = document.querySelector("#reset-button");
const memoryButton = document.querySelector("#memory-button");
const memoryPanel = document.querySelector("#memory-panel");
const memoryList = document.querySelector("#memory-list");
const memoryEmpty = document.querySelector("#memory-empty");
const clearMemoryButton = document.querySelector("#clear-memory-button");
const diagnosticsButton = document.querySelector("#diagnostics-button");
const diagnosticsPanel = document.querySelector("#diagnostics-panel");
const diagnosticsOutput = document.querySelector("#diagnostics-output");
const refreshDiagnosticsButton = document.querySelector("#refresh-diagnostics-button");
const chatLog = document.querySelector("#chat-log");
const status = document.querySelector("#status");

let pyodide;
let conversation;
let currentQuery = "";

function addMessage(who, text) {
  const message = document.createElement("div");
  message.className = `message ${who === "You" ? "user-message" : "bot-message"}`;
  const label = document.createElement("span");
  label.className = "message-label";
  label.textContent = who;
  const body = document.createElement("p");
  body.textContent = text;
  message.append(label, body);
  chatLog.append(message);
  chatLog.scrollTop = chatLog.scrollHeight;
}

async function loadBot() {
  pybotDiagnostics.mark("runtimeStatus", "initialising");
  pyodide = await loadPyodide();
  const treeResponse = await fetch(PYBOT_TREE);
  if (!treeResponse.ok) {
    throw new Error(`Could not find PyBot source (${treeResponse.status}).`);
  }
  const tree = await treeResponse.json();
  const sourceFiles = tree.tree.filter(
    (entry) => entry.type === "blob" && entry.path.startsWith("bot/") &&
      entry.path.endsWith(".py")
  );
  if (!sourceFiles.length) throw new Error("The PyBot source tree is empty.");
  await Promise.all(sourceFiles.map(async (entry) => {
    const response = await fetch(PYBOT_RAW_ROOT + entry.path);
    if (!response.ok) throw new Error(`Could not download ${entry.path}.`);
    const bytes = new Uint8Array(await response.arrayBuffer());
    pyodide.FS.mkdirTree(`/tmp/pybot-source/${entry.path.split("/").slice(0, -1).join("/")}`);
    pyodide.FS.writeFile(`/tmp/pybot-source/${entry.path}`, bytes);
  }));
  await pyodide.runPythonAsync(`
import os
import sys
import json

sys.path.insert(0, "/tmp/pybot-source")

from bot import runtime
from bot.memory import structured
_pybot_memory = {}

def _pybot_answer(text):
    return runtime.turn(text, _pybot_memory)["reply"]

def _pybot_export_memory():
    return json.dumps(_pybot_memory, separators=(",", ":"))

def _pybot_restore_memory(serialized):
    loaded = json.loads(serialized)
    if not isinstance(loaded, dict):
        raise ValueError("Stored PyBot memory is not an object.")
    _pybot_memory.clear()
    _pybot_memory.update(loaded)

def _pybot_turns():
    return json.dumps(_pybot_memory.get("turns", []), separators=(",", ":"))

def _pybot_modules():
    return json.dumps([name for name, _, _ in runtime._MODULES], separators=(",", ":"))

def _pybot_structured_memory():
    return json.dumps(structured.all_records(_pybot_memory), separators=(",", ":"))

def _pybot_retrieve(query):
    return json.dumps(structured.find(_pybot_memory, query), separators=(",", ":"))

def _pybot_update_memory(record_id, value):
    return structured.update(_pybot_memory, record_id, value)

def _pybot_delete_memory(record_id):
    return structured.delete(_pybot_memory, record_id)

def _pybot_clear_structured_memory():
    structured.clear(_pybot_memory)
`);
  conversation = (text) => pyodide.runPython(
    "_pybot_answer(" + JSON.stringify(text) + ")"
  );
  pybotDiagnostics.mark("runtimeStatus", "ready");
  pybotDiagnostics.mark("loadedModules",
    JSON.parse(pyodide.runPython("_pybot_modules()")));
}

function saveMemory() {
  const serialized = pyodide.runPython("_pybot_export_memory()");
  const saved = pybotPersistence.save(MEMORY_STORAGE_KEY, serialized, MAX_STORED_MEMORY_BYTES);
  pybotDiagnostics.mark("storageBytes", pybotPersistence.usage(MEMORY_STORAGE_KEY));
  pybotDiagnostics.mark("persistenceStatus", saved ? "saved" : "unavailable or too large");
}

function restoreMemory() {
  const loaded = pybotPersistence.loadJson(MEMORY_STORAGE_KEY);
  if (!loaded || typeof loaded !== "object" || Array.isArray(loaded)) return false;
  const serialized = JSON.stringify(loaded);
  try {
    pyodide.runPython("_pybot_restore_memory(" + JSON.stringify(serialized) + ")");
    return true;
  } catch (error) {
    pybotDiagnostics.recordError(error, "memory restore");
    pybotPersistence.remove(MEMORY_STORAGE_KEY);
    return false;
  }
}

function renderStoredConversation() {
  const turns = JSON.parse(pyodide.runPython("_pybot_turns()"));
  chatLog.replaceChildren();
  for (const turn of turns) {
    if (!turn || typeof turn !== "object") continue;
    if (turn.user) addMessage("You", turn.user);
    if (turn.bot) addMessage("PyBot", turn.bot);
  }
  return turns.length > 0;
}

function getMemories() {
  return JSON.parse(pyodide.runPython("_pybot_structured_memory()"));
}

function renderMemories() {
  const memories = getMemories();
  memoryList.replaceChildren();
  memoryEmpty.hidden = memories.length > 0;
  for (const memory of memories) {
    const item = document.createElement("div");
    item.className = "memory-item";
    const field = document.createElement("label");
    const category = document.createElement("small");
    category.textContent = memory.category.replaceAll("_", " ");
    const input = document.createElement("input");
    input.type = "text";
    input.value = memory.value;
    input.setAttribute("aria-label", memory.key);
    field.append(category, input);
    const actions = document.createElement("div");
    actions.className = "memory-actions";
    const save = document.createElement("button");
    save.type = "button";
    save.textContent = "Save";
    save.addEventListener("click", () => {
      if (!input.value.trim()) return;
      pyodide.runPython("_pybot_update_memory(" +
        JSON.stringify(memory.id) + ", " + JSON.stringify(input.value.trim()) + ")");
      saveMemory();
      renderMemories();
    });
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "delete-memory";
    remove.textContent = "Delete";
    remove.addEventListener("click", () => {
      pyodide.runPython("_pybot_delete_memory(" + JSON.stringify(memory.id) + ")");
      saveMemory();
      renderMemories();
    });
    actions.append(save, remove);
    item.append(field, actions);
    memoryList.append(item);
  }
}

function renderDiagnostics() {
  if (!pyodide) return;
  try {
    const turns = JSON.parse(pyodide.runPython("_pybot_turns()"));
    const serialized = pyodide.runPython("_pybot_export_memory()");
    const memories = getMemories();
    const retrieved = currentQuery
      ? JSON.parse(pyodide.runPython("_pybot_retrieve(" + JSON.stringify(currentQuery) + ")"))
      : [];
    pybotDiagnostics.mark("contextTurns", turns.length);
    pybotDiagnostics.mark("contextBytes", serialized.length);
    pybotDiagnostics.mark("memoryCount", memories.length);
    pybotDiagnostics.mark("retrievedMemories", retrieved.map((item) => ({
      id: item.id,
      category: item.category,
      importance: item.importance,
      confidence: item.confidence,
      provenance: item.provenance,
    })));
    pybotDiagnostics.mark("storageBytes", pybotPersistence.usage(MEMORY_STORAGE_KEY));
    diagnosticsOutput.textContent = JSON.stringify(pybotDiagnostics.snapshot(), null, 2);
  } catch (error) {
    pybotDiagnostics.recordError(error, "diagnostics");
    diagnosticsOutput.textContent = JSON.stringify(pybotDiagnostics.snapshot(), null, 2);
  }
}

async function start() {
  try {
    await loadBot();
    const restored = restoreMemory();
    input.disabled = false;
    sendButton.disabled = false;
    resetButton.disabled = false;
    memoryButton.disabled = false;
    diagnosticsButton.disabled = false;
    status.textContent = "Ready. PyBot runs locally in your browser.";
    input.focus();
    if (!restored || !renderStoredConversation()) {
      chatLog.replaceChildren();
      addMessage("PyBot", "Hello! What can I help with?");
    }
    renderDiagnostics();
  } catch (error) {
    console.error(error);
    pybotDiagnostics.recordError(error, "initialisation");
    pybotDiagnostics.mark("runtimeStatus", "error");
    status.textContent = "PyBot could not be loaded. Check the browser console and try again.";
    chatLog.replaceChildren();
    addMessage("PyBot", "Sorry, PyBot could not start.");
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text || !conversation) return;
  addMessage("You", text);
  input.value = "";
  sendButton.disabled = true;
  currentQuery = text;
  try {
    const retrievalStarted = performance.now();
    const retrieved = JSON.parse(pyodide.runPython(
      "_pybot_retrieve(" + JSON.stringify(text) + ")"));
    pybotDiagnostics.mark("retrievedMemories", retrieved.map((item) => ({
      id: item.id,
      category: item.category,
      importance: item.importance,
      confidence: item.confidence,
      provenance: item.provenance,
    })));
    pybotDiagnostics.mark("retrievalMs", Math.round(performance.now() - retrievalStarted));
    const responseStarted = performance.now();
    addMessage("PyBot", conversation(text));
    pybotDiagnostics.mark("responseMs", Math.round(performance.now() - responseStarted));
    saveMemory();
    if (!memoryPanel.hidden) renderMemories();
    if (!diagnosticsPanel.hidden) renderDiagnostics();
  } catch (error) {
    console.error(error);
    pybotDiagnostics.recordError(error, "python response");
    addMessage("PyBot", "I couldn't answer that. Please try again.");
  } finally {
    sendButton.disabled = false;
    input.focus();
  }
});

resetButton.addEventListener("click", () => {
  if (!pyodide) return;
  pyodide.runPython("_pybot_memory.clear()");
  pybotPersistence.remove(MEMORY_STORAGE_KEY);
  chatLog.replaceChildren();
  renderMemories();
  renderDiagnostics();
  addMessage("PyBot", "New conversation. What can I help with?");
  input.focus();
});

memoryButton.addEventListener("click", () => {
  memoryPanel.hidden = !memoryPanel.hidden;
  if (!memoryPanel.hidden) renderMemories();
});

diagnosticsButton.addEventListener("click", () => {
  diagnosticsPanel.hidden = !diagnosticsPanel.hidden;
  if (!diagnosticsPanel.hidden) renderDiagnostics();
});

refreshDiagnosticsButton.addEventListener("click", renderDiagnostics);

clearMemoryButton.addEventListener("click", () => {
  if (!pyodide || !window.confirm("Clear all remembered facts?")) return;
  pyodide.runPython("_pybot_clear_structured_memory()");
  saveMemory();
  renderMemories();
  renderDiagnostics();
});

start();
