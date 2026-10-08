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
    job: null,          // 지금 미리보기 중인 파일의 서버 응답(분석 결과)
    files: [],          // 올린 파일들: { job, title, status, result, error }
    sel: 0,             // 미리보기 중인 파일 번호
    multiMode: "each",  // 여러 파일: "each"(따로) | "merge"(하나로 합치기)
    mergeTitle: null,   // 통합본 제목(처음 합치기를 고를 때 첫 파일 제목으로)
    bundleId: null,     // 통합본/ZIP 묶음 작업 id
    logoURL: null,      // 로고 미리보기 URL
    logoSize: null,
    academyMode: "text",
    titleColor: "#000000",
    answerMode: "end",   // "end" | "endnote"
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
        frame: $("#in-frame").checked, titleColor: state.titleColor, answerMode: state.answerMode,
        autoNum: $("#in-autonum").checked,
      }));
    } catch (_) { /* 저장 안 되는 환경 */ }
  }

  // ---------------------------------------------------------------- theme --
  const darkMQ = window.matchMedia("(prefers-color-scheme: dark)");
  const isDark = () => (document.documentElement.dataset.theme || (darkMQ.matches ? "dark" : "light")) === "dark";
  function syncThemeLabel() {
    $("#btn-theme").setAttribute("aria-label", isDark() ? "밝은 화면으로 바꾸기" : "어두운 화면으로 바꾸기");
  }
  $("#btn-theme").addEventListener("click", () => {
    const next = isDark() ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("pdf2hwpx:theme", next); } catch (_) { /* 저장 안 되는 환경 */ }
    syncThemeLabel();
  });
  darkMQ.addEventListener("change", syncThemeLabel);
  syncThemeLabel();

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
    const fs = [...e.dataTransfer.files];
    if (fs.length) handleFiles(fs, state.files.length > 0);
  });
  let addMode = false;
  $("#dropzone").addEventListener("click", () => { addMode = false; $("#file-input").click(); });
  $("#btn-add").addEventListener("click", () => { addMode = true; $("#file-input").click(); });
  $("#file-input").addEventListener("change", (e) => {
    const fs = [...e.target.files];
    e.target.value = "";
    if (fs.length) handleFiles(fs, addMode && state.files.length > 0);
  });

  const maxFiles = () => state.cfg.max_files || 10;
  const hasUndownloaded = () => state.converted && !state.downloaded;

  // 여러 파일을 하나씩 올린다. append: 지금 목록 뒤에 더하기(작업 화면에서 끌어 놓기/추가 버튼)
  async function handleFiles(list, append) {
    let files = list.filter((f) => /\.pdf$/i.test(f.name) || f.type === "application/pdf");
    if (files.length < list.length) toast("PDF가 아닌 파일은 뺐어요.", true);
    const big = files.filter((f) => f.size > state.cfg.max_mb * 1024 * 1024);
    if (big.length) {
      toast(`너무 큰 파일은 뺐어요 (최대 ${state.cfg.max_mb}MB): ${big.map((f) => f.name).join(", ")}`, true);
      files = files.filter((f) => !big.includes(f));
    }
    if (!files.length) return;
    if (!append && state.files.length) {
      if (hasUndownloaded() && !confirm("변환한 파일을 아직 내려받지 않았어요. 새 PDF로 바꿀까요?")) return;
      await discardAll();
    }
    const room = maxFiles() - state.files.length;
    if (files.length > room) {
      toast(`한 번에 ${maxFiles()}개까지 올릴 수 있어요. 앞의 ${Math.max(0, room)}개만 올릴게요.`, true);
      files = files.slice(0, Math.max(0, room));
      if (!files.length) return;
    }
    const inWork = state.files.length > 0;
    const box = $("#upload-progress");
    if (!inWork) {
      showStage("stage-upload");
      setStep(1);
      box.hidden = false;
    }
    const bar = $(".bar", box);
    for (let k = 0; k < files.length; k++) {
      const file = files[k];
      const tag = files.length > 1 ? `(${k + 1}/${files.length}) ` : "";
      $(".up-name", box).textContent = tag + file.name;
      bar.classList.remove("is-indeterminate");
      $("i", bar).style.width = "0";
      if (inWork) toast(`${tag}${file.name} 올리는 중…`);
      try {
        const job = await uploadWithProgress(file, (p) => {
          $(".up-state", box).textContent = p < 1 ? `업로드 중… ${Math.round(p * 100)}%` : "문서 구조 분석 중…";
          if (p >= 1) bar.classList.add("is-indeterminate");
          else $("i", bar).style.width = `${p * 100}%`;
        });
        if (job.text_layer && job.text_layer.status === "scanned") {
          await api(`/api/jobs/${job.id}`, { method: "DELETE" }).catch(() => {});
          toast(`${file.name}: 글자 정보가 없는 스캔본 PDF예요. 글자를 긁을 수 있는 PDF만 변환할 수 있어요.`, true);
          continue;
        }
        if (job.text_layer && job.text_layer.status === "garbled") {
          toast(`${file.name}: 일부 글자가 깨진 PDF일 수 있어요. 결과를 꼭 확인해 주세요.`, true);
        }
        addFile(job);
      } catch (err) {
        toast(`${file.name}: ${err.message}`, true);
      }
    }
    box.hidden = true;
    if (state.files.length && !$("#stage-work").classList.contains("is-visible")) openWorkspace();
  }

  function defaultTitle(job) {
    const cands = job.title_candidates || [];
    const cur = $("#in-title").value;
    if (!cands[0]) return cur;
    const prefix = (cur.match(/^\s*\[[^\]]*\]\s*/) || [""])[0]; // "[중간 대비] " 같은 머리말은 이어서 쓴다
    return (prefix + cands[0]).trim();
  }

  function addFile(job) {
    state.files.push({ job, title: defaultTitle(job), status: "ready", result: null, error: null });
    if (state.files.length === 1) state.sel = 0;
    if (state.files.length > 1) markStale();
    if ($("#stage-work").classList.contains("is-visible")) { renderFiles(); selectFile(state.sel); }
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
  function openWorkspace() {
    state.converted = false;
    state.downloaded = false;
    $("#result").hidden = true;
    $("#actions").hidden = false;
    showStage("stage-work");
    setStep(2);
    renderFiles();
    selectFile(0);
  }

  // 미리보기할 파일 고르기(원본 그림·통계·제목 후보·미리보기가 그 파일로 바뀐다)
  function selectFile(i) {
    const f = state.files[i];
    if (!f) return;
    state.sel = i;
    const job = f.job;
    state.job = job;
    const multi = state.files.length > 1;
    $("#file-chip").textContent = multi ? `${i + 1}. ${job.filename}` : job.filename;
    $("#source-img").src = job.page1 + `?t=${Date.now()}`;
    const st = job.stats || {};
    $("#source-stats").innerHTML = [
      ["쪽", st.pages], ["문제", st.questions], ["지문", st.passages], ["정답", st.answers],
    ].filter(([, v]) => v != null).map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("");
    const chips = $("#title-chips");
    const cands = job.title_candidates || [];
    chips.innerHTML = cands.length ? `<span class="label">PDF에서 찾은 제목</span>` +
      cands.map((c) => `<button type="button" data-title="${esc(c)}">${esc(c)}</button>`).join("") : "";
    $("#in-title").value = getTitle();
    $$(".fl-item").forEach((li) => li.classList.toggle("is-sel", +li.dataset.i === i));
    renderPreview();
  }

  // 제목: 따로 변환이면 파일마다, 합치기면 통합본 하나
  const merging = () => state.files.length > 1 && state.multiMode === "merge";
  function getTitle() {
    if (merging()) return state.mergeTitle ?? (state.files[0] ? state.files[0].title : "");
    const f = state.files[state.sel];
    return f ? f.title : "";
  }
  function setTitle(v) {
    if (merging()) state.mergeTitle = v;
    else if (state.files[state.sel]) state.files[state.sel].title = v;
  }

  const STATUS = { ready: "", queued: "대기", working: "변환 중…", done: "완료", error: "오류" };
  function renderFiles() {
    const n = state.files.length;
    const multi = n > 1;
    $("#file-list-wrap").hidden = !multi;
    $("#multi-group").hidden = !multi;
    $("#btn-add").disabled = n >= maxFiles();
    $("#multi-count").textContent = multi ? `${n}개 · 최대 ${maxFiles()}개` : "";
    $$("[data-multi-mode]").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.multiMode === state.multiMode)));
    $("#multi-note").textContent = state.multiMode === "merge"
      ? "목록 순서대로 이어 한 파일로 만들어요. 문제 번호와 정답 번호가 1번부터 끝까지 이어져요(예: 20문제 3개 → 1~60번)."
      : "파일마다 한글 파일을 하나씩 만들어요. 하나씩 차례로 변환하고, ZIP으로 한 번에 또는 따로 받을 수 있어요. 제목은 파일마다 따로 정해요.";
    $("#file-list").innerHTML = state.files.map((f, i) => {
      const st = f.job.stats || {};
      const meta = [st.pages != null ? `${st.pages}쪽` : "", st.questions != null ? `문제 ${st.questions}` : ""].filter(Boolean).join(" · ");
      const label = STATUS[f.status] || "";
      return `<li class="fl-item${i === state.sel ? " is-sel" : ""}" data-i="${i}">
        <button type="button" class="fl-main" data-act="select" title="${esc(f.job.filename)}"><span class="fl-no">${i + 1}</span><span class="fl-name">${esc(f.job.filename)}</span><span class="fl-meta">${esc(meta)}</span></button>
        ${label ? `<span class="fl-status" data-s="${f.status}"${f.error ? ` title="${esc(f.error)}"` : ""}>${label}</span>` : ""}
        <button type="button" class="fl-btn" data-act="up" aria-label="위로" title="위로"${i === 0 ? " disabled" : ""}>↑</button>
        <button type="button" class="fl-btn" data-act="remove" aria-label="목록에서 빼기" title="빼기">×</button>
      </li>`;
    }).join("");
  }

  $("#file-list").addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-act]");
    if (!btn || state.busy) return;
    const i = +btn.closest(".fl-item").dataset.i;
    const act = btn.dataset.act;
    if (act === "select") { selectFile(i); return; }
    if (act === "up" && i > 0) {
      const [f] = state.files.splice(i, 1);
      state.files.splice(i - 1, 0, f);
      const sel = state.sel === i ? i - 1 : state.sel === i - 1 ? i : state.sel;
      renderFiles();
      selectFile(sel);
      markStale();
      return;
    }
    if (act === "remove") {
      const [f] = state.files.splice(i, 1);
      fetch(`/api/jobs/${f.job.id}`, { method: "DELETE" }).catch(() => {});
      if (!state.files.length) { await discardAll(); showStage("stage-upload"); setStep(1); return; }
      renderFiles();
      selectFile(Math.min(state.sel > i ? state.sel - 1 : state.sel, state.files.length - 1));
      markStale();
    }
  });

  $$("[data-multi-mode]").forEach((b) => b.addEventListener("click", () => {
    if (state.multiMode === b.dataset.multiMode) return;
    state.multiMode = b.dataset.multiMode;
    renderFiles();
    $("#in-title").value = getTitle();
    renderPreview();
    markStale();
  }));

  $("#title-chips").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-title]");
    if (!b) return;
    const cur = $("#in-title").value;
    const prefix = (cur.match(/^\s*\[[^\]]*\]\s*/) || [""])[0]; // "[중간 대비] " 같은 머리말은 유지
    $("#in-title").value = (prefix + b.dataset.title).trim();
    setTitle($("#in-title").value);
    onSettingsChange();
  });

  async function discardAll() {
    const ids = state.files.map((f) => f.job.id);
    if (state.bundleId) ids.push(state.bundleId);
    state.files = [];
    state.job = null;
    state.sel = 0;
    state.bundleId = null;
    state.mergeTitle = null;
    state.converted = false;
    stopTimer();
    await Promise.all(ids.map((id) => fetch(`/api/jobs/${id}`, { method: "DELETE" }).catch(() => {})));
  }
  $("#btn-new").addEventListener("click", async () => {
    if (hasUndownloaded() && !confirm("변환한 파일을 아직 내려받지 않았어요. 새 PDF를 올릴까요?")) return;
    await discardAll();
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
    setTitleColor(/^#[0-9a-fA-F]{6}$/.test(p.titleColor || "") ? p.titleColor : "#000000", false);
    setAnswerMode(p.answerMode === "endnote" ? "endnote" : "end", false);
    setAcademyMode(p.academyMode || "text", false);
    if (typeof p.autoNum === "boolean") $("#in-autonum").checked = p.autoNum;
    $("#out-size").textContent = (+$("#in-size").value).toFixed(1).replace(/\.0$/, "");
  }

  function setAcademyMode(mode, render = true) {
    state.academyMode = mode;
    $$("[data-academy-mode]").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.academyMode === mode)));
    $$("[data-academy-pane]").forEach((p) => { p.hidden = p.dataset.academyPane !== mode; });
    if (render) onSettingsChange();
  }
  $$("[data-academy-mode]").forEach((b) => b.addEventListener("click", () => setAcademyMode(b.dataset.academyMode)));

  // 제목 글자 색
  function setTitleColor(color, render = true) {
    state.titleColor = color.toUpperCase();
    let preset = false;
    $$("#title-colors [data-color]").forEach((b) => {
      const on = b.dataset.color.toUpperCase() === state.titleColor;
      preset = preset || on;
      b.setAttribute("aria-checked", String(on));
    });
    $("#in-title-color").value = state.titleColor.toLowerCase();
    $(".swatch-custom").classList.toggle("is-on", !preset);
    if (render) onSettingsChange();
  }
  $$("#title-colors [data-color]").forEach((b) => b.addEventListener("click", () => setTitleColor(b.dataset.color)));
  $("#in-title-color").addEventListener("input", (e) => setTitleColor(e.target.value));

  // 정답·해설 넣는 방식
  const ANSWER_NOTE = {
    end: "정답·해설을 문제 뒤에 [정답 및 해설] 쪽으로 이어 붙입니다.",
    endnote: "각 문제에 미주로 연결해 문서 끝에 모읍니다(한글 ‘미주’). 문제 쪽에는 미주 번호가 보이지 않게 숨겨요.",
  };
  function setAnswerMode(mode, render = true) {
    state.answerMode = mode;
    $$("[data-answer-mode]").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.answerMode === mode)));
    $("#answer-note").textContent = ANSWER_NOTE[mode];
    if (render) onSettingsChange();
  }
  $$("[data-answer-mode]").forEach((b) => b.addEventListener("click", () => setAnswerMode(b.dataset.answerMode)));

  $("#in-title").addEventListener("input", () => setTitle($("#in-title").value));
  ["#in-academy", "#in-title", "#in-font", "#in-title-font", "#in-size", "#in-frame", "#in-autonum"].forEach((sel) => {
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
    if (!f || !state.files.length) return;
    const fd = new FormData();
    fd.append("file", f);
    try {  // 로고는 첫 파일 작업에만 올리고, 다른 파일은 변환할 때 logo_job으로 빌려 쓴다
      const r = await api(`/api/jobs/${state.files[0].job.id}/logo`, { method: "POST", body: fd });
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
    if (state.files.length) await api(`/api/jobs/${state.files[0].job.id}/logo`, { method: "DELETE" }).catch(() => {});
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
      auto_number: $("#in-autonum").checked,
      frame: $("#in-frame").checked,
      title_color: state.titleColor || "#000000",
      answers_as_endnotes: state.answerMode === "endnote",
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
    ti.style.color = o.title ? o.title_color : "";
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
  const postJSON = (path, body) => api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

  function setBusy(on, label) {
    const btn = $("#btn-convert");
    state.busy = on;
    btn.disabled = on;
    btn.classList.toggle("is-busy", on);
    $(".btn-label", btn).textContent = on ? label : "HWPX로 변환하기";
    $("#btn-add").disabled = on || state.files.length >= maxFiles();
    $("#btn-new").disabled = on;
  }

  async function convertNow() {
    if (!state.files.length || state.busy) return;
    if (state.bundleId) {  // 이전 묶음은 지운다
      fetch(`/api/jobs/${state.bundleId}`, { method: "DELETE" }).catch(() => {});
      state.bundleId = null;
    }
    const opts = currentOptions();
    opts.logo_job = state.files[0].job.id;
    try {
      if (state.files.length === 1) {
        setBusy(true, "변환하는 중…");
        const f = state.files[0];
        const r = await postJSON(`/api/jobs/${f.job.id}/convert`, { ...opts, title: f.title.trim() });
        showResult(r);
      } else if (state.multiMode === "merge") {
        setBusy(true, `${state.files.length}개를 하나로 합치는 중…`);
        const r = await postJSON("/api/bundles/merge", {
          jobs: state.files.map((f) => f.job.id), options: { ...opts, title: getTitle().trim() },
        });
        state.bundleId = r.id;
        showResult(r);
      } else {
        await convertEach(opts);
      }
    } catch (err) {
      if (err.status === 404) {
        toast("작업 시간이 지나 파일이 삭제됐어요. PDF를 다시 올려 주세요.", true);
        await discardAll();
        showStage("stage-upload");
        setStep(1);
      } else toast(err.message, true);
    } finally {
      setBusy(false);
      if (state.files.length) renderFiles();
    }
  }

  // 대기열: 파일을 하나씩 차례로 변환한 뒤 ZIP으로 묶는다
  async function convertEach(opts) {
    const files = state.files;
    files.forEach((f) => { f.status = "queued"; f.result = null; f.error = null; });
    renderFiles();
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      if (!state.files.includes(f)) continue;
      f.status = "working";
      setBusy(true, `변환하는 중… (${i + 1}/${files.length})`);
      renderFiles();
      try {
        f.result = await postJSON(`/api/jobs/${f.job.id}/convert`, { ...opts, title: f.title.trim() });
        f.status = "done";
      } catch (err) {
        if (err.status === 404) throw err;
        f.status = "error";
        f.error = err.message;
      }
      renderFiles();
    }
    const done = files.filter((f) => f.status === "done");
    if (!done.length) { toast("변환에 성공한 파일이 없어요.", true); return; }
    const z = await postJSON("/api/bundles/zip", { jobs: done.map((f) => f.job.id) });
    state.bundleId = z.id;
    showBatchResult(z, files);
  }

  function summaryHTML(sm) {
    return [
      ["문제", sm.questions != null ? `${sm.questions}개` : null],
      ["객관식/서술형", sm.objective != null ? `${sm.objective}/${sm.subjective}` : null],
      ["박스", sm.boxes], ["그림", sm.pictures], ["정답", sm.answers], ["미주", sm.endnotes || null],
      ["원문 반영", sm.coverage != null ? `${Math.round(sm.coverage * 100)}%` : null],
    ].filter(([, v]) => v != null).map(([k, v]) => `<li>${k}<b>${v}</b></li>`).join("");
  }
  const statusText = (s) => (s === "PASS" ? "구조 검사 통과" : s === "WARN" ? "확인이 필요한 부분이 있어요" : "일부 문제가 있어요");

  // 자동 번호·미주를 일부만 적용했거나 원문과 다른 점이 있으면 이유를 결과 칸에 보여 준다
  function showWarnings(list) {
    const ul = $("#result-warn");
    const items = (list || []).filter(Boolean).slice(0, 6);
    ul.innerHTML = items.map((w) => `<li>${esc(w)}</li>`).join("");
    ul.hidden = !items.length;
  }

  function revealResult(r, label) {
    state.converted = true;
    state.downloaded = false;
    state.dirty = false;
    const res = $("#result");
    res.classList.remove("is-expired");
    $("#result-name").textContent = r.filename;
    const a = $("#btn-download");
    a.href = r.download_url;
    a.setAttribute("download", r.filename);
    $("#btn-download-label").textContent = label;
    res.hidden = false;
    $("#actions").hidden = true;
    setStep(3);
    startTimer(r.seconds_left);
    res.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function showResult(r) {
    const merged = r.files > 1;
    $("#result-meta").textContent = `${(r.size / 1024).toFixed(0)}KB · ${merged ? `${r.files}개 통합 · ` : ""}${statusText(r.status)}`;
    $("#result-summary").innerHTML = summaryHTML(r.summary || {});
    $("#result-files").hidden = true;
    showWarnings([...(r.root_causes || []), ...(r.warnings || [])]);
    revealResult(r, merged ? "통합본 내려받기" : "한글 파일 내려받기");
  }

  function showBatchResult(z, files) {
    const done = files.filter((f) => f.status === "done");
    const q = done.reduce((n, f) => n + ((f.result.summary || {}).questions || 0), 0);
    const failed = files.length - done.length;
    $("#result-meta").textContent = `${(z.size / 1024).toFixed(0)}KB · ${done.length}개 변환${failed ? ` · ${failed}개 실패` : ""}`;
    $("#result-summary").innerHTML = `<li>파일<b>${done.length}개</b></li><li>문제 합계<b>${q}개</b></li>`;
    const ul = $("#result-files");
    ul.innerHTML = files.map((f) => {
      if (f.status !== "done") return `<li class="is-error"><span>${esc(f.job.filename)}</span><small>${esc(f.error || "실패")}</small></li>`;
      const r = f.result;
      return `<li><span>${esc(r.filename)}</span><small>${statusText(r.status)}</small><a href="${r.download_url}" download="${esc(r.filename)}">받기</a></li>`;
    }).join("");
    ul.hidden = false;
    showWarnings(done.flatMap((f) => [...(f.result.root_causes || []), ...(f.result.warnings || [])].map((w) => `${f.job.filename}: ${w}`)));
    revealResult(z, "ZIP으로 한 번에 내려받기");
  }
  $("#btn-download").addEventListener("click", () => { state.downloaded = true; });
  $("#result-files").addEventListener("click", (e) => { if (e.target.closest("a")) state.downloaded = true; });

  function markStale() {
    if (state.dirty || !state.converted) return;
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
    for (const f of state.files) navigator.sendBeacon(`/api/jobs/${f.job.id}/delete`);
    if (state.bundleId) navigator.sendBeacon(`/api/jobs/${state.bundleId}/delete`);
  });

  // --------------------------------------------------------------- init --
  (async () => {
    try {
      const cfg = await api("/api/config");
      state.cfg = cfg;
      $$("[data-cfg]").forEach((el) => { el.textContent = cfg[el.dataset.cfg]; });
      if (cfg.admin) $("#admin-link").hidden = false;
    } catch (_) { /* 기본값 사용 */ }
    fillFonts();
  })();
})();
