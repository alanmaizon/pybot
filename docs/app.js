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
const chatLog = document.querySelector("#chat-log");
const status = document.querySelector("#status");

let pyodide;
let conversation;

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
`);
  conversation = (text) => pyodide.runPython(
    "_pybot_answer(" + JSON.stringify(text) + ")"
  );
}

function saveMemory() {
  try {
    const serialized = pyodide.runPython("_pybot_export_memory()");
    if (serialized.length > MAX_STORED_MEMORY_BYTES) {
      console.warn("PyBot memory is too large to persist locally.");
      return;
    }
    localStorage.setItem(MEMORY_STORAGE_KEY, serialized);
  } catch (error) {
    console.warn("PyBot memory could not be saved locally.", error);
  }
}

function restoreMemory() {
  let serialized;
  try {
    serialized = localStorage.getItem(MEMORY_STORAGE_KEY);
  } catch (error) {
    console.warn("Local PyBot memory is unavailable.", error);
    return false;
  }
  if (!serialized) return false;
  try {
    pyodide.runPython("_pybot_restore_memory(" + JSON.stringify(serialized) + ")");
    return true;
  } catch (error) {
    console.warn("Stored PyBot memory was invalid and has been discarded.", error);
    try {
      localStorage.removeItem(MEMORY_STORAGE_KEY);
    } catch (storageError) {
      console.warn("Invalid PyBot memory could not be removed.", storageError);
    }
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

async function start() {
  try {
    await loadBot();
    const restored = restoreMemory();
    input.disabled = false;
    sendButton.disabled = false;
    resetButton.disabled = false;
    status.textContent = "Ready. PyBot runs locally in your browser.";
    input.focus();
    if (!restored || !renderStoredConversation()) {
      chatLog.replaceChildren();
      addMessage("PyBot", "Hello! What can I help with?");
    }
  } catch (error) {
    console.error(error);
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
  try {
    addMessage("PyBot", conversation(text));
    saveMemory();
  } catch (error) {
    console.error(error);
    addMessage("PyBot", "I couldn't answer that. Please try again.");
  } finally {
    sendButton.disabled = false;
    input.focus();
  }
});

resetButton.addEventListener("click", () => {
  if (!pyodide) return;
  pyodide.runPython("_pybot_memory.clear()");
  try {
    localStorage.removeItem(MEMORY_STORAGE_KEY);
  } catch (error) {
    console.warn("PyBot local memory could not be cleared.", error);
  }
  chatLog.replaceChildren();
  addMessage("PyBot", "New conversation. What can I help with?");
  input.focus();
});

start();
