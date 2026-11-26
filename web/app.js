const state = {
  sb: null,
  runs: [],
  files: {},
  serverApi: false,
  activeVideo: "vertical",
};

function el(id) {
  return document.getElementById(id);
}

function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function setupTabs() {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      el(`tab-${btn.dataset.tab}`).classList.add("active");
    });
  });
}

async function fetchJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function loadState() {
  try {
    const data = await fetchJson("/api/state");
    state.sb = data.storyboard;
    state.runs = data.runs || [];
    state.files = data.files || {};
    state.serverApi = true;
    el("server-mode").textContent = "Connected to local studio server (pipeline.web)";
  } catch {
    // Static fallback (GitHub Pages / Hugging Face Static Space)
    const sb = await fetchJson("../storyboard.json").catch(() => fetchJson("storyboard.json"));
    const runsTxt = await fetch("../runs.jsonl").then((r) => (r.ok ? r.text() : "")).catch(() => "");
    state.sb = sb;
    state.runs = runsTxt.split("\n").filter(Boolean).map((l) => JSON.parse(l));
    state.files = {
      vertical: "../outputs/final/film_vertical_9x16.mp4",
      horizontal: "../outputs/final/film_horizontal_16x9.mp4",
      radio: "../outputs/final/radio_cut.mp4",
      srt: "../outputs/final/film.srt",
      basePrefix: "../",
    };
    state.serverApi = false;
    el("server-mode").textContent = "Static showcase mode (read-only)";
  }
  renderAll();
}

function renderAll() {
  renderHero();
  renderVideo();
  renderShots();
  renderRefsAndMusic();
  renderTelemetry();
}

function renderHero() {
  const sb = state.sb;
  if (!sb) return;
  el("film-title").textContent = sb.title;
  el("hero-title").textContent = sb.title;
  el("hero-logline").textContent = sb.logline;
  el("aud-who").textContent = sb.audience?.who || "";
  el("aud-where").textContent = sb.audience?.where || "";
  el("aud-feel").textContent = sb.audience?.feeling_at_end || "";

  const totalDur = sb.shots.reduce((a, s) => a + Number(s.duration_s || 0), 0) + Number(sb.end_card?.duration_s || 0);
  const judgeRows = state.runs.filter((r) => r.stage === "judge" && r.scores);
  const meanPerson = judgeRows.length
    ? (judgeRows.reduce((a, r) => a + (r.scores.same_person || 0), 0) / judgeRows.length).toFixed(2)
    : "—";
  const meanStyle = judgeRows.length
    ? (judgeRows.reduce((a, r) => a + (r.scores.same_style || 0), 0) / judgeRows.length).toFixed(2)
    : "—";

  const badges = [
    `<span class="badge amber">Made with AI</span>`,
    `<span class="badge">${escapeHtml(sb.language?.narration_name)} → ${escapeHtml(sb.language?.subtitle_language)} Subs</span>`,
    `<span class="badge">${sb.shots.length} Shots · ~${totalDur}s</span>`,
    `<span class="badge ok">Character: ${escapeHtml(sb.characters?.[0]?.name || "—")}</span>`,
  ];
  el("film-badges").innerHTML = badges.join("");

  const realRuns = state.runs.filter((r) => !r.dry_run && r.stage !== "smoke" && r.status === "ok");
  const gpuMin = realRuns.reduce((a, r) => a + Number(r.gpu_minutes || 0), 0);
  el("hero-stats").innerHTML = `
    <div class="stat-box"><div class="val">${meanPerson} / 5</div><div class="lbl">Mean identity score</div></div>
    <div class="stat-box"><div class="val">${meanStyle} / 5</div><div class="lbl">Mean style score</div></div>
    <div class="stat-box"><div class="val">${realRuns.length}</div><div class="lbl">Successful model calls</div></div>
    <div class="stat-box"><div class="val">${gpuMin.toFixed(2)} m</div><div class="lbl">Measured GPU minutes</div></div>
  `;

  if (state.serverApi) {
    el("assemble-btn").style.display = "inline-flex";
  }
  if (state.files.srt) {
    el("download-srt").style.display = "inline-flex";
    el("download-srt").href = state.files.srt;
  }
}

