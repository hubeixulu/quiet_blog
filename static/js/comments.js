(function () {
  "use strict";
  var form = document.querySelector(".comment-form");
  if (!form) return;
  var parentInput = form.querySelector("input[name=parent_id]");
  var notice = form.querySelector(".replying-to");
  var replyName = notice.querySelector("strong");

  document.addEventListener("click", function (event) {
    var button = event.target.closest(".comment-reply");
    if (!button) return;
    parentInput.value = button.dataset.commentId;
    replyName.textContent = button.dataset.commentName;
    notice.hidden = false;
    form.scrollIntoView({ behavior: "smooth", block: "center" });
    form.querySelector("textarea").focus({ preventScroll: true });
  });
  notice.querySelector("button").addEventListener("click", function () {
    parentInput.value = "";
    notice.hidden = true;
  });
  var captchaImage = form.querySelector(".captcha-row img");
  form.querySelector(".captcha-refresh").addEventListener("click", function () {
    captchaImage.src = captchaImage.src.split("?")[0] + "?t=" + Date.now();
  });
})();
