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

  function isEditorHtml(value) {
    return /^\s*<(?:p|h[1-6]|ul|ol|blockquote|pre|table|hr)(?:\s|>|\/)/i.test(value || "");
  }

  function legacyEditorValue(value) {
    return String(value || "").replace(/\r\n?/g, "\n").split("\n").map(function (line) {
      return line.replace(/^ +/, function (spaces) { return "\u00a0".repeat(spaces.length); });
    }).join("\n\n");
  }

  function serializedHtml(editor, mount) {
    var template = document.createElement("template");
    var visualEditor = mount.querySelector(".toastui-editor-ww-container .ProseMirror");
    // Toast UI's getHTML() converts the ProseMirror document and normalizes
    // leading whitespace on the way. Read the live WYSIWYG DOM instead so the
    // number of spaces the author typed is still available to us.
    var html;
    if (editor.isWysiwygMode() && visualEditor) {
      var visualContent = visualEditor.cloneNode(true);
      visualContent.querySelectorAll(".placeholder, .ProseMirror-widget").forEach(function (decoration) {
        decoration.remove();
      });
      html = visualContent.innerHTML;
    } else {
      html = editor.getHTML();
    }
    template.innerHTML = window.DOMPurify.sanitize(html);
    template.content.querySelectorAll("p, li, blockquote, h1, h2, h3, h4, h5, h6, td, th").forEach(function (block) {
      var walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT);
      var textNode;
      var atLineStart = true;
      while ((textNode = walker.nextNode())) {
        // HTML collapses ordinary runs of spaces, and ProseMirror drops even a
        // single leading space when parsing saved HTML. Non-breaking spaces
        // preserve the exact count through saving, rendering, and reloading.
        var value = textNode.data;
        if (atLineStart) {
          value = value.replace(/^ +/, function (spaces) { return "\u00a0".repeat(spaces.length); });
        }
        value = value.replace(/\n +/g, function (match) {
          return "\n" + "\u00a0".repeat(match.length - 1);
        });
        value = value.replace(/ {2,}/g, function (spaces) {
          return "\u00a0".repeat(spaces.length);
        });
        textNode.data = value;
        atLineStart = value.endsWith("\n");
      }
    });
    return template.innerHTML;
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
        initialEditType: "wysiwyg",
        language: "zh-CN",
        previewStyle: "vertical",
        initialValue: isEditorHtml(source.value) ? "" : legacyEditorValue(source.value),
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
          change: function () { source.value = serializedHtml(editor, mount); }
        }
      });
      if (isEditorHtml(source.value)) editor.setHTML(source.value, false);
      source.value = serializedHtml(editor, mount);
    } catch (error) {
      shell.remove();
      source.insertAdjacentHTML("afterend", '<p class="errornote">可视化编辑器加载失败，已保留 Markdown 输入框。</p>');
      console.error("Quiet Blog editor failed to initialize", error);
      return;
    }
    source.classList.add("quiet-editor-initialized");

    mount.addEventListener("beforeinput", function (event) {
      if (event.inputType !== "insertText" || event.data !== " " || !editor.isWysiwygMode()) return;
      var visualEditor = mount.querySelector(".toastui-editor-ww-container .ProseMirror");
      if (!visualEditor || !visualEditor.contains(event.target)) return;
      var selection = window.getSelection();
      if (!selection || !selection.rangeCount || !selection.isCollapsed) return;
      var range = selection.getRangeAt(0);
      var anchorElement = selection.anchorNode?.nodeType === Node.ELEMENT_NODE
        ? selection.anchorNode
        : selection.anchorNode?.parentElement;
      var block = anchorElement?.closest("p, li, blockquote, h1, h2, h3, h4, h5, h6, td, th");
      if (!block || !visualEditor.contains(block)) return;
      var beforeCaret = range.cloneRange();
      beforeCaret.selectNodeContents(block);
      beforeCaret.setEnd(range.startContainer, range.startOffset);
      var textBeforeCaret = beforeCaret.toString();
      if (textBeforeCaret === "" || /\s$/.test(textBeforeCaret)) {
        event.preventDefault();
        event.stopPropagation();
        editor.insertText("\u00a0");
      }
    }, true);

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
          source.value = serializedHtml(editor, mount);
          message("粘贴的图片已保存到本站");
        } catch (error) { message(error.message, true); }
      }, 100);
    });

    source.form?.addEventListener("submit", function () { source.value = serializedHtml(editor, mount); });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