function renderVideo() {
  const frame = el("video-frame");
  const isWide = state.activeVideo !== "vertical";
  frame.classList.toggle("wide", isWide);
  const url = state.files[state.activeVideo];
  if (!url) {
    const label = state.activeVideo === "radio" ? "radio_cut.mp4" : state.activeVideo === "vertical" ? "film_vertical_9x16.mp4" : "film_horizontal_16x9.mp4";
    frame.innerHTML = `<div class="empty-player"><strong>${escapeHtml(label)}</strong> is not generated yet.<br><br>Click <em>Assemble Film Now</em> (or run <span class="mono">make film</span>) once clips/music are ready.</div>`;
    return;
  }
  frame.innerHTML = `<video controls playsinline preload="metadata" src="${escapeHtml(url)}"></video>`;
}

function renderShots() {
  const sb = state.sb;
  if (!sb) return;
  const judgeByShot = {};
  for (const r of state.runs) {
    if (r.stage === "judge" && r.shot && r.scores) judgeByShot[r.shot] = r.scores;
  }
  const prefix = state.files.basePrefix || "/";
  el("shot-grid").innerHTML = sb.shots.map((s) => {
    const j = judgeByShot[s.id];
    const hasClip = (state.files.clips || []).includes(s.id);
    const kfUrl = `${prefix}outputs/keyframes/${s.id}.jpg`;
    const wavUrl = `${prefix}outputs/narration/${s.id}.wav`;
    const scoreTag = j ? `<span class="shot-score">ID ${j.same_person ?? "—"}/5 · Style ${j.same_style}/5</span>` : "";
    const motionBadge = hasClip ? "Video Clip" : `Ken Burns (${s.camera})`;
    return `
      <article class="shot-card">
        <div class="shot-media">
          <img src="${kfUrl}" alt="${escapeHtml(s.id)} keyframe" loading="lazy" onerror="this.style.opacity=0.2">
          <span class="shot-tag">${escapeHtml(s.id)} · ${escapeHtml(s.shot_size)} · ${s.duration_s}s</span>
          ${scoreTag}
        </div>
        <div class="shot-body">
          <div class="amharic">${escapeHtml(s.narration.text)}</div>
          <div class="en-sub">${escapeHtml(s.narration.translation_en)}</div>
          <div class="reason">${escapeHtml(s.reason)}</div>
          <div class="badges" style="margin:0.2rem 0;">
            <span class="badge">${escapeHtml(motionBadge)}</span>
            <span class="badge">Cue ${escapeHtml(s.music_cue)}</span>
          </div>
          <audio controls preload="none" src="${wavUrl}"></audio>
        </div>
      </article>
    `;
  }).join("");
}

function renderRefsAndMusic() {
  const sb = state.sb;
  if (!sb) return;
  const ch = sb.characters?.[0];
  if (ch) el("char-name").textContent = ch.name;
  const prefix = state.files.basePrefix || "/";
  const refs = state.files.references || [`${prefix}outputs/reference/yonas_1.jpg`];
  el("ref-strip").innerHTML = refs.map((url) => {
    const name = url.split("/").pop();
    const isGolden = ch?.golden_reference && url.endsWith(ch.golden_reference);
    return `
      <div class="ref-card ${isGolden ? "golden" : ""}">
        <img src="${escapeHtml(url)}" alt="${escapeHtml(name)}" loading="lazy">
        <div class="cap">
          <span class="mono">${escapeHtml(name)}</span>
          ${isGolden ? '<span class="badge amber">Golden</span>' : ""}
        </div>
      </div>
    `;
  }).join("");

  const cands = state.files.musicCandidates || [];
  const chosen = state.files.chosenMusic || {};
  if (!cands.length) {
    el("music-grid").innerHTML = `<div class="card">No registered ACE-Step candidates found in <span class="mono">outputs/music/candidates/</span> yet.</div>`;
    return;
  }
  el("music-grid").innerHTML = cands.map((item) => {
    const isChosen = chosen[item.cue] === item.name;
    return `
      <div class="music-card ${isChosen ? "chosen" : ""}">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <strong>Cue ${escapeHtml(item.cue)} · <span class="mono">${escapeHtml(item.name)}</span></strong>
          ${isChosen ? '<span class="badge ok">Chosen</span>' : ""}
        </div>
        <audio controls preload="none" src="${escapeHtml(item.url)}"></audio>
        ${state.serverApi ? `<button class="btn" onclick="chooseMusic('${escapeHtml(item.cue)}', '${escapeHtml(item.relPath)}')">Use for ${escapeHtml(item.cue)}</button>` : ""}
      </div>
    `;
  }).join("");
}

