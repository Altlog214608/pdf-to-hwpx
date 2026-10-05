/* PDF → HWPX 웹 화면 */
(() => {
  "use strict";

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  // 한글 글꼴 -> 미리보기용 글꼴(사용자 PC에 한글 글꼴이 있으면 그걸 먼저 씀)
  const FONT_STACK = {
    "함초롬바탕": '"함초롬바탕","HCR Batang","Noto Serif KR",serif',
    "함초롬돋움": '"함초롬돋움","HCR Dotum","Noto Sans KR",sans-serif',
    "맑은 고딕": '"Malgun Gothic","맑은 고딕","Noto Sans KR",sans-serif',
    "바탕": '"Batang","바탕","Noto Serif KR",serif',
    "돋움": '"Dotum","돋움","Noto Sans KR",sans-serif',
    "나눔명조": '"Nanum Myeongjo","나눔명조",serif',
    "나눔고딕": '"Nanum Gothic","나눔고딕",sans-serif',
  };
  const PAGE_W = 59528, VIEW_H = 52000;
  const MASTER = { left: 4251, right: 4251, bodyTop: 4251 + 4251, tableW: 54599, tableTop: (84186 - 75791) / 2, headH: 2782 };
  const PLAIN = { left: 2268, right: 2268, bodyTop: 2268 + 1134 };
  const PREF_KEY = "pdf2hwpx:prefs";

  const state = {
    cfg: { fonts: Object.keys(FONT_STACK), download_ttl_min: 10 },
    job: null,          // 서버 응답(분석 결과)
    logoURL: null,      // 로고 미리보기 URL
    logoSize: null,
    academyMode: "text",
    converted: false,
    downloaded: false,
    timer: null,
    dirty: false,
  };

  // ------------------------------------------------------------ utils --
  const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  let toastTimer;
  function toast(msg, isError = false) {
    const t = $("#toast");
    t.textContent = msg;
    t.classList.toggle("is-error", isError);
    t.classList.add("is-show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove("is-show"), isError ? 5200 : 3200);
  }
  function setStep(n) {
    $$(".steps li").forEach((li) => {
      const k = +li.dataset.step;
      li.classList.toggle("is-active", k === n);
      li.classList.toggle("is-done", k < n);
    });
  }
  function showStage(id) {
    $$(".stage").forEach((s) => s.classList.toggle("is-visible", s.id === id));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  async function api(path, opts = {}) {
    const res = await fetch(path, opts);
    let data = null;
    try { data = await res.json(); } catch (_) { /* 본문 없음 */ }
    if (!res.ok) {
      const err = new Error((data && data.detail) || `요청이 실패했습니다 (${res.status})`);
      err.status = res.status;
      throw err;
    }
    return data;
  }
  function loadPrefs() {
    try { return JSON.parse(localStorage.getItem(PREF_KEY) || "{}"); } catch (_) { return {}; }
  }
  function savePrefs() {
    try {
      localStorage.setItem(PREF_KEY, JSON.stringify({
        academy: $("#in-academy").value, academyMode: state.academyMode === "logo" ? "text" : state.academyMode,
        font: $("#in-font").value, titleFont: $("#in-title-font").value, size: $("#in-size").value,
        frame: $("#in-frame").checked,
      }));
    } catch (_) { /* 저장 안 되는 환경 */ }
  }

  // ---------------------------------------------------------- drag & drop --
  let dragDepth = 0;
  const overlay = $("#drop-overlay");
  const hasFiles = (e) => e.dataTransfer && [...e.dataTransfer.types].includes("Files");
  window.addEventListener("dragenter", (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault();
    dragDepth++;
    overlay.classList.add("is-active");
  });
  // 창 밖으로 끌고 나가는 등 dragleave가 빠지는 경우를 위한 안전장치: dragover가 끊기면 닫는다
  let dragWatch = 0;
  const hideOverlay = () => { dragDepth = 0; overlay.classList.remove("is-active"); };
  window.addEventListener("dragover", (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault();
    clearTimeout(dragWatch);
    dragWatch = setTimeout(hideOverlay, 400);
  });
  window.addEventListener("dragleave", (e) => {
    if (!hasFiles(e)) return;
    dragDepth = Math.max(0, dragDepth - 1);
    if (dragDepth === 0) overlay.classList.remove("is-active");
  });
  window.addEventListener("drop", (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault();
    dragDepth = 0;
    overlay.classList.remove("is-active");
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  });
  $("#dropzone").addEventListener("click", () => $("#file-input").click());
  $("#file-input").addEventListener("change", (e) => { const f = e.target.files[0]; if (f) handleFile(f); e.target.value = ""; });

  async function handleFile(file) {
    if (!/\.pdf$/i.test(file.name) && file.type !== "application/pdf") {
      toast("PDF 파일만 올릴 수 있어요.", true);
      return;
    }
    if (file.size > state.cfg.max_mb * 1024 * 1024) {
      toast(`파일이 너무 커요 (최대 ${state.cfg.max_mb}MB).`, true);
      return;
    }
    if (state.job) {
      if (state.converted && !state.downloaded && !confirm("변환한 파일을 아직 내려받지 않았어요. 새 PDF로 바꿀까요?")) return;
      await discardJob();
    }
    showStage("stage-upload");
    setStep(1);
    const box = $("#upload-progress");
    box.hidden = false;
    $(".up-name", box).textContent = file.name;
    $(".up-state", box).textContent = "업로드 중… 0%";
    const bar = $(".bar", box);
    bar.classList.remove("is-indeterminate");
    $("i", bar).style.width = "0";
    try {
      const job = await uploadWithProgress(file, (p) => {
        $(".up-state", box).textContent = p < 1 ? `업로드 중… ${Math.round(p * 100)}%` : "문서 구조 분석 중…";
        if (p >= 1) bar.classList.add("is-indeterminate");
        else $("i", bar).style.width = `${p * 100}%`;
      });
      box.hidden = true;
      if (job.text_layer && job.text_layer.status === "scanned") {
        await api(`/api/jobs/${job.id}`, { method: "DELETE" }).catch(() => {});
        toast("글자 정보가 없는 스캔본 PDF예요. 글자를 긁을 수 있는 PDF만 변환할 수 있어요.", true);
        return;
      }
      if (job.text_layer && job.text_layer.status === "garbled") {
        toast("일부 글자가 깨진 PDF일 수 있어요. 결과를 꼭 확인해 주세요.", true);
      }
      openWorkspace(job);
    } catch (err) {
      box.hidden = true;
      toast(err.message, true);
    }
  }

  function uploadWithProgress(file, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const fd = new FormData();
      fd.append("file", file);
      xhr.open("POST", "/api/jobs");
      xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(e.loaded / e.total); };
      xhr.upload.onload = () => onProgress(1);
      xhr.onload = () => {
        let data = null;
        try { data = JSON.parse(xhr.responseText); } catch (_) { /* */ }
        if (xhr.status >= 200 && xhr.status < 300) resolve(data);
        else reject(new Error((data && data.detail) || `업로드에 실패했어요 (${xhr.status})`));
      };
      xhr.onerror = () => reject(new Error("네트워크 오류로 업로드하지 못했어요."));
      xhr.send(fd);
    });
  }

  // ------------------------------------------------------------ workspace --
  function openWorkspace(job) {
    state.job = job;
    state.converted = false;
    state.downloaded = false;
    $("#file-chip").textContent = job.filename;
    $("#source-img").src = job.page1 + `?t=${Date.now()}`;
    const st = job.stats || {};
    $("#source-stats").innerHTML = [
      ["쪽", st.pages], ["문제", st.questions], ["지문", st.passages], ["정답", st.answers],
    ].filter(([, v]) => v != null).map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("");
    const chips = $("#title-chips");
    const cands = job.title_candidates || [];
    chips.innerHTML = cands.length ? `<span class="label">PDF에서 찾은 제목</span>` +
      cands.map((c) => `<button type="button" data-title="${esc(c)}">${esc(c)}</button>`).join("") : "";
    if (!$("#in-title").value && cands[0]) $("#in-title").value = cands[0];
    $("#result").hidden = true;
    $("#actions").hidden = false;
    showStage("stage-work");
    setStep(2);
    renderPreview();
  }

  $("#title-chips").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-title]");
    if (!b) return;
    const cur = $("#in-title").value;
    const prefix = (cur.match(/^\s*\[[^\]]*\]\s*/) || [""])[0]; // "[중간 대비] " 같은 머리말은 유지
    $("#in-title").value = (prefix + b.dataset.title).trim();
    onSettingsChange();
  });

  async function discardJob() {
    if (!state.job) return;
    const id = state.job.id;
    state.job = null;
    stopTimer();
    try { await fetch(`/api/jobs/${id}`, { method: "DELETE" }); } catch (_) { /* */ }
  }
  $("#btn-new").addEventListener("click", async () => {
    if (state.converted && !state.downloaded && !confirm("변환한 파일을 아직 내려받지 않았어요. 새 PDF를 올릴까요?")) return;
    await discardJob();
    showStage("stage-upload");
    setStep(1);
  });
  $("#btn-source-expand").addEventListener("click", () => {
    const lb = $("#lightbox");
    $("img", lb).src = $("#source-img").src;
    lb.hidden = false;
  });
  $("#lightbox").addEventListener("click", (e) => { e.currentTarget.hidden = true; });

  // ------------------------------------------------------------- settings --
  function fillFonts() {
    const fonts = state.cfg.fonts;
    for (const sel of [$("#in-font"), $("#in-title-font")]) {
      sel.innerHTML = fonts.map((f) => `<option value="${esc(f)}" style="font-family:${esc(FONT_STACK[f] || "inherit")}">${esc(f)}</option>`).join("");
    }
    const p = loadPrefs();
    $("#in-font").value = fonts.includes(p.font) ? p.font : "함초롬바탕";
    $("#in-title-font").value = fonts.includes(p.titleFont) ? p.titleFont : "함초롬돋움";
    if (p.size) $("#in-size").value = p.size;
    if (typeof p.frame === "boolean") $("#in-frame").checked = p.frame;
    if (p.academy) $("#in-academy").value = p.academy;
    setAcademyMode(p.academyMode || "text", false);
    $("#out-size").textContent = (+$("#in-size").value).toFixed(1).replace(/\.0$/, "");
  }

  function setAcademyMode(mode, render = true) {
    state.academyMode = mode;
    $$("[data-academy-mode]").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.academyMode === mode)));
    $$("[data-academy-pane]").forEach((p) => { p.hidden = p.dataset.academyPane !== mode; });
    if (render) onSettingsChange();
  }
  $$("[data-academy-mode]").forEach((b) => b.addEventListener("click", () => setAcademyMode(b.dataset.academyMode)));

  ["#in-academy", "#in-title", "#in-font", "#in-title-font", "#in-size", "#in-frame"].forEach((sel) => {
    $(sel).addEventListener("input", onSettingsChange);
    $(sel).addEventListener("change", onSettingsChange);
  });
  $$("[data-size-step]").forEach((b) => b.addEventListener("click", () => {
    const r = $("#in-size");
    r.value = Math.min(+r.max, Math.max(+r.min, +r.value + +b.dataset.sizeStep));
    onSettingsChange();
  }));

  function onSettingsChange() {
    $("#out-size").textContent = (+$("#in-size").value).toFixed(1).replace(/\.0$/, "");
    savePrefs();
    renderPreview();
    if (state.converted) markStale();
  }

  // 로고
  $("#btn-logo").addEventListener("click", () => $("#logo-input").click());
  $("#logo-input").addEventListener("change", async (e) => {
    const f = e.target.files[0];
    e.target.value = "";
    if (!f || !state.job) return;
    const fd = new FormData();
    fd.append("file", f);
    try {
      const r = await api(`/api/jobs/${state.job.id}/logo`, { method: "POST", body: fd });
      if (state.logoURL) URL.revokeObjectURL(state.logoURL);
      state.logoURL = URL.createObjectURL(f);
      state.logoSize = [r.width, r.height];
      $("#logo-thumb").src = state.logoURL;
      $("#logo-thumb").hidden = false;
      $("#btn-logo-remove").hidden = false;
      onSettingsChange();
    } catch (err) { toast(err.message, true); }
  });
  $("#btn-logo-remove").addEventListener("click", async () => {
    if (state.job) await api(`/api/jobs/${state.job.id}/logo`, { method: "DELETE" }).catch(() => {});
    state.logoURL = null;
    state.logoSize = null;
    $("#logo-thumb").hidden = true;
    $("#btn-logo-remove").hidden = true;
    onSettingsChange();
  });

  function currentOptions() {
    const mode = state.academyMode;
    return {
      body_font: $("#in-font").value,
      title_font: $("#in-title-font").value,
      body_size: +$("#in-size").value,
      academy_name: mode === "text" ? $("#in-academy").value.trim() : "",
      use_logo: mode === "logo" && !!state.logoURL,
      title: $("#in-title").value.trim(),
      frame: $("#in-frame").checked,
    };
  }

  // ------------------------------------------------------------- preview --
  function runsHTML(p) {
    if (!p || p.kind !== "text") return "";
    return p.runs.map((r) => {
      let t = esc(r.t);
      if (r.u) t = `<u>${t}</u>`;
      if (r.b) t = `<b>${t}</b>`;
      return t;
    }).join("");
  }
  function paraHTML(p) {
    if (p.kind === "blank") return `<div class="pv-blank"></div>`;
    if (p.kind !== "text") return "";
    const cls = p.align === "RIGHT" ? " pv-right" : p.align === "CENTER" ? " pv-center" : "";
    return `<p class="pv-p${cls}">${runsHTML(p)}</p>`;
  }

  function renderPreview() {
    const paper = $("#paper");
    const pw = paper.clientWidth || 680;
    const u = pw / PAGE_W;
    paper.style.setProperty("--pw", `${pw}px`);
    const o = currentOptions();
    const hasAcademy = (o.academy_name || o.use_logo);
    const hasHead = hasAcademy || !!o.title;
    const useMaster = hasHead || o.frame;
    const g = useMaster ? MASTER : PLAIN;
    const titlePx = 14 * 100 * u;

    // 바탕쪽: 머리 칸 + 바깥 테두리
    const head = $("#mp-head"), frame = $("#mp-frame");
    const tx = (PAGE_W - MASTER.tableW) / 2;
    frame.hidden = !o.frame;
    Object.assign(frame.style, { left: `${tx * u}px`, top: `${MASTER.tableTop * u}px`, width: `${MASTER.tableW * u}px`, height: `${75791 * u}px` });
    head.hidden = !hasHead;
    Object.assign(head.style, { left: `${tx * u}px`, top: `${MASTER.tableTop * u}px`, width: `${MASTER.tableW * u}px`, height: `${MASTER.headH * u}px` });
    const ac = $("#mp-academy"), ti = $("#mp-title");
    let aw = 0;
    if (state.academyMode !== "none") {
      if (o.use_logo && state.logoSize) {
        aw = Math.max(6000, Math.min(20000, (MASTER.headH - 600) * state.logoSize[0] / state.logoSize[1] + 900));
        ac.innerHTML = `<img src="${state.logoURL}" alt="학원 로고">`;
        ac.classList.remove("is-empty");
      } else if (o.academy_name) {
        aw = Math.max(6000, Math.min(20000, o.academy_name.length * 14 * 100 * 0.98 + 1600));
        ac.textContent = o.academy_name;
        ac.classList.remove("is-empty");
      } else {
        aw = 12000;
        ac.textContent = state.academyMode === "logo" ? "로고 그림 선택" : "학원 이름 입력";
        ac.classList.add("is-empty");
      }
    }
    ac.hidden = state.academyMode === "none";
    if (!hasHead && state.academyMode !== "none") head.hidden = false; // 비어 있어도 눌러서 입력할 수 있게 표시
    ac.style.width = `${aw * u}px`;
    ac.style.fontSize = `${titlePx}px`;
    ac.style.fontFamily = FONT_STACK[o.title_font] || "inherit";
    ti.textContent = o.title || "시험 제목 입력";
    ti.classList.toggle("is-empty", !o.title);
    ti.style.fontSize = `${titlePx}px`;
    ti.style.fontFamily = FONT_STACK[o.title_font] || "inherit";
    ti.style.borderLeftWidth = state.academyMode === "none" ? "0" : "";

    // 본문 2단
    const cols = $("#body-cols");
    Object.assign(cols.style, {
      left: `${g.left * u}px`, top: `${g.bodyTop * u}px`, width: `${(PAGE_W - g.left - g.right) * u}px`,
      height: `${(VIEW_H - g.bodyTop) * u}px`, columnGap: `${2268 * u}px`,
      fontSize: `${o.body_size * 100 * u}px`, fontFamily: FONT_STACK[o.body_font] || "serif",
    });
    const s = (state.job && state.job.sample) || {};
    let html = "";
    if (s.passage) {
      html += `<p class="pv-guide">${esc(s.passage.guide)}</p>`;
      const inner = s.passage.paras.map(paraHTML).join("") + (s.passage.more ? `<p class="pv-p" style="color:#999">⋯</p>` : "");
      html += s.passage.boxed ? `<div class="pv-box">${inner}</div>` : inner;
    }
    if (s.question) {
      html += `<p class="pv-stem">${runsHTML(s.question.stem)}</p>`;
      for (const b of s.question.blocks || []) {
        html += `<div class="pv-aux">${b.title ? `<div class="pv-aux-title">${esc(b.title)}</div>` : ""}${b.paras.map(paraHTML).join("")}</div>`;
      }
      html += (s.question.choices || []).map((c) => `<p class="pv-choice">${runsHTML(c)}</p>`).join("");
    }
    cols.innerHTML = html;
  }
  window.addEventListener("resize", () => { if (state.job) renderPreview(); });

  function flashField(input) {
    const field = input.closest(".field");
    input.focus();
    if (field) { field.classList.remove("is-flash"); void field.offsetWidth; field.classList.add("is-flash"); }
  }
  $("#mp-academy").addEventListener("click", () => {
    if (state.academyMode === "logo") $("#logo-input").click();
    else { if (state.academyMode === "none") setAcademyMode("text"); flashField($("#in-academy")); }
  });
  $("#mp-title").addEventListener("click", () => flashField($("#in-title")));

  // ------------------------------------------------------------- convert --
  $("#btn-convert").addEventListener("click", convertNow);
  async function convertNow() {
    if (!state.job) return;
    const btn = $("#btn-convert");
    btn.disabled = true;
    btn.classList.add("is-busy");
    $(".btn-label", btn).textContent = "변환하는 중…";
    try {
      const r = await api(`/api/jobs/${state.job.id}/convert`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(currentOptions()),
      });
      showResult(r);
    } catch (err) {
      if (err.status === 404) {
        toast("작업 시간이 지나 파일이 삭제됐어요. PDF를 다시 올려 주세요.", true);
        state.job = null;
        showStage("stage-upload");
        setStep(1);
      } else toast(err.message, true);
    } finally {
      btn.disabled = false;
      btn.classList.remove("is-busy");
      $(".btn-label", btn).textContent = "HWPX로 변환하기";
    }
  }

  function showResult(r) {
    state.converted = true;
    state.downloaded = false;
    state.dirty = false;
    const res = $("#result");
    res.classList.remove("is-expired");
    $("#result-name").textContent = r.filename;
    $("#result-meta").textContent = `${(r.size / 1024).toFixed(0)}KB · ${r.status === "PASS" ? "구조 검사 통과" : r.status === "WARN" ? "확인이 필요한 부분이 있어요" : "일부 문제가 있어요"}`;
    const sm = r.summary || {};
    $("#result-summary").innerHTML = [
      ["문제", sm.questions != null ? `${sm.questions}개` : null],
      ["객관식/서술형", sm.objective != null ? `${sm.objective}/${sm.subjective}` : null],
      ["박스", sm.boxes], ["그림", sm.pictures], ["정답", sm.answers],
      ["원문 반영", sm.coverage != null ? `${Math.round(sm.coverage * 100)}%` : null],
    ].filter(([, v]) => v != null).map(([k, v]) => `<li>${k}<b>${v}</b></li>`).join("");
    const a = $("#btn-download");
    a.href = r.download_url;
    a.setAttribute("download", r.filename);
    res.hidden = false;
    $("#actions").hidden = true;
    setStep(3);
    startTimer(r.seconds_left);
    res.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
  $("#btn-download").addEventListener("click", () => { state.downloaded = true; });

  function markStale() {
    if (state.dirty) return;
    state.dirty = true;
    $("#actions").hidden = false;
    $(".btn-label", $("#btn-convert")).textContent = "바뀐 설정으로 다시 변환";
    setStep(2);
  }

  function startTimer(seconds) {
    stopTimer();
    const total = Math.max(1, seconds);
    const end = Date.now() + seconds * 1000;
    const tick = () => {
      const left = Math.max(0, Math.round((end - Date.now()) / 1000));
      const mm = String(Math.floor(left / 60)).padStart(2, "0"), ss = String(left % 60).padStart(2, "0");
      $("#timer-fill").style.width = `${(left / total) * 100}%`;
      if (left <= 0) {
        stopTimer();
        $("#result").classList.add("is-expired");
        $("#timer-text").textContent = "다운로드 시간이 지났어요. 다시 변환하면 새 링크가 생겨요.";
        $("#actions").hidden = false;
        $(".btn-label", $("#btn-convert")).textContent = "다시 변환하기";
        state.converted = false;
        return;
      }
      $("#timer-text").textContent = `다운로드 가능 시간 ${mm}:${ss}`;
    };
    tick();
    state.timer = setInterval(tick, 1000);
  }
  function stopTimer() { if (state.timer) clearInterval(state.timer); state.timer = null; }

  // 페이지를 떠나면 서버의 작업 파일을 지운다
  window.addEventListener("beforeunload", (e) => {
    if (state.converted && !state.downloaded) { e.preventDefault(); e.returnValue = ""; }
  });
  window.addEventListener("pagehide", () => {
    if (state.job) navigator.sendBeacon(`/api/jobs/${state.job.id}/delete`);
  });

  // --------------------------------------------------------------- init --
  (async () => {
    try {
      const cfg = await api("/api/config");
      state.cfg = cfg;
      $$("[data-cfg]").forEach((el) => { el.textContent = cfg[el.dataset.cfg]; });
    } catch (_) { /* 기본값 사용 */ }
    fillFonts();
  })();
})();
