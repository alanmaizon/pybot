const log = document.querySelector("#chat-log");
const form = document.querySelector("#chat-form");
const input = document.querySelector("#message-input");
const send = document.querySelector("#send-button");
const statusLine = document.querySelector("#status");
const initialLog = log.firstElementChild.cloneNode(true);
let worker;

function reset() {
  worker?.terminate();
  worker = undefined;
  send.disabled = false;
  input.value = "";
  log.replaceChildren(initialLog.cloneNode(true));
  statusLine.textContent = "New conversation.";
  input.focus();
}

form.addEventListener("submit", event => {
  event.preventDefault();
  const prompt = input.value.trim();
  if (!prompt || send.disabled) return;
  if (prompt.toLowerCase() === "/reset") return reset();
  log.querySelector(".empty")?.remove();
  const question = document.createElement("p");
  question.className = "question";
  question.textContent = prompt;
  const group = document.createElement("div");
  log.append(question, group);
  log.scrollTop = log.scrollHeight;
  send.disabled = true;
  input.value = "";
  statusLine.textContent = worker ? "Running the rules…" : "Loading the original Python bot on your device…";
  function fail() {
    group.textContent = "This turn failed. Send your question again to start a fresh conversation.";
    worker?.terminate();
    worker = undefined;
    send.disabled = false;
    statusLine.textContent = "Runtime stopped.";
    if (!input.value) input.value = prompt;
  }
  try {
    worker ??= new Worker("watch/worker.js?mode=chat");
    const active = worker;
    worker.onerror = () => { if (worker === active) fail(); };
    worker.onmessage = ({data}) => {
      if (worker !== active) return;
      if (data.error) return fail();
      renderCandidates(data, group);
      statusLine.textContent = "Ready for your next message.";
      send.disabled = false;
      log.scrollTop += question.getBoundingClientRect().top - log.getBoundingClientRect().top - 12;
    };
    worker.postMessage(prompt);
  } catch { fail(); }
});
document.querySelector("#reset-button").addEventListener("click", reset);
