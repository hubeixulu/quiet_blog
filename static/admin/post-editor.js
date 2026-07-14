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

  async function importRemote(url) {
    var response = await fetch(uploadUrl(), {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": decodeURIComponent(csrfToken()) },
      body: JSON.stringify({ url: url }),
      credentials: "same-origin"
    });
    var result = await response.json();
    if (!response.ok) throw new Error(result.error || "远程图片转存失败");
    return result.url;
  }


  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, function (char) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char];
    });
  }

  function fontSizeControl(editor, source, message) {
    var bar = document.createElement("div");
    bar.className = "quiet-editor-tools";
    var label = document.createElement("label");
    label.textContent = "字号";
    var select = document.createElement("select");
    select.innerHTML = [
      '<option value="">选择字号</option>',
      '<option value="font-size-small">小号</option>',
      '<option value="font-size-normal">正文</option>',
      '<option value="font-size-large">大号</option>',
      '<option value="font-size-x-large">特大</option>',
      '<option value="font-size-title">标题级</option>'
    ].join("");
    label.append(select);
    bar.append(label);
    select.addEventListener("change", function () {
      if (!select.value) return;
      var selected = editor.getSelectedText() || "要调整字号的文字";
      editor.replaceSelection('<span class="' + select.value + '">' + escapeHtml(selected) + '</span>');
      source.value = editor.getMarkdown();
      message("已插入字号标记，可在预览中查看效果");
      select.value = "";
      editor.focus();
    });
    return bar;
  }

  function start() {
    var source = document.querySelector("textarea.quiet-editor-source");
    if (!source) return;
    if (!window.toastui?.Editor) {
      source.insertAdjacentHTML("afterend", '<p class="errornote">可视化编辑器资源加载失败，当前可继续使用 Markdown 输入框。</p>');
      return;
    }
    var shell = document.createElement("div");
    shell.className = "quiet-editor-shell";
    var mount = document.createElement("div");
    var status = document.createElement("div");
    status.className = "quiet-editor-status";
    status.setAttribute("aria-live", "polite");
    shell.append(mount, status);
    source.after(shell);

    function message(text, error) {
      status.textContent = text || "";
      status.classList.toggle("error", Boolean(error));
    }

    var editor;
    try {
      editor = new window.toastui.Editor({
        el: mount,
        height: "620px",
        initialEditType: "markdown",
        language: "zh-CN",
        previewStyle: "vertical",
        initialValue: source.value,
        usageStatistics: false,
        customHTMLSanitizer: function (html) { return window.DOMPurify.sanitize(html); },
        hooks: {
          addImageBlobHook: function (blob, callback) {
            message("正在上传图片…");
            uploadBlob(blob).then(function (url) {
              callback(url, blob.name || "图片");
              message("图片已上传");
            }).catch(function (error) { message(error.message, true); });
            return false;
          }
        },
        events: {
          change: function () { source.value = editor.getMarkdown(); }
        }
      });
    } catch (error) {
      shell.remove();
      source.insertAdjacentHTML("afterend", '<p class="errornote">可视化编辑器加载失败，已保留 Markdown 输入框。</p>');
      console.error("Quiet Blog editor failed to initialize", error);
      return;
    }
    shell.prepend(fontSizeControl(editor, source, message));
    source.classList.add("quiet-editor-initialized");

    mount.addEventListener("paste", function (event) {
      var html = event.clipboardData?.getData("text/html") || "";
      if (!html || event.clipboardData?.files.length) return;
      var documentFragment = new DOMParser().parseFromString(html, "text/html");
      var urls = Array.from(documentFragment.images).map(function (img) { return img.src; })
        .filter(function (url) { return /^https?:\/\//i.test(url); });
      if (!urls.length) return;
      window.setTimeout(async function () {
        message("正在转存粘贴内容中的图片…");
        try {
          var pastedDocument = new DOMParser().parseFromString(editor.getHTML(), "text/html");
          var remoteImages = Array.from(pastedDocument.images).filter(function (img) {
            return urls.includes(img.src);
          });
          var imported = new Map();
          for (var image of remoteImages) {
            if (!imported.has(image.src)) imported.set(image.src, await importRemote(image.src));
            image.src = imported.get(image.src);
          }
          editor.setHTML(pastedDocument.body.innerHTML, false);
          source.value = editor.getMarkdown();
          message("粘贴的图片已保存到本站");
        } catch (error) { message(error.message, true); }
      }, 100);
    });

    source.form?.addEventListener("submit", function () { source.value = editor.getMarkdown(); });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
