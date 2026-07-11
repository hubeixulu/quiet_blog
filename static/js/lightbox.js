(function () {
  "use strict";
  var dialog = document.createElement("dialog");
  dialog.className = "image-lightbox";
  dialog.setAttribute("aria-label", "图片预览");
  dialog.innerHTML = '<button class="image-lightbox-close" type="button" aria-label="关闭图片预览">×</button><div class="image-lightbox-stage"><figure><img alt=""><figcaption></figcaption></figure></div>';
  document.body.appendChild(dialog);

  var stage = dialog.querySelector(".image-lightbox-stage");
  var preview = dialog.querySelector("img");
  var caption = dialog.querySelector("figcaption");

  function close() { dialog.close(); }

  document.addEventListener("click", function (event) {
    var image = event.target.closest(".article .prose img, .article img.cover, .post-card img");
    if (!image) return;
    preview.src = image.currentSrc || image.src;
    preview.alt = image.alt || "文章图片";
    caption.textContent = image.alt || "";
    caption.hidden = !image.alt;
    document.documentElement.classList.add("lightbox-open");
    dialog.showModal();
  });

  dialog.querySelector(".image-lightbox-close").addEventListener("click", close);
  stage.addEventListener("click", function (event) { if (event.target === stage) close(); });
  dialog.addEventListener("close", function () {
    preview.removeAttribute("src");
    document.documentElement.classList.remove("lightbox-open");
  });
})();
