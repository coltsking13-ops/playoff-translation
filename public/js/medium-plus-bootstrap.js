(function () {
  const KEY = "ptl_medium_plus_mode";
  const MEDIUM_URL = "./public/data/data-package.medium-plus.json";

  function on() {
    return localStorage.getItem(KEY) === "on";
  }

  function shouldRedirect(url) {
    url = String(url || "");
    return on()
      && !url.includes("data-package.medium-plus.json")
      && (
        url.includes("data-package.embedded.json") ||
        url.endsWith("data-package.json") ||
        url.includes("/data-package.json")
      );
  }

  const nativeFetch = window.fetch;
  if (nativeFetch) {
    window.fetch = function (input, init) {
      const url = typeof input === "string" ? input : input && input.url;
      if (shouldRedirect(url)) {
        console.log("Medium+ mode redirected data package:", url, "->", MEDIUM_URL);
        return nativeFetch.call(this, MEDIUM_URL + "?v=" + Date.now(), init);
      }
      return nativeFetch.call(this, input, init);
    };
  }

  const nativeOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    if (shouldRedirect(url)) {
      console.log("Medium+ mode redirected XHR:", url, "->", MEDIUM_URL);
      return nativeOpen.call(this, method, MEDIUM_URL + "?v=" + Date.now(), ...rest);
    }
    return nativeOpen.call(this, method, url, ...rest);
  };

  window.PTL_DATASET_MODE = on() ? "medium-plus" : "base";
})();
