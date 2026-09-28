(() => {
  const $ = (s) => document.querySelector(s);
  const cards = Object.fromEntries(window.CARDS.map((c) => [c.id, c]));

  const views = { start: $("#start"), scanner: $("#scanner"), holo: $("#holo") };
  const video = $("#video");
  const canvas = $("#canvas");
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  const stage = $("#stage");

  const state = {
    stream: null,
    scanning: false,
    card: null,
    slides: [],
    i: 0,
    timer: null,
    auto: true,
    pyramid: false,
    flip: -1,
    ignore: { id: null, until: 0 },
    wakeLock: null,
  };

  function show(name) {
    for (const [k, el] of Object.entries(views)) el.hidden = k !== name;
  }

  function setStatus(text) {
    $("#status").textContent = text;
  }

  /* ---------------- Camera + QR scanning ---------------- */

  async function startCamera() {
    show("scanner");
    if (state.stream) return resumeScan();
    try {
      state.stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });
      video.srcObject = state.stream;
      await video.play();
      resumeScan();
    } catch (err) {
      setStatus("Camera unavailable (" + err.name + "). Use “Choose card” instead.");
    }
  }

  function resumeScan() {
    setStatus("Point the camera at the card's QR code");
    state.scanning = true;
    requestAnimationFrame(scanLoop);
  }

  let lastScan = 0;
  function scanLoop(t) {
    if (!state.scanning) return;
    requestAnimationFrame(scanLoop);
    if (t - lastScan < 150 || video.readyState < 2 || !video.videoWidth) return;
    lastScan = t;

    const w = 640;
    const h = Math.round((video.videoHeight / video.videoWidth) * w);
    canvas.width = w;
    canvas.height = h;
    ctx.drawImage(video, 0, 0, w, h);
    const code = jsQR(ctx.getImageData(0, 0, w, h).data, w, h, { inversionAttempts: "dontInvert" });
    if (!code) return;

    const id = parseCardId(code.data);
    if (!id) return setStatus("Unknown QR code: " + code.data.slice(0, 40));
    if (id === state.ignore.id && performance.now() < state.ignore.until) return;
    found(id);
  }

  // Accepts "eve", "card:eve" or a URL containing ?card=eve / #card=eve
  function parseCardId(text) {
    text = text.trim();
    try {
      const url = new URL(text);
      const id = url.searchParams.get("card") || new URLSearchParams(url.hash.slice(1)).get("card");
      if (id && cards[id.toLowerCase()]) return id.toLowerCase();
    } catch (_) { /* not a URL */ }
    const id = text.toLowerCase().replace(/^card:/, "");
    return cards[id] ? id : null;
  }

  function found(id) {
    state.scanning = false;
    navigator.vibrate?.(60);
    openCard(id);
  }

  /* ---------------- OCR fallback (cards without a QR code) ---------------- */

  let ocrWorker = null;

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = src;
      s.onload = resolve;
      s.onerror = () => reject(new Error("Failed to load " + src));
      document.head.append(s);
    });
  }

  // Maps the on-screen guide frame to pixel coordinates in the video (object-fit: cover)
  function guideRectInVideo() {
    const vr = video.getBoundingClientRect();
    const gr = $("#guide").getBoundingClientRect();
    const scale = Math.max(vr.width / video.videoWidth, vr.height / video.videoHeight);
    const ox = (vr.width - video.videoWidth * scale) / 2;
    const oy = (vr.height - video.videoHeight * scale) / 2;
    return {
      x: (gr.left - vr.left - ox) / scale,
      y: (gr.top - vr.top - oy) / scale,
      w: gr.width / scale,
      h: gr.height / scale,
    };
  }

  function levenshtein(a, b) {
    const d = Array.from({ length: a.length + 1 }, (_, i) => [i]);
    for (let j = 1; j <= b.length; j++) d[0][j] = j;
    for (let i = 1; i <= a.length; i++)
      for (let j = 1; j <= b.length; j++)
        d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    return d[a.length][b.length];
  }

  function matchText(text) {
    const upper = text.toUpperCase();
    const words = upper.split(/[^A-Z]+/).filter((w) => w.length >= 3);
    let best = null;
    for (const c of window.CARDS) {
      const name = c.name.toUpperCase();
      const tolerance = name.length <= 4 ? 1 : 2;
      for (const w of words) {
        const dist = levenshtein(w, name);
        if (dist <= tolerance && (!best || dist < best.dist)) best = { id: c.id, dist };
      }
      if (!best && upper.replace(/\s+/g, " ").includes(c.title.toUpperCase())) best = { id: c.id, dist: 3 };
    }
    return best?.id || null;
  }

  async function readTitle() {
    if (!video.videoWidth) return;
    const btn = $("#btnOcr");
    btn.disabled = true;
    state.scanning = false;
    try {
      setStatus("Loading text reader…");
      if (!window.Tesseract) await loadScript("https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.min.js");
      ocrWorker ??= await Tesseract.createWorker("eng");

      setStatus("Reading card title…");
      const g = guideRectInVideo();
      // Top ~30% of the card holds the name and subtitle; upscale for better OCR.
      const crop = { x: g.x, y: g.y, w: g.w, h: g.h * 0.3 };
      canvas.width = Math.round(crop.w * 2);
      canvas.height = Math.round(crop.h * 2);
      ctx.filter = "grayscale(1) contrast(1.6)";
      ctx.drawImage(video, crop.x, crop.y, crop.w, crop.h, 0, 0, canvas.width, canvas.height);
      ctx.filter = "none";

      const { data } = await ocrWorker.recognize(canvas);
      const id = matchText(data.text);
      if (id) return found(id);
      setStatus("Couldn't recognise the card. Fit it inside the frame and try again.");
    } catch (err) {
      setStatus("Text reader failed: " + err.message);
    } finally {
      btn.disabled = false;
      if (views.scanner.hidden === false && !state.scanning && !state.card) resumeScanSoon();
    }
  }

  function resumeScanSoon() {
    setTimeout(() => {
      if (!views.scanner.hidden && !state.scanning) {
        state.scanning = true;
        requestAnimationFrame(scanLoop);
      }
    }, 2500);
  }

  /* ---------------- Hologram slides ---------------- */

  function wordReveal(text) {
    const words = text.split(" ");
    const step = Math.min(0.06, 2.2 / words.length);
    return words.map((w, i) => `<span class="w" style="animation-delay:${(0.5 + i * step).toFixed(2)}s">${w}</span>`).join(" ");
  }

  function buildSlides(c) {
    const slides = [];
    slides.push({
      ms: 5000,
      html: `<div class="slide s-intro">
        ${c.image ? `<div class="art"><img src="${c.image}" alt="" onerror="this.parentNode.remove()"></div>` : ""}
        <div class="kicker">${c.testament} · No. ${c.no}</div>
        <h1 class="name">${c.name}</h1>
        <div class="subtitle">${c.title}</div>
      </div>`,
    });
    c.verses.forEach((v, k) => {
      const part = c.verses.length > 1 ? ` · ${k + 1}/${c.verses.length}` : "";
      slides.push({
        ms: Math.min(15000, 4000 + v.text.length * 45),
        html: `<div class="slide s-verse">
          <div class="kicker">📖 ${c.reference}${part}</div>
          <p class="verse ${v.text.length > 140 ? "long" : ""}"><sup>${v.n}</sup> ${wordReveal(v.text)}</p>
        </div>`,
      });
    });
    slides.push({
      ms: 8000,
      html: `<div class="slide s-power">
        <div class="kicker">Card Power</div>
        <p class="ability">${c.ability}</p>
        <div class="sin"><span class="lbl">Sin</span><span class="num">${c.sin}</span></div>
      </div>`,
    });
    return slides;
  }

  function renderFrame() {
    stage.classList.toggle("pyramid", state.pyramid);
    if (state.pyramid) {
      stage.innerHTML = `<div class="pyr" style="--flip:${state.flip}">
        ${[0, 90, 180, 270].map((a) => `<div class="panel" style="--a:${a}deg"><div class="host"></div></div>`).join("")}
        <div class="tip"></div>
      </div>`;
    } else {
      stage.innerHTML = `<div class="projector">
        <div class="beam"></div>
        <div class="base"></div>
        <div class="screen"><div class="host"></div><div class="sweep"></div></div>
      </div>`;
    }
    $("#btnMirror").hidden = !state.pyramid;
    renderSlide();
  }

  function renderSlide() {
    const slide = state.slides[state.i];
    stage.querySelectorAll(".host").forEach((h) => (h.innerHTML = slide.html));
    $("#dots").innerHTML = state.slides.map((_, k) => `<i class="${k === state.i ? "on" : ""}"></i>`).join("");
    clearTimeout(state.timer);
    if (state.auto) state.timer = setTimeout(() => go(1), slide.ms);
  }

  function go(delta) {
    const n = state.slides.length;
    state.i = (state.i + delta + n) % n;
    renderSlide();
  }

  async function openCard(id) {
    const card = cards[id];
    if (!card) return;
    state.card = card;
    state.slides = buildSlides(card);
    state.i = 0;
    show("holo");
    renderFrame();
    try { state.wakeLock = await navigator.wakeLock?.request("screen"); } catch (_) { /* optional */ }
  }

  function closeCard() {
    clearTimeout(state.timer);
    state.ignore = { id: state.card?.id, until: performance.now() + 3000 };
    state.card = null;
    stage.innerHTML = "";
    state.wakeLock?.release?.();
    state.wakeLock = null;
    if (document.fullscreenElement) document.exitFullscreen?.();
    if (state.stream) {
      show("scanner");
      resumeScan();
    } else {
      show("start");
    }
    history.replaceState(null, "", location.pathname);
  }

  function setAuto(on) {
    state.auto = on;
    $("#btnPlay").textContent = on ? "❚❚" : "▶";
    $("#btnPlay").setAttribute("aria-label", on ? "Pause slideshow" : "Play slideshow");
    renderSlide();
  }

  /* ---------------- Card picker ---------------- */

  function openPicker() {
    state.scanning = false;
    $("#pickList").innerHTML = window.CARDS.map(
      (c) => `<button class="pick" data-id="${c.id}"><b>${c.name}</b><span>${c.title}</span></button>`
    ).join("");
    $("#picker").showModal();
  }

  $("#pickList").addEventListener("click", (e) => {
    const b = e.target.closest(".pick");
    if (!b) return;
    $("#picker").close();
    openCard(b.dataset.id);
  });

  $("#picker").addEventListener("close", () => {
    if (!state.card && !views.scanner.hidden) resumeScan();
  });

  /* ---------------- Wiring ---------------- */

  $("#btnStart").onclick = startCamera;
  $("#btnPickStart").onclick = openPicker;
  $("#btnPick").onclick = openPicker;
  $("#btnOcr").onclick = readTitle;
  $("#btnClose").onclick = closeCard;
  $("#btnPrev").onclick = () => go(-1);
  $("#btnNext").onclick = () => go(1);
  $("#btnPlay").onclick = () => setAuto(!state.auto);
  $("#btnPyr").onclick = () => { state.pyramid = !state.pyramid; renderFrame(); };
  $("#btnMirror").onclick = () => { state.flip *= -1; renderFrame(); };
  $("#btnFs").onclick = () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else document.documentElement.requestFullscreen?.();
  };

  document.addEventListener("keydown", (e) => {
    if (views.holo.hidden) return;
    if (e.key === "ArrowRight") go(1);
    else if (e.key === "ArrowLeft") go(-1);
    else if (e.key === "Escape") closeCard();
    else if (e.key === " ") setAuto(!state.auto);
  });

  let downX = null;
  stage.addEventListener("pointerdown", (e) => (downX = e.clientX));
  stage.addEventListener("pointerup", (e) => {
    if (downX === null) return;
    const dx = e.clientX - downX;
    downX = null;
    if (Math.abs(dx) > 50) go(dx < 0 ? 1 : -1);
  });

  // Opened from a phone's own camera app via a QR link like index.html?card=eve
  const initial = new URLSearchParams(location.search).get("card");
  if (initial && cards[initial.toLowerCase()]) openCard(initial.toLowerCase());
})();
