(function () {
  const video = document.getElementById("cam-video");
  const startBtn = document.getElementById("cam-start");
  const stopBtn = document.getElementById("cam-stop");
  const detectBtn = document.getElementById("cam-detect");
  const result = document.getElementById("cam-result");
  const liveStatus = document.getElementById("live-status");
  if (!video || !startBtn) return;
  let stream = null;
  let timer = null;
  let busy = false;

  function setStatus(text) {
    if (liveStatus) liveStatus.textContent = text;
  }

  async function detectFrame() {
    if (!video.videoWidth || busy) return;
    busy = true;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    canvas.toBlob(async function (blob) {
      try {
        const body = new FormData();
        body.append("frame", blob, "frame.jpg");
        const response = await fetch("/api/live-frame", { method: "POST", body });
        if (!response.ok) {
          setStatus("Detection failed for this frame.");
          return;
        }
        const out = await response.blob();
        result.src = URL.createObjectURL(out);
        setStatus("Road damage identified on this frame.");
      } finally {
        busy = false;
      }
    }, "image/jpeg", 0.85);
  }

  startBtn.addEventListener("click", async function () {
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      video.srcObject = stream;
      setStatus("Camera started. Frames are sent only after you start detection.");
    } catch (err) {
      setStatus("Camera permission was not granted.");
    }
  });

  stopBtn.addEventListener("click", function () {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
    if (stream) stream.getTracks().forEach((t) => t.stop());
    video.srcObject = null;
    setStatus("Camera stopped.");
  });

  detectBtn.addEventListener("click", async function () {
    if (!video.videoWidth) {
      setStatus("Start the camera first.");
      return;
    }
    if (timer) {
      clearInterval(timer);
      timer = null;
      setStatus("Continuous detection paused.");
      return;
    }
    await detectFrame();
    timer = setInterval(detectFrame, 1800);
    setStatus("Reviewing the live camera view.");
  });
})();
