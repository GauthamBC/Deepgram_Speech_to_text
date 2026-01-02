<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Practice audio (slow & clear)</title>
  <style>
    :root{
      --bg:#0b0f14;
      --panel:#0f1620;
      --panel2:#0c121b;
      --text:#e9eef5;
      --muted:#a7b2c3;
      --border:rgba(255,255,255,.08);
      --btn:#162233;
      --btnHover:#1b2a40;
      --accent:#7aa2ff;
      --shadow: 0 10px 30px rgba(0,0,0,.35);
      --radius:16px;
    }
    *{box-sizing:border-box}
    body{
      margin:0;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
      background: radial-gradient(900px 500px at 20% 0%, rgba(122,162,255,.18), transparent 60%),
                  radial-gradient(900px 500px at 80% 20%, rgba(122,162,255,.10), transparent 60%),
                  var(--bg);
      color:var(--text);
    }

    /* Sticky top bar */
    .topbar{
      position: sticky;
      top: 0;
      z-index: 50;
      backdrop-filter: blur(10px);
      background: rgba(11,15,20,.75);
      border-bottom: 1px solid var(--border);
    }
    .topbar-inner{
      max-width: 1100px;
      margin: 0 auto;
      padding: 14px 18px;
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap: 12px;
    }
    .title{
      display:flex;
      flex-direction:column;
      gap:2px;
      line-height:1.1;
    }
    .title h1{
      margin:0;
      font-size: 26px;
      font-weight: 750;
      letter-spacing: .2px;
    }
    .title p{
      margin:0;
      color:var(--muted);
      font-size: 13px;
    }
    .actions{
      display:flex;
      align-items:center;
      gap:10px;
      flex-wrap:wrap;
      justify-content:flex-end;
    }
    .pill{
      font-size: 12px;
      color: var(--muted);
      border:1px solid var(--border);
      padding:8px 10px;
      border-radius:999px;
      background: rgba(255,255,255,.03);
      white-space:nowrap;
    }
    .btn{
      border: 1px solid var(--border);
      background: var(--btn);
      color: var(--text);
      padding: 10px 12px;
      border-radius: 12px;
      cursor:pointer;
      font-weight:650;
      font-size: 13px;
      transition: transform .08s ease, background .15s ease, border-color .15s ease;
    }
    .btn:hover{ background: var(--btnHover); border-color: rgba(122,162,255,.30); }
    .btn:active{ transform: translateY(1px); }
    .btn.secondary{
      background: rgba(255,255,255,.03);
    }

    .wrap{
      max-width: 1100px;
      margin: 0 auto;
      padding: 18px;
    }

    .card{
      background: linear-gradient(180deg, rgba(255,255,255,.04), rgba(255,255,255,.02));
      border: 1px solid var(--border);
      box-shadow: var(--shadow);
      border-radius: var(--radius);
      overflow:hidden;
    }
    .table{
      width:100%;
      border-collapse: collapse;
    }
    .thead{
      background: rgba(255,255,255,.03);
      border-bottom:1px solid var(--border);
    }
    .thead th{
      text-align:left;
      padding: 14px 16px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: .4px;
      text-transform: uppercase;
    }
    .tbody td{
      padding: 14px 16px;
      border-bottom: 1px solid var(--border);
      vertical-align: middle;
    }
    .tbody tr:last-child td{ border-bottom:none; }

    .phrase{
      font-size: 15px;
      font-weight: 650;
      letter-spacing:.1px;
    }
    .sub{
      margin-top:6px;
      color:var(--muted);
      font-size: 12px;
    }

    .controls{
      display:flex;
      gap:10px;
      align-items:center;
      flex-wrap:wrap;
      justify-content:flex-start;
    }
    .mode{
      display:inline-flex;
      align-items:center;
      gap:8px;
      padding: 10px 12px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,.03);
      cursor:pointer;
      user-select:none;
      font-size: 13px;
      font-weight: 700;
    }
    .mode:hover{ border-color: rgba(122,162,255,.30); }
    .mode[disabled]{
      opacity:.55;
      cursor:not-allowed;
    }
    .mode .dot{
      width:8px; height:8px; border-radius:999px;
      background: rgba(122,162,255,.9);
      box-shadow: 0 0 0 3px rgba(122,162,255,.16);
    }

    .status{
      display:flex;
      align-items:center;
      gap:10px;
      color: var(--muted);
      font-size: 12px;
      margin-left: 6px;
    }
    .spinner{
      width: 14px;
      height: 14px;
      border-radius: 999px;
      border: 2px solid rgba(255,255,255,.18);
      border-top-color: rgba(122,162,255,.9);
      animation: spin .8s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    .footer-note{
      padding: 14px 16px;
      border-top:1px solid var(--border);
      background: rgba(0,0,0,.18);
      color: var(--muted);
      font-size: 12px;
      line-height: 1.4;
    }

    .hidden-audio{
      position:absolute;
      width:1px;
      height:1px;
      overflow:hidden;
      clip:rect(0 0 0 0);
      white-space:nowrap;
      border:0;
      padding:0;
      margin:-1px;
    }
  </style>
</head>
<body>

  <div class="topbar">
    <div class="topbar-inner">
      <div class="title">
        <h1>Practice audio (slow &amp; clear)</h1>
        <p>British voice • 1 pronunciation per phrase • Normal (default), Slow, Fast</p>
      </div>

      <div class="actions">
        <!-- Visible, simple info. (No transcript/dialect/stt fields shown.) -->
        <div class="pill" id="voicePill">Voice: aura-2-draco-en</div>
        <button class="btn secondary" id="newSessionBtn" title="Clears cached audio and resets playback">New session</button>
      </div>
    </div>
  </div>

  <div class="wrap">
    <div class="card">
      <table class="table">
        <thead class="thead">
          <tr>
            <th style="width:55%;">Word / phrase</th>
            <th style="width:45%;">Playback</th>
          </tr>
        </thead>
        <tbody class="tbody" id="rows"></tbody>
      </table>

      <div class="footer-note">
        Note: This uses a single British pronunciation per phrase (TTS). Slow/Fast are playback speeds (0.75× / 1.25×) so we don’t generate duplicates.
      </div>
    </div>

    <!-- Hidden shared audio element (one player for everything) -->
    <audio id="player" class="hidden-audio"></audio>
  </div>

  <script>
    /***********************
     * Internal config (not shown in UI)
     ***********************/
    const CONFIG = {
      ttsModel: "aura-2-draco-en",     // British voice model
      defaultRate: 1.0,               // Normal default
      rateSlow: 0.75,
      rateFast: 1.25,
      // Your TTS endpoint should return audio bytes (blob) for the text+model.
      // Adjust to match your backend.
      ttsEndpoint: "/api/tts",
      // Any extra fields you previously had (transcript/dialect/sttModel) intentionally removed from UI.
    };

    /***********************
     * Your phrases list
     * Replace / extend this array however you want.
     ***********************/
    const PHRASES = [
      "executive corps convened",
      "unsealed its",
      "precise",
      "the indictment was unsealed",
      "evidentiary record",
      "procedural compliance",
      "strategic communiqué"
    ];

    /***********************
     * State + caching
     ***********************/
    const audioCache = new Map(); // phrase -> objectURL
    const loadingSet = new Set(); // phrase currently being fetched

    const rowsEl = document.getElementById("rows");
    const player = document.getElementById("player");
    const newSessionBtn = document.getElementById("newSessionBtn");

    function escapeHtml(str){
      return str.replace(/[&<>"']/g, s => ({
        "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"
      }[s]));
    }

    function rateLabel(rate){
      if (rate === CONFIG.defaultRate) return "Normal";
      if (rate === CONFIG.rateSlow) return "Slow";
      if (rate === CONFIG.rateFast) return "Fast";
      return `${rate}×`;
    }

    function render(){
      rowsEl.innerHTML = PHRASES.map((phrase, idx) => {
        const safe = escapeHtml(phrase);
        const isLoading = loadingSet.has(phrase);
        return `
          <tr data-phrase="${safe}">
            <td>
              <div class="phrase">${safe}</div>
              <div class="sub">Single pronunciation • British</div>
            </td>
            <td>
              <div class="controls">
                <button class="mode" data-rate="${CONFIG.defaultRate}" data-phrase="${safe}" ${isLoading ? "disabled" : ""}>
                  <span class="dot"></span> ${rateLabel(CONFIG.defaultRate)}
                </button>
                <button class="mode" data-rate="${CONFIG.rateSlow}" data-phrase="${safe}" ${isLoading ? "disabled" : ""}>
                  <span class="dot"></span> ${rateLabel(CONFIG.rateSlow)}
                </button>
                <button class="mode" data-rate="${CONFIG.rateFast}" data-phrase="${safe}" ${isLoading ? "disabled" : ""}>
                  <span class="dot"></span> ${rateLabel(CONFIG.rateFast)}
                </button>

                <div class="status" aria-live="polite">
                  ${isLoading ? `<span class="spinner"></span><span>Generating…</span>` : ``}
                </div>
              </div>
            </td>
          </tr>
        `;
      }).join("");

      // Attach listeners after render
      rowsEl.querySelectorAll("button.mode").forEach(btn => {
        btn.addEventListener("click", async () => {
          const phrase = btn.getAttribute("data-phrase");
          const rate = Number(btn.getAttribute("data-rate"));
          await playPhrase(phrase, rate);
        });
      });
    }

    async function fetchTTSBlob(phrase){
      // Adjust this request shape to match your server.
      // Expect: audio bytes as response body.
      const res = await fetch(CONFIG.ttsEndpoint, {
        method: "POST",
        headers: { "Content-Type":"application/json" },
        body: JSON.stringify({
          text: phrase,
          model: CONFIG.ttsModel
        })
      });

      if (!res.ok){
        const msg = await safeReadText(res);
        throw new Error(`TTS failed (${res.status}): ${msg || "Unknown error"}`);
      }
      return await res.blob();
    }

    async function safeReadText(res){
      try { return await res.text(); } catch { return ""; }
    }

    async function ensureAudioUrl(phrase){
      if (audioCache.has(phrase)) return audioCache.get(phrase);
      if (loadingSet.has(phrase)) return null;

      loadingSet.add(phrase);
      render();

      try{
        const blob = await fetchTTSBlob(phrase);
        const url = URL.createObjectURL(blob);
        audioCache.set(phrase, url);
        return url;
      } finally {
        loadingSet.delete(phrase);
        render();
      }
    }

    async function playPhrase(phrase, rate){
      // Normal is default; user chooses rate via buttons.
      const url = await ensureAudioUrl(phrase);
      if (!url) return; // already loading

      // Stop any current playback
      try { player.pause(); } catch {}
      player.currentTime = 0;

      // Set source if different
      if (player.src !== url) player.src = url;

      // Playback rate: Option A (single audio, varying speeds)
      player.playbackRate = rate;

      // Play
      try{
        await player.play();
      } catch (e){
        console.error(e);
        alert("Playback failed. If you're on mobile, tap again or check if your browser blocks autoplay.");
      }
    }

    function newSession(){
      // Clear cache, revoke object URLs, stop playback
      try { player.pause(); } catch {}
      player.removeAttribute("src");
      player.load();

      for (const url of audioCache.values()){
        try { URL.revokeObjectURL(url); } catch {}
      }
      audioCache.clear();
      loadingSet.clear();
      render();
    }

    newSessionBtn.addEventListener("click", newSession);

    // Initial render
    render();
  </script>
</body>
</html>
