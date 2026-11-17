function show(result, target) {
  target.replaceChildren();
  for (const candidate of result.candidates) {
    const card = document.createElement("article");
    const label = document.createElement("strong");
    label.textContent = (result.module === candidate.module ? "Chosen" : "Alternative") + " · " + candidate.module;
    const reply = document.createElement("p");
    reply.textContent = candidate.reply;
    card.append(label, reply);
    target.append(card);
  }
  if (!result.candidates.length) target.textContent = result.reply;
}
const record = document.querySelector("#record");
fetch("example.json").then(r => r.json()).then(data => show(data, record)).catch(() => record.textContent = "Reload to see the example.");
const run = document.querySelector("#run");
const statusLine = document.querySelector("#status");
let worker;
run.onclick = () => {
  const prompt = document.querySelector("#prompt").value.trim();
  if (!prompt) return;
  run.disabled = true;
  document.querySelector("#output").replaceChildren();
  statusLine.textContent = worker ? "Running the rules…" : "Loading Python on your device. The first run takes longer.";
  function failed() {
    worker?.terminate(); worker = null; run.disabled = false;
    statusLine.textContent = "The run failed. Check your connection and try again.";
  }
  try {
    worker ??= new Worker("worker.js");
    worker.onerror = failed;
    worker.onmessage = ({data}) => {
      if (data.error) { failed(); return; }
      show(data, document.querySelector("#output"));
      run.disabled = false; statusLine.textContent = "Run complete.";
    };
    worker.postMessage(prompt);
  } catch { failed(); }
};
