const record = document.querySelector("#record");
fetch("example.json").then(r => r.json()).then(data => renderCandidates(data, record)).catch(() => record.textContent = "Reload to see the example.");
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
      renderCandidates(data, document.querySelector("#output"));
      run.disabled = false; statusLine.textContent = "Run complete.";
    };
    worker.postMessage(prompt);
  } catch { failed(); }
};