window.chooseMusic = async function (cue, relPath) {
  const why = prompt(`Why are you choosing ${relPath.split("/").pop()} for ${cue}?`);
  if (!why) return;
  const st = el("music-status");
  st.style.display = "block";
  st.textContent = `Saving ${cue} choice...`;
  const r = await fetch("/api/select-music", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cue, file: relPath, why }),
  });
  const data = await r.json();
  st.textContent = r.ok ? `Chosen ${relPath} for ${cue}.` : `Error: ${data.error}`;
  await loadState();
};

function renderTelemetry() {
  const rows = state.runs.filter((r) => !r.dry_run && r.stage !== "smoke");
  const groups = {};
  for (const r of rows) {
    if (!groups[r.stage]) groups[r.stage] = [];
    groups[r.stage].push(r);
  }
  el("telemetry-body").innerHTML = Object.entries(groups).map(([stage, rs]) => {
    const models = [...new Set(rs.map((r) => r.model))].join(", ");
    const ok = rs.filter((r) => r.status === "ok").length;
    const meanLat = (rs.reduce((a, r) => a + Number(r.latency_s || 0), 0) / rs.length).toFixed(1);
    const gpuMin = rs.reduce((a, r) => a + Number(r.gpu_minutes || 0), 0).toFixed(2);
    return `
      <tr>
        <td><strong>${escapeHtml(stage)}</strong></td>
        <td class="mono">${escapeHtml(models)}</td>
        <td>${rs.length}</td>
        <td>${ok}</td>
        <td>${rs.length - ok}</td>
        <td>${meanLat} s</td>
        <td>${gpuMin} m</td>
      </tr>
    `;
  }).join("") || `<tr><td colspan="7">No runs logged yet.</td></tr>`;
}

function setupControls() {
  document.querySelectorAll("[data-video]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-video]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.activeVideo = btn.dataset.video;
      renderVideo();
    });
  });

  el("assemble-btn").addEventListener("click", async () => {
    const btn = el("assemble-btn");
    const st = el("assemble-status");
    btn.disabled = true;
    st.style.display = "block";
    st.textContent = "Assembling 9:16 and 16:9 films with FFmpeg (this takes ~20-60s)...";
    try {
      const r = await fetch("/api/assemble", { method: "POST" });
      const data = await r.json();
      st.textContent = r.ok ? `Done! Built vertical and horizontal MP4s.` : `Error: ${data.error}`;
      await loadState();
    } finally {
      btn.disabled = false;
    }
  });

  el("download-story-btn").addEventListener("click", () => {
    const [langName] = el("f-lang").value.split("|");
    const md = `# ${el("f-title").value || "Family Story"}\n\n- **Audience:** ${el("f-audience").value}\n- **Language:** ${langName}\n- **Voice:** ${el("f-voice").value}\n- **Real person appears:** ${el("f-real").checked}\n\n${el("f-story").value}\n`;
    const blob = new Blob([md], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "story.md";
    a.click();
  });

  el("family-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const st = el("family-status");
    st.style.display = "block";
    const [langName, langCode] = el("f-lang").value.split("|");
    const payload = {
      title: el("f-title").value,
      audience: el("f-audience").value,
      language_name: langName,
      language_code: langCode,
      voice: el("f-voice").value,
      story: el("f-story").value,
      real_person: el("f-real").checked,
    };
    if (!state.serverApi) {
      st.textContent = "Running in static mode — click 'Download story.md' and run `python -m pipeline.script story.md` locally.";
      return;
    }
    el("draft-btn").disabled = true;
    st.textContent = "Drafting storyboard.draft.json via Gemini...";
    try {
      const r = await fetch("/api/draft-story", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await r.json();
      st.textContent = r.ok ? `Wrote ${data.path} (${data.shots} shots). Review it before replacing storyboard.json.` : `Error: ${data.error}`;
    } finally {
      el("draft-btn").disabled = false;
    }
  });
}

setupTabs();
setupControls();
loadState();
