/* Floating help chat widget with file upload + conversion. */
(function () {
  var toggle = document.getElementById("chatToggle");
  var panel = document.getElementById("chatPanel");
  if (!toggle || !panel) return;

  var close = document.getElementById("chatClose");
  var msgs = document.getElementById("chatMessages");
  var text = document.getElementById("chatText");
  var send = document.getElementById("chatSend");
  var attach = document.getElementById("chatAttach");
  var fileInput = document.getElementById("chatFile");

  toggle.addEventListener("click", function () {
    panel.classList.toggle("hidden");
    if (!panel.classList.contains("hidden")) text.focus();
  });
  close.addEventListener("click", function () { panel.classList.add("hidden"); });

  var downloadLabel = panel.getAttribute("data-download") || "Download";

  function addMsg(txt, who, link) {
    var d = document.createElement("div");
    d.className = "chat-msg " + who;
    if (who === "bot") {
      var img = document.createElement("img");
      img.className = "chat-bot-avatar";
      img.src = "/static/robot.svg";
      img.alt = "";
      d.appendChild(img);
      var body = document.createElement("span");
      body.className = "chat-bot-body";
      var t = document.createElement("span");
      t.textContent = txt;
      body.appendChild(t);
      if (link) {
        var a = document.createElement("a");
        a.href = link;
        a.target = "_blank";
        a.rel = "noopener";
        a.className = "chat-link";
        a.textContent = "⬇ " + downloadLabel;
        body.appendChild(a);
      }
      d.appendChild(body);
    } else {
      d.textContent = txt;
    }
    msgs.appendChild(d);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function sendText() {
    var m = text.value.trim();
    if (!m) return;
    addMsg(m, "user");
    text.value = "";
    var lang = panel.getAttribute("data-lang") || "en";
    fetch("/chatbot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: m, lang: lang })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) { addMsg(data.reply || "...", "bot"); })
      .catch(function () { addMsg("...", "bot"); });
  }

  function sendFile() {
    var f = fileInput.files[0];
    if (!f) { sendText(); return; }
    var m = text.value.trim();
    addMsg((m ? m + "  " : "") + "📎 " + f.name, "user");
    text.value = "";
    var fd = new FormData();
    fd.append("file", f);
    fd.append("message", m);
    fd.append("lang", panel.getAttribute("data-lang") || "en");
    fetch("/chatbot/upload", { method: "POST", body: fd })
      .then(function (r) { return r.json(); })
      .then(function (data) { addMsg(data.reply || "...", "bot", data.link); })
      .catch(function () { addMsg("...", "bot"); });
    fileInput.value = "";
  }

  send.addEventListener("click", function () {
    if (fileInput.files.length) sendFile(); else sendText();
  });
  text.addEventListener("keydown", function (e) { if (e.key === "Enter") send.click(); });
  if (attach) attach.addEventListener("click", function () { fileInput.click(); });

  var greet = panel.getAttribute("data-greeting");
  if (greet) addMsg(greet, "bot");
})();
