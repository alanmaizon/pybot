/* Browser-local persistence only. This module never sends memory over the network. */
(function (root) {
  function load(key) {
    try {
      return root.localStorage.getItem(key);
    } catch (error) {
      return null;
    }
  }

  function save(key, value, maxBytes) {
    if (value.length > maxBytes) return false;
    try {
      root.localStorage.setItem(key, value);
      return true;
    } catch (error) {
      return false;
    }
  }

  function remove(key) {
    try {
      root.localStorage.removeItem(key);
    } catch (error) {
      // Private browsing and disabled storage are expected to fail safely.
    }
  }

  function usage(key) {
    const value = load(key);
    return value ? value.length : 0;
  }

  function loadJson(key) {
    const value = load(key);
    if (!value) return null;
    try {
      return JSON.parse(value);
    } catch (error) {
      remove(key);
      return null;
    }
  }

  root.pybotPersistence = { load, loadJson, save, remove, usage };
})(window);
