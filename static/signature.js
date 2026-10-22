/* Signature pad: draw on a canvas, serialize to a hidden input on submit. */
function setupSignaturePad(canvasId, clearId, hiddenId, formId) {
  var canvas = document.getElementById(canvasId);
  if (!canvas) return;
  var ctx = canvas.getContext("2d");

  ctx.lineWidth = 2.5;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.strokeStyle = "#1a1a2e";

  var drawing = false;

  function getPos(e) {
    var rect = canvas.getBoundingClientRect();
    var clientX = e.clientX || (e.touches && e.touches[0].clientX);
    var clientY = e.clientY || (e.touches && e.touches[0].clientY);
    var x = (clientX - rect.left) * (canvas.width / rect.width);
    var y = (clientY - rect.top) * (canvas.height / rect.height);
    return [x, y];
  }

  canvas.addEventListener("pointerdown", function (e) {
    drawing = true;
    var p = getPos(e);
    ctx.beginPath();
    ctx.moveTo(p[0], p[1]);
    try { canvas.setPointerCapture(e.pointerId); } catch (err) {}
  });
  canvas.addEventListener("pointermove", function (e) {
    if (!drawing) return;
    var p = getPos(e);
    ctx.lineTo(p[0], p[1]);
    ctx.stroke();
  });
  canvas.addEventListener("pointerup", function () { drawing = false; });
  canvas.addEventListener("pointerleave", function () { drawing = false; });

  var clearBtn = document.getElementById(clearId);
  if (clearBtn) {
    clearBtn.addEventListener("click", function () {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    });
  }

  var form = document.getElementById(formId);
  if (form) {
    form.addEventListener("submit", function () {
      document.getElementById(hiddenId).value = canvas.toDataURL("image/png");
    });
  }
}
