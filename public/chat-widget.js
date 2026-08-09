/*
 * Widget de "Fale no WhatsApp" do OgrowNT.
 * Uso no site da empresa (sem dependencias, cola e funciona):
 *
 * <script
 *   src="https://SEU-DOMINIO/widget/chat-widget.js"
 *   data-phone="5511999999999"
 *   data-message="Ola! Quero agendar um horario."
 *   data-color="#25D366"
 *   data-position="right"
 *   defer
 * ></script>
 */
(function () {
  var currentScript = document.currentScript;
  if (!currentScript) return;

  var phone = (currentScript.getAttribute("data-phone") || "").replace(/[^\d]/g, "");
  if (!phone) {
    console.warn("[ogrownt-widget] data-phone nao informado no <script> do widget.");
    return;
  }

  var message = currentScript.getAttribute("data-message") || "Ola! Gostaria de mais informacoes.";
  var color = currentScript.getAttribute("data-color") || "#25D366";
  var position = currentScript.getAttribute("data-position") === "left" ? "left" : "right";

  var style = document.createElement("style");
  style.textContent =
    ".ogrownt-wa-btn{position:fixed;bottom:20px;" +
    position +
    ":20px;width:56px;height:56px;border-radius:50%;" +
    "background:" +
    color +
    ";display:flex;align-items:center;justify-content:center;" +
    "box-shadow:0 4px 12px rgba(0,0,0,0.25);cursor:pointer;z-index:2147483000;border:none;" +
    "transition:transform .15s ease;}" +
    ".ogrownt-wa-btn:hover{transform:scale(1.06);}" +
    ".ogrownt-wa-btn svg{width:30px;height:30px;}";
  document.head.appendChild(style);

  var button = document.createElement("button");
  button.className = "ogrownt-wa-btn";
  button.setAttribute("aria-label", "Falar no WhatsApp");
  button.innerHTML =
    '<svg viewBox="0 0 32 32" fill="white" xmlns="http://www.w3.org/2000/svg">' +
    '<path d="M16.004 3C9.377 3 4 8.373 4 15c0 2.36.687 4.56 1.872 6.41L4 29l7.78-1.84A11.93 11.93 0 0 0 16.004 27C22.63 27 28 21.627 28 15S22.63 3 16.004 3zm0 21.6a9.55 9.55 0 0 1-4.87-1.33l-.35-.21-4.62 1.09 1.11-4.5-.23-.37A9.56 9.56 0 1 1 25.6 15c0 5.3-4.3 9.6-9.596 9.6zm5.24-7.17c-.29-.14-1.7-.84-1.96-.93-.26-.1-.45-.14-.64.14-.19.29-.74.93-.9 1.12-.17.19-.33.21-.62.07-.29-.14-1.22-.45-2.32-1.43-.86-.76-1.44-1.7-1.61-1.99-.17-.29-.02-.44.13-.58.13-.13.29-.33.43-.5.14-.17.19-.29.29-.48.1-.19.05-.36-.02-.5-.07-.14-.64-1.54-.88-2.11-.23-.55-.47-.48-.64-.49-.17-.01-.36-.01-.55-.01-.19 0-.5.07-.76.36-.26.29-1 1-1 2.43 0 1.43 1.02 2.81 1.17 3 .14.19 2.01 3.07 4.88 4.31.68.29 1.21.47 1.63.6.68.22 1.31.19 1.8.11.55-.08 1.7-.69 1.94-1.36.24-.67.24-1.24.17-1.36-.07-.12-.26-.19-.55-.33z"/>' +
    "</svg>";

  button.addEventListener("click", function () {
    var url = "https://wa.me/" + phone + "?text=" + encodeURIComponent(message);
    window.open(url, "_blank", "noopener,noreferrer");
  });

  if (document.body) {
    document.body.appendChild(button);
  } else {
    document.addEventListener("DOMContentLoaded", function () {
      document.body.appendChild(button);
    });
  }
})();
