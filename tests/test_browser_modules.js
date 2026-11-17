/* Minimal no-browser regression checks for the local diagnostics/persistence modules. */
const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

const listeners = {};
const storage = new Map();
const window = {
  localStorage: {
    getItem: (key) => storage.has(key) ? storage.get(key) : null,
    setItem: (key, value) => storage.set(key, value),
    removeItem: (key) => storage.delete(key),
  },
  addEventListener: (name, handler) => { listeners[name] = handler; },
  fetch: async () => ({ status: 200, ok: true }),
};
const context = {
  window,
  performance: { now: () => 100 },
  Date,
  console,
  fetch: window.fetch,
};
vm.createContext(context);
vm.runInContext(fs.readFileSync("docs/persistence.js", "utf8"), context);
vm.runInContext(fs.readFileSync("docs/diagnostics.js", "utf8"), context);

assert.strictEqual(window.pybotPersistence.save("memory", "{}", 10), true);
assert.strictEqual(window.pybotPersistence.load("memory"), "{}");
assert.strictEqual(JSON.stringify(window.pybotPersistence.loadJson("memory")), "{}");
assert.strictEqual(window.pybotPersistence.usage("memory"), 2);
assert.strictEqual(window.pybotPersistence.save("memory", "too long", 3), false);
storage.set("broken", "{not-json");
assert.strictEqual(window.pybotPersistence.loadJson("broken"), null);
assert.strictEqual(window.pybotPersistence.load("broken"), null);

window.pybotDiagnostics.mark("runtimeStatus", "ready");
window.pybotDiagnostics.mark("memoryCount", 2);
listeners.error({ error: new Error("test failure") });
const snapshot = window.pybotDiagnostics.snapshot();
assert.strictEqual(snapshot.runtimeStatus, "ready");
assert.strictEqual(snapshot.memoryCount, 2);
assert.strictEqual(snapshot.errors[0].source, "javascript");
assert.match(snapshot.errors[0].stack, /test failure/);
console.log("browser module diagnostics tests passed");
