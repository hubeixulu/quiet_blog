(function () {
  "use strict";

  function csrfToken() {
    return document.cookie.split(";").map(function (item) { return item.trim(); })
      .find(function (item) { return item.startsWith("csrftoken="); })
      ?.split("=").slice(1).join("=") || "";
  }

  function uploadUrl() {
    return window.location.pathname.replace(/(?:add|[^/]+\/change)\/$/, "upload-image/");
  }

  async function uploadBlob(blob) {
    var data = new FormData();
    data.append("image", blob, blob.name || "pasted-image");
    var response = await fetch(uploadUrl(), {
      method: "POST",
      headers: { "X-CSRFToken": decodeURIComponent(csrfToken()) },
      body: data,
      credentials: "same-origin"
    });
    var result = await response.json();
    if (!response.ok) throw new Error(result.error || "图片上传失败");
    return result.url;
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, function (char) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char];
    });
  }

  function selectedText(source) {
    return source.value.slice(source.selectionStart, source.selectionEnd);
  }

  function replaceSelection(source, text) {
    var start = source.selectionStart;
    var end = source.selectionEnd;
    source.setRangeText(text, start, end, "end");
    source.dispatchEvent(new Event("input", { bubbles: true }));
    source.focus();
  }

  function start() {
    var source = document.querySelector("textarea.quiet-editor-source");
    if (!source) return;

    var shell = document.createElement("div");
    shell.className = "quiet-editor-shell";
    var tools = document.createElement("div");
    tools.className = "quiet-editor-tools";
    var status = document.createElement("div");
    status.className = "quiet-editor-status";
    status.setAttribute("aria-live", "polite");

    function message(text, error) {
      status.textContent = text || "";
      status.classList.toggle("error", Boolean(error));
    }

    var fontLabel = document.createElement("label");
    fontLabel.textContent = "字号";
    var fontSelect = document.createElement("select");
    fontSelect.innerHTML = [
      '<option value="">选择字号</option>',
      '<option value="font-size-small">小号</option>',
      '<option value="font-size-normal">正文</option>',
      '<option value="font-size-large">大号</option>',
      '<option value="font-size-x-large">特大</option>',
      '<option value="font-size-title">标题级</option>'
    ].join("");
    fontLabel.append(fontSelect);
    tools.append(fontLabel);

    shell.append(tools, status);
    source.before(shell);
    source.classList.add("quiet-editor-initialized");

    fontSelect.addEventListener("change", function () {
      if (!fontSelect.value) return;
      var text = selectedText(source) || "要调整字号的文字";
      replaceSelection(source, '<span class="' + fontSelect.value + '">' + escapeHtml(text) + '</span>');
      message("已插入字号标记，发布后会按所选字号显示");
      fontSelect.value = "";
    });

    source.addEventListener("paste", function (event) {
      var files = Array.from(event.clipboardData?.files || []).filter(function (file) {
        return file.type.startsWith("image/");
      });
      if (!files.length) return;
      event.preventDefault();
      message("正在上传粘贴的图片…");
      Promise.all(files.map(uploadBlob)).then(function (urls) {
        replaceSelection(source, urls.map(function (url, index) {
          return "![图片" + (index + 1) + "](" + url + ")";
        }).join("\n"));
        message("图片已上传并插入 Markdown");
      }).catch(function (error) { message(error.message, true); });
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
