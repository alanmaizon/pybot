/* PyBot is loaded from this repository's source and executed by Pyodide in the browser. */
const PYBOT_REPOSITORY = "alanmaizon/pybot";
const PYBOT_BRANCH = "main";
const PYBOT_TREE =
  `https://api.github.com/repos/${PYBOT_REPOSITORY}/git/trees/${PYBOT_BRANCH}?recursive=1`;
const PYBOT_RAW_ROOT =
  `https://raw.githubusercontent.com/${PYBOT_REPOSITORY}/${PYBOT_BRANCH}/`;

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

sys.path.insert(0, "/tmp/pybot-source")

from bot import runtime
_pybot_memory = {}
`);
  conversation = (text) => pyodide.runPython(
    "runtime.turn(" + JSON.stringify(text) + ", _pybot_memory)['reply']"
  );
}

async function start() {
  try {
    await loadBot();
    input.disabled = false;
    sendButton.disabled = false;
    resetButton.disabled = false;
    status.textContent = "Ready. PyBot runs locally in your browser.";
    input.focus();
    chatLog.replaceChildren();
    addMessage("PyBot", "Hello! What can I help with?");
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
  chatLog.replaceChildren();
  addMessage("PyBot", "New conversation. What can I help with?");
  input.focus();
});

start();
