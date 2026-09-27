/* =========================================================
   নিরীক্ষা সহায়ক — চ্যাট স্তর
   এজেন্ট এই কম্পিউটারেই চলে; কোনো তথ্য বাহিরে যায় না।
   ========================================================= */
(function () {
  "use strict";

  var SESSION = "ui-" + (Date.now() % 1000000);
  var busy = false;

  function $(id) { return document.getElementById(id); }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  /* ছোট markdown — **গাঢ়**, _তির্যক_, • ও ক্রমিক অপরিবর্তিত */
  function md(s) {
    return esc(s)
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/_([^_\n]+)_/g, "<em>$1</em>");
  }

  function bubble(cls, html) {
    var log = $("chat-log");
    var d = document.createElement("div");
    d.className = "chat-msg " + cls;
    d.innerHTML = html;
    log.appendChild(d);
    log.scrollTop = log.scrollHeight;
    return d;
  }

  function chips(list) {
    var box = $("chat-chips");
    box.innerHTML = "";
    (list || []).forEach(function (t) {
      var b = document.createElement("button");
      b.className = "chat-chip";
      b.textContent = t;
      b.onclick = function () { $("chat-q").value = t; send(); };
      box.appendChild(b);
    });
  }

  async function post(path, body) {
    var r = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {})
    });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }

  /* ---- নিরীক্ষার ধরন সার্ভারে জানানো ---- */
  async function syncProfile() {
    try {
      await post("/api/agent/profile", {
        session_id: SESSION,
        entity_type: $("chat-entity").value,
        company: $("chat-company").value.trim() || "নিরীক্ষাধীন প্রতিষ্ঠান"
      });
    } catch (e) { /* নীরব — চ্যাট তবু চলিবে */ }
  }

  /* ---- প্রশ্ন পাঠানো ---- */
  async function send() {
    if (busy) return;
    var q = $("chat-q").value.trim();
    if (!q) return;

    $("chat-q").value = "";
    bubble("me", esc(q));
    chips([]);
    busy = true;
    var wait = bubble("sys", "ভাবিতেছি…");

    try {
      await syncProfile();
      var res = await post("/api/agent/ask", { question: q, session_id: SESSION });
      wait.remove();
      bubble("bot", md(res.answer || res.text || "উত্তর পাওয়া যায় নাই।"));
      chips(res.next_actions || []);
      if (res.source && res.source !== "rules") {
        bubble("sys", "উৎস: " + esc(res.source) + (res.model ? " / " + esc(res.model) : ""));
      }
    } catch (e) {
      wait.remove();
      bubble("bot", "দুঃখিত, সার্ভারের সহিত সংযোগে সমস্যা হইয়াছে। " +
                    "সার্ভারটি চালু আছে কিনা দেখুন।<br><em>" + esc(e.message) + "</em>");
    } finally {
      busy = false;
      $("chat-q").focus();
    }
  }

  /* ---- নথি নামানো ---- */
  async function download(path, filename) {
    var note = $("font-note");
    note.textContent = "নথি তৈরি হইতেছে…";
    try {
      var r = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: SESSION, font: $("chat-font").value })
      });
      if (!r.ok) throw new Error("HTTP " + r.status);
      var blob = await r.blob();
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url; a.download = filename;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 4000);
      note.textContent = "নামানো হইয়াছে।";
    } catch (e) {
      note.textContent = "নথি তৈরি হয় নাই: " + e.message;
    }
  }

  function fontHint() {
    var f = $("chat-font").value;
    $("font-note").textContent = (f === "sutonnymj")
      ? "SutonnyMJ ইউনিকোড নহে — লেখা রূপান্তরিত হইয়া বসিবে। ফন্টটি "
        + "কম্পিউটারে ইনস্টল থাকা চাই।"
      : "ইউনিকোড — যেকোনো কম্পিউটারে খোলা যাইবে।";
  }

  /* ---- স্তরের অবস্থা ---- */
  async function refreshTier() {
    try {
      var r = await fetch("/api/agent/status?session_id=" + encodeURIComponent(SESSION));
      var j = await r.json();
      var local = ((j.agent || {})["স্থানীয় মডেল"] || {})["অবস্থা"];
      var el = $("chat-tier");
      if (local === "চালু") {
        el.textContent = "স্তর: নিয়ম + স্থানীয় মডেল";
        el.className = "badge badge-ok";
      } else {
        el.textContent = "স্তর: নিয়ম-ভিত্তিক (অফলাইন)";
        el.className = "badge badge-muted";
      }
    } catch (e) {
      $("chat-tier").textContent = "স্তর: —";
    }
  }

  /* ---- সূচনা ---- */
  function greet() {
    $("chat-log").innerHTML = "";
    bubble("bot", md(
      "আসসালামু আলাইকুম। আমি আপনার **নিরীক্ষা সহায়ক**।\n\n" +
      "আপনি যেভাবে বলবেন সেভাবেই কাজ করব — ছোট একটি অংশ যাচাই করতে বললে " +
      "সেটুকুই করব, আবার সম্পূর্ণ নিরীক্ষা করতে বললে শুরু থেকে শেষ পর্যন্ত " +
      "করে প্রতিবেদনের খসড়া পর্যন্ত দিব।\n\n" +
      "উপরে প্রতিষ্ঠানের শ্রেণিটি বাছিয়া লউন — তাহাতে কেবল প্রাসঙ্গিক " +
      "অংশটুকুই দেখাইব।"
    ));
    chips([
      "কী কী দলিল লাগবে",
      "রেজিস্টার নাই, কী করব",
      "সম্পূর্ণ নিরীক্ষা কর",
      "তুমি কী কী করতে পারো",
      "প্রতিবেদনের অনুচ্ছেদক্রম দাও"
    ]);
  }

  function init() {
    if (!$("chat-send")) return;

    $("chat-send").onclick = send;
    $("chat-q").addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
    });
    $("chat-entity").onchange = function () {
      syncProfile();
      bubble("sys", "শ্রেণি নির্ধারিত: " +
        $("chat-entity").options[$("chat-entity").selectedIndex].text);
    };
    $("btn-docx").onclick = function () {
      download("/api/report/docx", "নিরীক্ষা-প্রতিবেদন.docx");
    };
    $("btn-proof").onclick = function () {
      download("/api/report/font-proof", "ফন্ট-যাচাই.docx");
    };
    $("chat-font").onchange = fontHint;
    fontHint();

    $("chat-reset").onclick = async function () {
      try { await post("/api/agent/reset", { session_id: SESSION }); } catch (e) {}
      greet();
    };

    /* ট্যাব বদল */
    var navs = [
      ["nav-file", "view-file"], ["nav-manual", "view-manual"], ["nav-chat", "view-chat"]
    ];
    $("nav-chat").addEventListener("click", function () {
      navs.forEach(function (p) {
        var btn = $(p[0]), view = $(p[1]);
        if (!btn || !view) return;
        var on = p[0] === "nav-chat";
        view.classList.toggle("hidden", !on);
        btn.className = "btn btn-sm " + (on ? "btn-primary" : "btn-ghost");
      });
      refreshTier();
      $("chat-q").focus();
    });
    ["nav-file", "nav-manual"].forEach(function (id) {
      var b = $(id);
      if (b) b.addEventListener("click", function () {
        $("view-chat").classList.add("hidden");
        $("nav-chat").className = "btn btn-ghost btn-sm";
      });
    });

    greet();
    refreshTier();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else { init(); }
})();
