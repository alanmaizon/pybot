/* Optional, local-only runtime diagnostics. Personal message contents are never recorded. */
(function (root) {
  const startedAt = performance.now();
  const state = {
    runtimeStatus: "not started",
    loadedModules: [],
    contextTurns: 0,
    contextBytes: 0,
    memoryCount: 0,
    retrievedMemories: [],
    retrievalMs: 0,
    responseMs: 0,
    errors: [],
    networkRequests: [],
    storageBytes: 0,
    persistenceStatus: "unknown",
  };

  function errorDetails(error, source) {
    return {
      source,
      message: String(error && error.message || error),
      stack: String(error && error.stack || ""),
      at: new Date().toISOString(),
    };
  }

  function recordError(error, source) {
    state.errors.push(errorDetails(error, source));
    if (state.errors.length > 20) state.errors.shift();
  }

  function mark(name, value) {
    state[name] = value;
  }

  function snapshot() {
    return {
      uptimeMs: Math.round(performance.now() - startedAt),
      runtimeStatus: state.runtimeStatus,
      loadedModules: [...state.loadedModules],
      contextTurns: state.contextTurns,
      contextBytes: state.contextBytes,
      memoryCount: state.memoryCount,
      retrievedMemories: state.retrievedMemories.map((item) => ({ ...item })),
      retrievalMs: state.retrievalMs,
      responseMs: state.responseMs,
      errors: state.errors.map((item) => ({ ...item })),
      networkRequests: state.networkRequests.map((item) => ({ ...item })),
      storageBytes: state.storageBytes,
      persistenceStatus: state.persistenceStatus,
    };
  }

  const originalFetch = root.fetch.bind(root);
  root.fetch = async (...args) => {
    const requestStarted = performance.now();
    const request = {
      url: String(args[0] && args[0].url || args[0]),
      startedAt: new Date().toISOString(),
    };
    try {
      const response = await originalFetch(...args);
      request.status = response.status;
      request.ok = response.ok;
      return response;
    } catch (error) {
      request.error = String(error && error.message || error);
      recordError(error, "network");
      throw error;
    } finally {
      request.durationMs = Math.round(performance.now() - requestStarted);
      state.networkRequests.push(request);
    }
  };

  root.addEventListener("error", (event) => recordError(event.error || event.message, "javascript"));
  root.addEventListener("unhandledrejection",
    (event) => recordError(event.reason, "promise"));

  root.pybotDiagnostics = { mark, recordError, snapshot };
})(window);
