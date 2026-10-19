/*
 * Docs chatbot widget. Paste one tag on any page:
 *
 *   <script src="https://YOUR-SERVER/widget.js" data-title="Ask us" data-color="#8a4b2a" defer></script>
 *
 * It talks to the server it was loaded from. Styles live in a shadow root,
 * so they don't clash with the host site's CSS.
 */
(function () {
  var script = document.currentScript;
  if (!script || window.__docsChatbotLoaded) return;
  window.__docsChatbotLoaded = true;

  var api = new URL(script.src).origin;
  var title = script.dataset.title || "Ask us";
  var color = script.dataset.color || "#8a4b2a";
  var greeting = script.dataset.greeting || "Hi! Ask me a question and I'll answer from our documents.";

  var host = document.createElement("div");
  host.id = "docs-chatbot-widget";
  document.body.appendChild(host);
  var root = host.attachShadow({ mode: "open" });

  root.innerHTML =
    "<style>" +
    ":host{all:initial}*{box-sizing:border-box;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}" +
    ".fab{position:fixed;right:20px;bottom:20px;width:56px;height:56px;border-radius:50%;border:0;background:" + color + ";color:#fff;font-size:24px;cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,.25);z-index:2147483646}" +
    ".panel{position:fixed;right:20px;bottom:88px;width:360px;max-width:calc(100vw - 40px);height:520px;max-height:calc(100vh - 110px);background:#fff;border-radius:14px;box-shadow:0 8px 30px rgba(0,0,0,.2);display:none;flex-direction:column;overflow:hidden;z-index:2147483647;font-size:14px;color:#1f2328}" +
    ".panel.open{display:flex}" +
    ".top{background:" + color + ";color:#fff;padding:12px 14px;font-weight:600;display:flex;justify-content:space-between;align-items:center}" +
    ".top button{background:none;border:0;color:#fff;font-size:18px;cursor:pointer}" +
    ".log{flex:1;overflow-y:auto;padding:12px;background:#fafafa}" +
    ".m{margin:0 0 10px;max-width:88%;line-height:1.45}.m .b{padding:8px 11px;border-radius:10px;white-space:pre-line}" +
    ".u{margin-left:auto}.u .b{background:" + color + ";color:#fff}" +
    ".a .b{background:#fff;border:1px solid #e3e3e3}.a.idk .b{background:#fff8e6;border-color:#f0d79a}" +
    ".src{font-size:12px;color:#555;margin-top:4px}.src div{border-left:3px solid " + color + ";padding:2px 6px;margin-top:3px;background:#fff}" +
    ".note{font-size:11px;color:#777;margin-top:3px}" +
    "form{display:flex;gap:6px;padding:10px;border-top:1px solid #eee}" +
    "input,textarea{font:inherit;flex:1;padding:8px 10px;border:1px solid #ddd;border-radius:8px;width:100%}" +
    "button.send{font:inherit;border:0;border-radius:8px;background:" + color + ";color:#fff;padding:8px 12px;cursor:pointer}" +
    ".human{display:grid;gap:6px;margin-top:6px;padding:8px;border:1px solid #e3e3e3;border-radius:8px;background:#fff}" +
    ".link{background:none;border:0;color:" + color + ";text-decoration:underline;cursor:pointer;padding:0;font:inherit;font-size:13px;margin-top:4px}" +
    "</style>" +
    "<button class='fab' aria-label='Open chat'>💬</button>" +
    "<div class='panel' role='dialog' aria-label='Chat'>" +
    "<div class='top'><span class='t'></span><button class='x' aria-label='Close'>×</button></div>" +
    "<div class='log'></div>" +
    "<form class='ask'><input maxlength='1000' placeholder='Type your question…' aria-label='Question'><button class='send'>Send</button></form>" +
    "</div>";

  var $ = function (s) { return root.querySelector(s); };
  var panel = $(".panel"), log = $(".log"), form = $("form.ask"), input = form.querySelector("input");
  $(".t").textContent = title;

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function scroll() { log.scrollTop = log.scrollHeight; }
  function say(cls, text) { var m = el("div", "m " + cls); m.appendChild(el("div", "b", text)); log.appendChild(m); scroll(); return m; }

  function post(path, body) {
    return fetch(api + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) {
        if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : "Something went wrong (" + r.status + ")");
        return j;
      }); });
  }

  function humanForm(question) {
    var f = el("form", "human");
    f.innerHTML = "<b>Talk to a human</b><input name='name' placeholder='Your name' required maxlength='100'>" +
      "<input name='email' type='email' placeholder='Your email' required maxlength='200'>" +
      "<textarea name='question' rows='2' required maxlength='2000'></textarea><button class='send'>Send</button>";
    f.querySelector("textarea").value = question;
    f.addEventListener("submit", function (e) {
      e.preventDefault();
      post("/api/leads", { name: f.elements.namedItem("name").value, email: f.elements.namedItem("email").value,
        question: f.elements.namedItem("question").value, page_url: location.href })
        .then(function (r) { f.replaceChildren(el("div", null, r.message)); })
        .catch(function (err) { f.appendChild(el("div", "note", err.message)); });
    });
    return f;
  }

  function answer(question, r) {
    var m = say(r.found ? "a" : "a idk", r.answer);
    if (r.sources && r.sources.length) {
      var s = el("div", "src", "Sources:");
      r.sources.forEach(function (x) {
        s.appendChild(el("div", null, x.source + (x.page ? ", page " + x.page : "") + ", chunk " + x.chunk));
      });
      m.appendChild(s);
    }
    if (r.offer_human) {
      var b = el("button", "link", "Talk to a human"); b.type = "button";
      b.onclick = function () { b.replaceWith(humanForm(question)); scroll(); };
      m.appendChild(b);
    }
    scroll();
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var q = input.value.trim(); if (!q) return;
    input.value = ""; say("u", q);
    var wait = say("a", "…");
    post("/api/chat", { question: q })
      .then(function (r) { wait.remove(); answer(q, r); })
      .catch(function (err) { wait.querySelector(".b").textContent = err.message; });
  });

  var greeted = false;
  function toggle(open) {
    panel.classList.toggle("open", open);
    if (open && !greeted) { say("a", greeting); greeted = true; }
    if (open) input.focus();
  }
  $(".fab").addEventListener("click", function () { toggle(!panel.classList.contains("open")); });
  $(".x").addEventListener("click", function () { toggle(false); });
})();
