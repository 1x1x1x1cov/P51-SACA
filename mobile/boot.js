// SACA Android shell: starts Python (Pyodide) in this page, runs the SACA Flask app, and turns links and
// forms into in-page requests. No server and no internet: everything comes from the app's own files.
(function () {
  "use strict";
  var py = null, handle = null, busy = false;
  var DATA = "/data";

  function status(text) {
    var el = document.getElementById("saca-status");
    if (el) el.textContent = text;
  }

  function fail(err) {
    var box = document.getElementById("saca-boot");
    status("SACA could not start. / SACA imeshindwa kuanza.");
    if (box) {
      var pre = document.createElement("pre");
      pre.textContent = String(err && (err.stack || err.message) || err);
      box.appendChild(pre);
    }
    console.error(err);
  }

  function syncfs(populate) {
    return new Promise(function (resolve) {
      py.FS.syncfs(populate, function (err) {
        if (err) console.warn("syncfs", err);
        resolve();
      });
    });
  }

  // ------------------------------------------------------------------ rendering
  function stopSpeech() {
    try { if (window.SACAAndroid) window.SACAAndroid.stop(); } catch (e) { /* ignore */ }
    try { if (window.speechSynthesis) window.speechSynthesis.cancel(); } catch (e) { /* ignore */ }
  }

  function scriptText(src) {
    // Scripts the app serves itself (e.g. /voice.js) come from Flask, not from a file.
    if (!src || /^(https?:)?\/\//.test(src) || src.indexOf("pyodide/") === 0) return null;
    try {
      var p = handle("GET", src, "", ""), r = p.toJs(); p.destroy();
      return r[0] === 200 ? r[3] : "";
    } catch (e) { return ""; }
  }

  function activateScripts(root) {
    var olds = Array.prototype.slice.call(root.querySelectorAll("script"));
    olds.forEach(function (old) {
      var s = document.createElement("script");
      Array.prototype.forEach.call(old.attributes, function (a) { if (a.name !== "src") s.setAttribute(a.name, a.value); });
      var src = old.getAttribute("src");
      if (src) {
        var inline = scriptText(src);
        if (inline === null) { s.src = src; } else { s.textContent = inline; }
      } else {
        s.textContent = old.textContent;
      }
      old.parentNode.replaceChild(s, old);  // runs it here, so document.currentScript works
    });
  }

  function render(html) {
    stopSpeech();
    var doc = new DOMParser().parseFromString(html, "text/html");
    var lang = doc.documentElement.getAttribute("lang");
    if (lang) document.documentElement.setAttribute("lang", lang);
    document.title = doc.title || "SACA";
    var head = document.head;
    while (head.firstChild) head.removeChild(head.firstChild);
    Array.prototype.forEach.call(doc.head.childNodes, function (n) { head.appendChild(document.importNode(n, true)); });
    var body = document.importNode(doc.body, true);
    document.documentElement.replaceChild(body, document.body);
    activateScripts(document.head);
    activateScripts(document.body);
    window.scrollTo(0, 0);
  }

  function showBusy(on) {
    var el = document.getElementById("saca-busy");
    if (on && !el) {
      el = document.createElement("div");
      el.id = "saca-busy";
      el.setAttribute("role", "status");
      el.style.cssText = "position:fixed;left:0;right:0;top:0;height:4px;z-index:99999;background:linear-gradient(90deg,#0f766e 0,#5eead4 50%,#0f766e 100%);background-size:200% 100%;animation:sacabusy 1s linear infinite";
      var st = document.createElement("style");
      st.textContent = "@keyframes sacabusy{from{background-position:200% 0}to{background-position:0 0}}";
      el.appendChild(st);
      (document.body || document.documentElement).appendChild(el);
    } else if (!on && el) {
      el.parentNode.removeChild(el);
    }
  }

  function navigate(method, url, body, contentType, push) {
    if (busy) return;
    busy = true;
    showBusy(true);
    // Let the progress bar paint before Python runs (signing in hashes the PIN and can take a second or two).
    setTimeout(function () { doNavigate(method, url, body, contentType, push); }, 30);
  }

  function doNavigate(method, url, body, contentType, push) {
    try {
      var p = handle(method, url, body || "", contentType || ""), r = p.toJs(); p.destroy();
      var code = r[0], finalUrl = r[1], mime = r[2], text = r[3];
      if (mime === "text/html" || text) {
        render(text || ("<p>Error " + code + "</p>"));
      }
      var state = { url: finalUrl };
      if (push) history.pushState(state, "", "#" + finalUrl);
      else history.replaceState(state, "", "#" + finalUrl);
      if (method === "POST") syncfs(false);
    } catch (e) {
      fail(e);
    } finally {
      busy = false;
      showBusy(false);
    }
  }

  // ------------------------------------------------------------------ links and forms
  function appUrl(href) {
    if (!href) return null;
    if (/^(tel|mailto|sms|geo|intent):/i.test(href)) return null;   // let Android handle these
    if (/^https?:\/\//i.test(href) || href.indexOf("//") === 0) return null; // external: Android opens a browser
    if (href.charAt(0) === "#") return null;
    if (href.charAt(0) !== "/") {
      var cur = (history.state && history.state.url) || "/";
      href = new URL(href, "http://saca.local" + cur).pathname + new URL(href, "http://saca.local" + cur).search;
    }
    return href;
  }

  document.addEventListener("click", function (e) {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey) return;
    var a = e.target.closest && e.target.closest("a[href]");
    if (!a || a.target === "_blank" || a.hasAttribute("download")) return;
    var url = appUrl(a.getAttribute("href"));
    if (url === null) return;
    e.preventDefault();
    navigate("GET", url, "", "", true);
  });

  document.addEventListener("submit", function (e) {
    if (e.defaultPrevented) return;  // the page's own checks blocked it
    var form = e.target;
    e.preventDefault();
    var fd;
    try { fd = new FormData(form, e.submitter && !e.submitter.disabled ? e.submitter : undefined); }
    catch (err) { fd = new FormData(form); }
    var params = new URLSearchParams();
    fd.forEach(function (v, k) { if (typeof v === "string") params.append(k, v); });
    var method = (form.getAttribute("method") || "GET").toUpperCase();
    var action = appUrl(form.getAttribute("action") || ((history.state && history.state.url) || "/").split("?")[0]) || "/";
    if (method === "GET") {
      var q = params.toString();
      navigate("GET", action.split("?")[0] + (q ? "?" + q : ""), "", "", true);
    } else {
      navigate("POST", action, params.toString(), "application/x-www-form-urlencoded", true);
    }
  });

  window.addEventListener("popstate", function (e) {
    var url = (e.state && e.state.url) || (location.hash ? location.hash.slice(1) : "/");
    navigate("GET", url, "", "", false);
  });

  // Called by MainActivity when the phone's text-to-speech finishes.
  window.__sacaSpeechDoneBridge = function () {
    if (typeof window.__sacaSpeechDone === "function") window.__sacaSpeechDone();
  };

  // ------------------------------------------------------------------ start
  async function boot() {
    status("Starting Python... / Inaanza...");
    py = await loadPyodide({ indexURL: "pyodide/" });
    py.FS.mkdirTree(DATA);
    py.FS.mount(py.FS.filesystems.IDBFS, {}, DATA);
    await syncfs(true);
    status("Loading SACA... / Inapakia SACA...");
    var zip = await (await fetch("app.zip")).arrayBuffer();
    py.unpackArchive(zip, "zip", { extractDir: "/app" });
    py.runPython("import sys; sys.path.insert(0, '/app'); import mobile_main");
    handle = py.globals.get("mobile_main").handle;
    await syncfs(false);  // keeps the secret key and the new database
    var start = location.hash ? location.hash.slice(1) : "/";
    navigate("GET", start, "", "", false);
  }

  boot().catch(fail);
})();
