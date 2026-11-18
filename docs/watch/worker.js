const chat = new URL(self.location.href).searchParams.get("mode") === "chat";
let python;
async function load() {
  importScripts("https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.js");
  const runtime = await loadPyodide();
  const archive = await fetch("baseline.zip");
  if (!archive.ok) throw Error("Missing baseline");
  runtime.unpackArchive(await archive.arrayBuffer(), "zip");
  runtime.runPython("import json, random\nfrom bot.runtime import turn\nrandom.seed(7)\nmemory = {}");
  return runtime;
}
onmessage = async ({data}) => {
  try {
    python ??= await load();
    python.globals.set("prompt", data);
    if (!chat) python.runPython("memory.clear()\nrandom.seed(7)");
    const result = python.runPython("json.dumps(turn(prompt, memory))");
    postMessage(JSON.parse(result));
  } catch { postMessage({error:true}); }
};
