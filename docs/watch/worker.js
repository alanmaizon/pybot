let python;
async function load() {
  importScripts("https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.js");
  const runtime = await loadPyodide();
  const archive = await fetch("baseline.zip");
  if (!archive.ok) throw Error("Missing baseline");
  runtime.unpackArchive(await archive.arrayBuffer(), "zip");
  runtime.runPython("import json, random\nfrom bot.runtime import turn");
  return runtime;
}
onmessage = async ({data}) => {
  try {
    python ??= await load();
    python.globals.set("prompt", data);
    const result = python.runPython("random.seed(7)\njson.dumps(turn(prompt, {}))");
    postMessage(JSON.parse(result));
  } catch { postMessage({error:true}); }
};
