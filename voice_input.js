/*
 * SACA voice input -- adds a microphone button + language picker next to a text box.
 *
 * Use (one line, after the page's own script):
 *   <script src="/voice.js" data-target="input" data-lang="sw"></script>
 *
 *   data-target   id of the <input>/<textarea> to fill            (required)
 *   data-api      base URL of the SACA API, if the page is served from a different
 *                 server than the API, e.g. "http://localhost:8000"   (default: same server)
 *   data-lang     starting language: "auto" | "en" | "sw"           (default: "auto")
 *   data-max-seconds  longest recording                            (default: 60)
 *
 * Tap once to start, tap again to stop. The transcript is put in the text box for the
 * person to CHECK AND CORRECT -- it is never submitted automatically.
 * Browsers only allow the microphone on https:// pages or http://localhost.
 */
(function () {
  var script = document.currentScript;
  var cfg = {
    target: script && script.dataset.target,
    api: ((script && script.dataset.api) || "").replace(/\/$/, ""),
    lang: (script && script.dataset.lang) || "auto",
    maxSeconds: parseInt((script && script.dataset.maxSeconds) || "60", 10),
  };
  var MIN_MS = 700;

  function init() {
    var field = document.getElementById(cfg.target);
    if (!field) { console.warn("SACA voice: no element with id '" + cfg.target + "'"); return; }

    var supported = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);

    // ---- controls ---------------------------------------------------------
    var wrap = document.createElement("span");
    wrap.className = "saca-voice";
    wrap.style.cssText = "display:inline-flex;align-items:center;gap:6px;flex-wrap:wrap;margin:6px 0;";

    var select = document.createElement("select");
    select.setAttribute("aria-label", "Speaking language");
    [["auto", "Auto"], ["en", "English"], ["sw", "Kiswahili"]].forEach(function (o) {
      var opt = document.createElement("option");
      opt.value = o[0]; opt.textContent = o[1];
      if (o[0] === cfg.lang) opt.selected = true;
      select.appendChild(opt);
    });
    select.style.cssText = "padding:6px;border-radius:6px;border:1px solid #ccc;font-size:14px;";

    var btn = document.createElement("button");
    btn.type = "button";               // never submit the surrounding form
    btn.textContent = "\uD83C\uDFA4 Speak";
    btn.setAttribute("aria-pressed", "false");
    btn.style.cssText = "padding:8px 14px;border:none;border-radius:8px;background:#475569;color:#fff;font-size:14px;cursor:pointer;margin:0;";

    var status = document.createElement("span");
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    status.style.cssText = "font-size:13px;color:#555;";

    wrap.appendChild(select); wrap.appendChild(btn); wrap.appendChild(status);
    field.insertAdjacentElement("afterend", wrap);

    function say(msg, isError) { status.textContent = msg; status.style.color = isError ? "#b91c1c" : "#555"; }

    if (!supported) {
      btn.disabled = true;
      say("Voice input needs a secure (https) page or localhost and a recent browser. Please type instead.", true);
      return;
    }

    // ---- recording --------------------------------------------------------
    var recorder = null, stream = null, chunks = [], startedAt = 0, timer = null;

    function pickMime() {
      var list = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
      for (var i = 0; i < list.length; i++) {
        if (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(list[i])) return list[i];
      }
      return "";
    }
    function extFor(mime) {
      mime = mime || "";
      return mime.indexOf("webm") > -1 ? "webm" : mime.indexOf("ogg") > -1 ? "ogg" : mime.indexOf("mp4") > -1 ? "mp4" : "webm";
    }
    function setRecording(on) {
      btn.textContent = on ? "\u25A0 Stop" : "\uD83C\uDFA4 Speak";
      btn.style.background = on ? "#dc2626" : "#475569";
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      select.disabled = on;
    }
    function releaseMic() {
      if (stream) { stream.getTracks().forEach(function (t) { t.stop(); }); stream = null; }
      if (timer) { clearTimeout(timer); timer = null; }
    }

    async function start() {
      say("");
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch (e) {
        say("Microphone blocked or not found. Allow microphone access, or type instead.", true);
        return;
      }
      var mime = pickMime();
      try {
        recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      } catch (e) {
        releaseMic(); say("This browser cannot record audio. Please type instead.", true); return;
      }
      chunks = [];
      recorder.ondataavailable = function (ev) { if (ev.data && ev.data.size) chunks.push(ev.data); };
      recorder.onstop = onStopped;
      recorder.start();
      startedAt = Date.now();
      setRecording(true);
      say("Listening\u2026 tap Stop when you finish.");
      timer = setTimeout(stop, cfg.maxSeconds * 1000);
    }

    function stop() {
      if (recorder && recorder.state !== "inactive") recorder.stop();
    }

    async function onStopped() {
      var ms = Date.now() - startedAt;
      var mime = recorder.mimeType || pickMime();
      releaseMic();
      setRecording(false);
      if (ms < MIN_MS || !chunks.length) { say("That was too short. Tap Speak and try again.", true); return; }

      var form = new FormData();
      form.append("audio", new Blob(chunks, { type: mime || "audio/webm" }), "voice." + extFor(mime));
      form.append("language", select.value);

      btn.disabled = true;
      say("Turning your voice into text\u2026");
      try {
        var res = await fetch(cfg.api + "/transcribe", { method: "POST", body: form });
        var data = {};
        try { data = await res.json(); } catch (e) {}
        if (!res.ok) { say(data.detail || "Voice input failed. Please type instead.", true); return; }
        var text = (data.text || "").trim();
        if (!text) { say("I could not hear anything. Please try again, closer to the microphone.", true); return; }
        field.value = field.value.trim() ? field.value.trim() + " " + text : text;
        field.dispatchEvent(new Event("input", { bubbles: true }));
        field.focus();
        say("Please check the text above and fix any mistakes before you submit.");
      } catch (e) {
        say("Could not reach the server. Please type instead.", true);
      } finally {
        btn.disabled = false;
      }
    }

    btn.addEventListener("click", function () {
      if (recorder && recorder.state === "recording") stop(); else start();
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();