/* ============================================================================
   annotate.js — session-free page annotations (content-kit)

   Loaded by lib.js only when the serving engine answers /__annotations/ping.
     reads   GET  <page>.annotations.json           a static sidecar, committed
     writes  POST /__annotations  {op, page, …}    the engine writes the sidecar

   Nothing here needs a session. The human annotates whenever; the file is the
   channel; any agent later runs `ckit annotations list` and the /address skill.
   Quotes are anchored by text (W3C TextQuoteSelector), never by CSS path, so an
   edited page keeps its notes and a rewritten passage is reported stale by the gate.

   Two kinds of thread meet here. A reader's QUESTION opens and waits: whoever
   acts on the page replies and keeps, addresses or declines it. An agent's FLAG
   rests as `noted`: a disclosure that a passage was written beyond the source,
   asking nothing until the reader keeps it or asks for a change. Both sides act
   from this panel; the CLI is never required. `#ann=<id>` in the URL opens the
   panel on that thread (the home page and the review page link this way).
   ========================================================================== */

(function () {
  "use strict";

  var main = document.querySelector("main");
  if (!main || document.body.dataset.hbAnnotate === "on") return;
  document.body.dataset.hbAnnotate = "on";

  var PAGE = location.pathname.replace(/index\.html$/, "");
  var SIDECAR = PAGE.slice(-1) === "/"
    ? PAGE + "index.annotations.json"
    : PAGE.replace(/\.html$/, ".annotations.json");
  var CONTEXT = 32;
  var CLIP = 160;

  var state = { on: false, threads: [], stale: {}, focus: null, scrollTo: null, pending: "", expanded: {} };

  var css = document.createElement("link");
  css.rel = "stylesheet";
  css.href = window.hbUrl ? window.hbUrl("/shell/annotate.css") : "/shell/annotate.css";
  document.head.appendChild(css);

  var toggle = el("button", "hb-ann-toggle hb-ann-ui", "✎ Annotate");
  toggle.type = "button";
  toggle.title = "Mark up this page; an agent picks the notes up later";
  document.body.appendChild(toggle);

  var panel = el("aside", "hb-ann-panel hb-ann-ui");
  panel.hidden = true;
  panel.setAttribute("aria-label", "Annotations");
  document.body.appendChild(panel);

  var bubble = el("button", "hb-ann-bubble hb-ann-ui", "＋ Comment on selection");
  bubble.type = "button";
  bubble.hidden = true;
  document.body.appendChild(bubble);

  /* ------------------------------------------------------------------ helpers */
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function esc(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function norm(s) { return String(s).replace(/\s+/g, " ").trim(); }
  function reEsc(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }
  function me() { return localStorage.getItem("ckit.author") || ""; }
  function author() {
    var a = me();
    if (!a) {
      a = window.prompt("Your name for annotations (kept in this browser):", "") || "";
      a = a.trim();
      if (a) localStorage.setItem("ckit.author", a);
    }
    return a;
  }
  function kindOf(t) { return t.kind || "question"; }
  function isLive(t) { return t.state === "open" || t.state === "noted"; }
  function post(req) {
    return fetch("/__annotations", {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req)
    }).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok || !j.ok) throw new Error(j.error || ("HTTP " + r.status));
        return j;
      });
    });
  }
  function hashThread() {
    var m = /(?:^#|[#&])ann=([^&]+)/.exec(location.hash);
    return m ? decodeURIComponent(m[1]) : null;
  }

  /* ----------------------------------------------------- the page's text model
     The same model the engine uses: text nodes under <main>, minus script/style and
     our own chrome, concatenated. Quotes are located whitespace-flexibly. */
  function textNodes() {
    var out = [];
    var walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        for (var p = n.parentNode; p && p !== main; p = p.parentNode) {
          var t = p.nodeName;
          if (t === "SCRIPT" || t === "STYLE" || t === "NOSCRIPT" || t === "TEMPLATE") return NodeFilter.FILTER_REJECT;
          if (p.classList && p.classList.contains("hb-ann-ui")) return NodeFilter.FILTER_REJECT;
        }
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var n;
    while ((n = walker.nextNode())) out.push(n);
    return out;
  }
  function model() {
    var full = "", spans = [];
    textNodes().forEach(function (n) {
      spans.push({ node: n, start: full.length, end: full.length + n.nodeValue.length });
      full += n.nodeValue;
    });
    return { full: full, spans: spans };
  }
  function find(m, exact) {
    var q = norm(exact);
    if (!q) return null;
    var re = new RegExp(q.split(" ").map(reEsc).join("\\s+"));
    var hit = re.exec(m.full);
    return hit ? [hit.index, hit.index + hit[0].length] : null;
  }
  function context(m, se) {
    return {
      prefix: norm(m.full.slice(Math.max(0, se[0] - CONTEXT * 3), se[0])).slice(-CONTEXT),
      suffix: norm(m.full.slice(se[1], se[1] + CONTEXT * 3)).slice(0, CONTEXT)
    };
  }
  function markQuote(m, se, id, cls) {
    var s = se[0], e = se[1];
    m.spans.forEach(function (sp) {
      if (sp.start >= e || sp.end <= s) return;
      var ls = Math.max(s, sp.start) - sp.start;
      var le = Math.min(e, sp.end) - sp.start;
      if (le <= ls) return;
      var mid = sp.node.splitText(ls);
      mid.splitText(le - ls);
      var mk = el("mark", "hb-ann " + cls);
      mk.dataset.id = id;
      mid.parentNode.insertBefore(mk, mid);
      mk.appendChild(mid);
      mk.addEventListener("click", function (ev) { ev.preventDefault(); focusThread(id, true); });
    });
  }
  function clearMarks() {
    main.querySelectorAll("mark.hb-ann").forEach(function (mk) {
      var p = mk.parentNode;
      while (mk.firstChild) p.insertBefore(mk.firstChild, mk);
      p.removeChild(mk);
    });
    main.normalize();
  }

  /* --------------------------------------------------------------- lifecycle */
  toggle.addEventListener("click", function () { setOn(!state.on); });
  function setOn(on) {
    state.on = on;
    document.body.classList.toggle("hb-ann-on", on);
    toggle.classList.toggle("on", on);
    panel.hidden = !on;
    bubble.hidden = true;
    if (on) load(); else clearMarks();
  }
  function load() {
    fetch(SIDECAR, { credentials: "same-origin", cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : { threads: [] }; })
      .catch(function () { return { threads: [] }; })
      .then(function (d) { state.threads = d.threads || []; render(); });
  }
  function openOn(id) {  // a deep link: the panel on, this thread in view
    if (!id) return;
    state.focus = id;
    state.scrollTo = id;
    if (state.on) render(); else setOn(true);
  }
  openOn(hashThread());
  window.addEventListener("hashchange", function () { openOn(hashThread()); });

  /* ------------------------------------------------------------- selection */
  var bubbleTimer = null;
  document.addEventListener("selectionchange", function () {
    if (!state.on) return;
    clearTimeout(bubbleTimer);
    bubbleTimer = setTimeout(placeBubble, 160);
  });
  function placeBubble() {
    var sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount || !main.contains(sel.anchorNode) || !main.contains(sel.focusNode)) {
      bubble.hidden = true; return;
    }
    var text = norm(sel.toString());
    if (!text) { bubble.hidden = true; return; }
    var rect = sel.getRangeAt(0).getBoundingClientRect();
    bubble.style.top = (window.scrollY + rect.bottom + 6) + "px";
    bubble.style.left = (window.scrollX + Math.max(8, rect.left)) + "px";
    bubble.hidden = false;
    state.pending = text;
  }
  bubble.addEventListener("mousedown", function (e) { e.preventDefault(); });
  bubble.addEventListener("click", function () {
    var q = state.pending;
    bubble.hidden = true;
    if (q) compose(q);
  });

  /* ------------------------------------------------- composer: a new question */
  function compose(quote) {
    var m = model();
    var se = quote ? find(m, quote) : null;
    if (quote && !se) { alert("Could not locate that selection in the page text."); return; }
    var ctx = se ? context(m, se) : null;
    var form = el("div", "hb-ann-form hb-ann-ui");
    form.innerHTML =
      (quote ? '<div class="hb-ann-quote">' + esc(quote.length > CLIP ? quote.slice(0, CLIP) + "…" : quote) + "</div>"
             : '<div class="hb-ann-meta">Page-level note</div>') +
      '<textarea placeholder="What should change, and why?"></textarea>' +
      '<div class="hb-ann-err" hidden></div>' +
      '<div class="hb-ann-actions"><button type="button" class="hb-ann-btn primary" data-act="save">Save</button>' +
      '<button type="button" class="hb-ann-btn" data-act="cancel">Cancel</button></div>';
    var slot = panel.querySelector("[data-composer]");
    slot.innerHTML = "";
    slot.appendChild(form);
    var ta = form.querySelector("textarea");
    ta.focus();
    form.addEventListener("click", function (e) {
      var b = e.target.closest("[data-act]");
      if (!b) return;
      if (b.dataset.act === "cancel") { slot.innerHTML = ""; return; }
      var body = ta.value.trim();
      var err = form.querySelector(".hb-ann-err");
      if (!body) { err.textContent = "Say something first."; err.hidden = false; return; }
      var who = author();
      if (!who) { err.textContent = "A name is needed so the thread has an author."; err.hidden = false; return; }
      b.disabled = true;
      post({ op: "add", page: PAGE, author: who, body: body,
             target: quote ? { type: "TextQuoteSelector", exact: quote, prefix: ctx.prefix, suffix: ctx.suffix } : null })
        .then(function () { slot.innerHTML = ""; load(); })
        .catch(function (ex) { err.textContent = ex.message; err.hidden = false; b.disabled = false; });
    });
    ta.addEventListener("keydown", function (e) { if (e.key === "Escape") slot.innerHTML = ""; });
  }

  /* ------------------------------------------ a reply, a change request, a decline
     One inline form under the thread. `mode` says what saving means:
       reply    — a reply in the thread, state unchanged
       change   — the reader asks for a change: the thread becomes (or stays) open, waiting
       decline  — whoever acts on the page declines, with the reason the gate requires */
  var PROMPTS = {
    reply: "Reply in this thread.",
    change: "What should change, and why? The thread opens and waits for the agent.",
    decline: "Why not? A declined thread needs its reason."
  };
  function replyForm(item, t, mode) {
    var old = item.querySelector(".hb-ann-form");
    if (old) old.remove();
    var form = el("div", "hb-ann-form inline hb-ann-ui");
    form.innerHTML =
      '<textarea placeholder="' + esc(PROMPTS[mode]) + '"></textarea>' +
      '<div class="hb-ann-err" hidden></div>' +
      '<div class="hb-ann-actions"><button type="button" class="hb-ann-btn primary" data-act="save">' +
      (mode === "decline" ? "Decline" : mode === "change" ? "Ask for the change" : "Reply") + "</button>" +
      '<button type="button" class="hb-ann-btn" data-act="cancel">Cancel</button></div>';
    item.querySelector(".hb-ann-actions").insertAdjacentElement("beforebegin", form);
    var ta = form.querySelector("textarea");
    ta.focus();
    form.addEventListener("click", function (e) {
      var b = e.target.closest("[data-act]");
      if (!b) return;
      if (b.dataset.act === "cancel") { form.remove(); return; }
      var body = ta.value.trim();
      var err = form.querySelector(".hb-ann-err");
      if (!body) { err.textContent = mode === "reply" ? "Say something first." : "Say why."; err.hidden = false; return; }
      var who = author();
      if (!who) { err.textContent = "A name is needed so the reply has an author."; err.hidden = false; return; }
      b.disabled = true;
      var req = { op: "reply", page: PAGE, id: t.id, author: who, body: body };
      if (mode === "decline") req.state = "declined";
      if (mode === "change") req.state = "open";
      post(req).then(load).catch(function (ex) { err.textContent = ex.message; err.hidden = false; b.disabled = false; });
    });
    ta.addEventListener("keydown", function (e) { if (e.key === "Escape") form.remove(); });
  }

  /* ------------------------------------------------------------------ render */
  function chips(t, stale) {
    var out = '<span class="hb-ann-chip ' + esc(t.state) + '">' + esc(t.state) + "</span>";
    if (kindOf(t) === "flag") out += '<span class="hb-ann-chip flag" title="An agent wrote this passage beyond its source">flag</span>';
    if (t.label) out += '<span class="hb-ann-chip label">' + esc(t.label) + "</span>";
    if (stale) out += '<span class="hb-ann-chip stale" title="The quoted passage is no longer on the page">stale anchor</span>';
    return out;
  }
  function actions(t) {
    var mine = me() && t.author === me();
    var b = [];
    if (t.state === "open") {
      b.push('<button type="button" class="hb-ann-btn" data-form="reply" data-id="' + esc(t.id) + '">Reply</button>');
      b.push('<button type="button" class="hb-ann-btn primary" data-keep="' + esc(t.id) + '" title="Close the thread as accepted">Keep</button>');
      b.push('<button type="button" class="hb-ann-btn" data-form="decline" data-id="' + esc(t.id) + '">Decline</button>');
    } else if (t.state === "noted") {
      b.push('<button type="button" class="hb-ann-btn primary" data-keep="' + esc(t.id) + '" title="Accept the passage as written">Keep</button>');
      b.push('<button type="button" class="hb-ann-btn" data-form="change" data-id="' + esc(t.id) + '">Ask for a change</button>');
    } else {
      b.push('<button type="button" class="hb-ann-btn" data-state="open" data-id="' + esc(t.id) + '">Reopen</button>');
    }
    if (isLive(t) && mine) {
      b.push('<button type="button" class="hb-ann-btn" data-state="withdrawn" data-id="' + esc(t.id) + '">Withdraw</button>');
    }
    return b.join("");
  }
  function bodyHtml(t) {
    var collapsed = t.state === "noted" && t.body.length > CLIP && !state.expanded[t.id];
    if (!collapsed) return '<div class="hb-ann-body">' + esc(t.body) + "</div>";
    return '<div class="hb-ann-body">' + esc(t.body.slice(0, CLIP)) + '… <button type="button" class="hb-ann-more" data-more="' +
      esc(t.id) + '">more</button></div>';
  }
  function render() {
    clearMarks();
    state.stale = {};
    var open = 0, noted = 0;
    state.threads.forEach(function (t) {
      if (t.state === "open") open++;
      if (t.state === "noted") noted++;
      if (t.target && t.state !== "withdrawn") {
        var m = model();
        var se = find(m, t.target.exact);
        if (se) markQuote(m, se, t.id, "hb-ann-" + t.state);
        else state.stale[t.id] = true;
      }
    });

    var html = [
      '<div class="hb-ann-head"><b>Annotations</b>',
      '<span><button type="button" class="hb-ann-btn primary" data-act="note">＋ Page note</button> ',
      '<button type="button" class="hb-ann-btn" data-act="close">Close</button></span>',
      '<div class="hb-ann-meta">' + open + " waiting · " + noted + " noted · " + state.threads.length +
        " total · select prose to comment on it</div></div>",
      '<div data-composer></div>'
    ];
    if (!state.threads.length) {
      html.push('<div class="hb-ann-empty">No annotations yet. Select some prose, or add a page note.</div>');
    }
    state.threads.slice().reverse().forEach(function (t) {
      var stale = state.stale[t.id];
      html.push('<div class="hb-ann-item hb-ann-' + esc(t.state) + (kindOf(t) === "flag" ? " hb-ann-flag" : "") +
        '" data-id="' + esc(t.id) + '">');
      html.push('<div class="hb-ann-top">' + chips(t, stale) +
        '<span class="hb-ann-meta">' + esc(t.author) + " · " + esc(String(t.created || "").slice(0, 10)) + "</span></div>");
      if (t.target) {
        var q = t.target.exact || "";
        html.push('<div class="hb-ann-quote" data-goto="' + esc(t.id) + '" title="Jump to the passage">' +
          esc(q.length > 140 ? q.slice(0, 140) + "…" : q) + "</div>");
      }
      html.push(bodyHtml(t));
      (t.replies || []).forEach(function (r) {
        html.push('<div class="hb-ann-reply"><span class="hb-ann-meta">' + esc(r.author || "") + " · " +
          esc(String(r.created || "").slice(0, 10)) + (r.state ? " → " + esc(r.state) : "") + "</span>" +
          '<div class="hb-ann-body">' + esc(r.body || "") + "</div></div>");
      });
      html.push('<div class="hb-ann-actions">' + actions(t) + "</div></div>");
    });
    panel.innerHTML = html.join("");
    if (state.scrollTo) { var id = state.scrollTo; state.scrollTo = null; focusThread(id, true); }
    else if (state.focus) focusThread(state.focus, false);
  }

  panel.addEventListener("click", function (e) {
    var act = e.target.closest("[data-act]");
    if (act) {
      if (act.dataset.act === "close") setOn(false);
      if (act.dataset.act === "note") compose(null);
      return;
    }
    var go = e.target.closest("[data-goto]");
    if (go) { focusThread(go.dataset.goto, true); return; }
    var more = e.target.closest("[data-more]");
    if (more) { state.expanded[more.dataset.more] = true; state.focus = more.dataset.more; render(); return; }
    var fm = e.target.closest("[data-form]");
    if (fm) {
      var item = fm.closest(".hb-ann-item");
      var t = state.threads.filter(function (x) { return x.id === fm.dataset.id; })[0];
      if (item && t) { state.focus = t.id; replyForm(item, t, fm.dataset.form); }
      return;
    }
    var keep = e.target.closest("[data-keep]");
    if (keep) {
      var who = author();
      if (!who) return;
      keep.disabled = true;
      post({ op: "reply", page: PAGE, id: keep.dataset.keep, author: who, body: "Kept.", state: "addressed" })
        .then(load)
        .catch(function (ex) { alert(ex.message); keep.disabled = false; });
      return;
    }
    var st = e.target.closest("[data-state]");
    if (st) {
      var name = author();
      if (!name) return;
      st.disabled = true;
      post({ op: "state", page: PAGE, id: st.dataset.id, state: st.dataset.state, author: name })
        .then(load)
        .catch(function (ex) { alert(ex.message); st.disabled = false; });
    }
  });

  function focusThread(id, scroll) {
    state.focus = id;
    panel.querySelectorAll(".hb-ann-item.focus").forEach(function (x) { x.classList.remove("focus"); });
    main.querySelectorAll("mark.hb-ann.focus").forEach(function (x) { x.classList.remove("focus"); });
    var item = panel.querySelector('.hb-ann-item[data-id="' + id + '"]');
    var mk = main.querySelector('mark.hb-ann[data-id="' + id + '"]');
    if (item) item.classList.add("focus");
    if (mk) mk.classList.add("focus");
    if (scroll) {
      if (mk) mk.scrollIntoView({ block: "center", behavior: "smooth" });
      if (item) item.scrollIntoView({ block: "nearest" });
    }
  }

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && state.on && !panel.querySelector(".hb-ann-form textarea")) setOn(false);
  });
})();
