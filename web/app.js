(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const HISTORIES = [
    ["史記", "西漢 · 司馬遷"], ["漢書", "東漢 · 班固"], ["後漢書", "南朝宋 · 范曄"],
    ["三國志", "西晉 · 陳壽"], ["晉書", "唐 · 房玄齡等"], ["宋書", "南朝梁 · 沈約"],
    ["南齊書", "南朝梁 · 蕭子顯"], ["梁書", "唐 · 姚思廉"], ["陳書", "唐 · 姚思廉"],
    ["魏書", "北齊 · 魏收"], ["北齊書", "唐 · 李百藥"], ["周書", "唐 · 令狐德棻等"],
    ["隋書", "唐 · 魏徵等"], ["南史", "唐 · 李延壽"], ["北史", "唐 · 李延壽"],
    ["舊唐書", "後晉 · 劉昫等"], ["新唐書", "北宋 · 歐陽修等"], ["舊五代史", "北宋 · 薛居正等"],
    ["新五代史", "北宋 · 歐陽修"], ["宋史", "元 · 脫脫等"], ["遼史", "元 · 脫脫等"],
    ["金史", "元 · 脫脫等"], ["元史", "明 · 宋濂等"], ["明史", "清 · 張廷玉等"],
  ];

  const state = {
    bookId: "jinshu",
    chapterId: null,
    book: null,
    chapters: [],
    chapter: null,
    paragraphs: [],
    footnotes: [],
    annotations: [],
    layout: localStorage.getItem("qj-layout") || "vertical",
    theme: localStorage.getItem("qj-theme") || "paper",
    fontSize: Number(localStorage.getItem("qj-font") || 21),
    transOpen: true,
    originalOpen: false,
    panelTab: "trans",
    activePid: null,
    pendingSelection: null,
    editingAnn: null,
    selectionTranslation: null,
    generated: new Set(),
    llm: null,
    ocr: null,
    ocrPoll: null,
    suppressActive: false,
  };

  const el = {};
  let activeTimer = 0;
  let progressTimer = 0;
  let resizeTimer = 0;
  let searchTimer = 0;
  let toastTimer = 0;

  // ---------- api ----------
  async function api(path, options = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    let data = null;
    try { data = await res.json(); } catch (_) { data = {}; }
    if (!res.ok) throw new Error(data.error || `请求失败 (${res.status})`);
    return data;
  }

  function toast(message, ms = 2600) {
    el.toast.textContent = message;
    el.toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.toast.classList.remove("show"), ms);
  }

  // ---------- boot ----------
  async function init() {
    cacheEls();
    bindEvents();
    applyTheme(state.theme);
    applyLayout(state.layout, false);
    applyFont(state.fontSize, false);
    tickClock();
    setInterval(tickClock, 30000);

    try {
      const [lib, bookData, settings] = await Promise.all([
        api("/api/library"),
        api(`/api/books/${state.bookId}`),
        api("/api/settings"),
      ]);
      state.book = bookData.book;
      state.chapters = bookData.chapters;
      state.llm = settings.llm;
      const reader = settings.reader || {};
      if (reader.theme) state.theme = reader.theme;
      if (reader.layout) state.layout = reader.layout;
      if (reader.fontSize) state.fontSize = Number(reader.fontSize);
      if (typeof reader.showTranslation === "boolean") state.transOpen = reader.showTranslation;
      const params = new URLSearchParams(location.search);
      if (params.get("layout") === "horizontal" || params.get("layout") === "vertical") state.layout = params.get("layout");
      if (params.get("original") === "1") state.originalOpen = true;
      if (params.get("trans") === "0") state.transOpen = false;
      applyTheme(state.theme);
      applyLayout(state.layout, false);
      applyFont(state.fontSize, false);
      renderSidebar(lib.books);

      const hashChapter = (location.hash.match(/#\/read\/([\w-]+)/) || [])[1];
      const libBook = (lib.books || []).find((x) => x.id === state.bookId) || {};
      const progressChapter = libBook.progress && libBook.progress.chapter_id;
      const firstReady = bookData.chapters.find((c) => c.status === "ready")?.id;
      const chapterId = hashChapter || (bookData.chapters.find((c) => c.id === progressChapter)?.id) || firstReady || "jinshu-01";
      el.translationPanel.hidden = !state.transOpen;
      el.transBtn.classList.toggle("active", state.transOpen);
      el.app.hidden = false;
      await loadChapter(chapterId);
      await refreshOcrStatus();
      if (params.get("settings") === "1") setTimeout(openSettings, 350);
      if (params.get("library") === "1") setTimeout(() => { renderLibrary(); el.libraryModal.hidden = false; }, 350);
      if (params.get("search") === "1") setTimeout(openSearch, 350);
      requestAnimationFrame(() => {
        el.boot.classList.add("done");
        setTimeout(() => { el.boot.hidden = true; }, 600);
      });
    } catch (err) {
      el.boot.querySelector(".boot-text").textContent = "书卷未能展开：" + err.message;
      el.boot.querySelector(".boot-line").style.display = "none";
      toast(err.message, 5000);
    }
  }

  function cacheEls() {
    const ids = [
      "boot", "app", "crumb", "layoutBtn", "layoutLabel", "transBtn", "originalBtn",
      "fontMinus", "fontPlus", "fontValue", "searchBtn", "settingsBtn", "bookCard",
      "sideCover", "sideTitle", "sideMeta", "sideProgress", "sideProgressText",
      "tocList", "volumeList", "tocPane", "marksPane", "marksList", "markCount",
      "libraryBtn", "chapterKicker", "chapterTitle", "chapterSub", "chapterMeta",
      "readerStage", "readerScroll", "readerText", "readerEmpty", "emptyOcrBtn",
      "originalPanel", "originalImage", "originalPageLabel", "closeOriginal",
      "translationPanel", "closeTrans", "transBody", "notesBody", "transContext",
      "transText", "translateCurrent", "transModel", "footnoteList", "statusText",
      "posText", "focusBtn", "themeBtn", "clock", "selectionMenu", "noteModal",
      "noteQuote", "noteInput", "saveNote", "settingsModal", "themeSeg", "layoutSeg",
      "fontRange", "fontRangeValue", "llmBase", "llmModel", "llmKey", "llmState",
      "saveLlm", "ocrStart", "ocrEnd", "ocrQualitySeg", "ocrProgress",
      "ocrProgressText", "ocrProgressPct", "ocrBar", "ocrState", "startOcr",
      "ocrModal", "ocrPageSelect", "ocrConfidence", "ocrText", "copyOcr", "saveOcr", "viewOcr",
      "libraryModal", "libraryGrid", "searchModal", "searchInput", "searchResults",
      "annotationModal", "annotationQuote", "annotationText", "annotationMeta",
      "deleteAnnotation", "editAnnotation", "toast",
    ];
    ids.forEach((id) => { el[id] = document.getElementById(id); });
    el.boot.querySelector(".boot-text").textContent = "正在展開書卷";
  }

  // ---------- rendering ----------
  function renderSidebar(library) {
    const b = state.book;
    el.sideCover.src = b.cover || "/assets/cover-jinshu.jpg";
    el.sideTitle.textContent = b.title;
    el.sideMeta.textContent = b.author || "";
    el.sideProgress.style.width = "7.8%";
    el.sideProgressText.textContent = state.chapter ? `${state.chapter.volume} · ${state.chapter.subtitle}` : "卷一 · 宣帝";
    renderToc();
    renderVolumeList();
    el.markCount.textContent = String(state.annotations.length);
  }

  function renderToc() {
    const current = state.chapterId;
    el.tocList.innerHTML = state.chapters.map((ch) => {
      const locked = ch.status !== "ready";
      return `<button class="toc-item ${ch.id === current ? "active" : ""} ${locked ? "locked" : ""}" data-chapter="${ch.id}">
        <span class="toc-vol">${esc(ch.volume || "")}</span>
        <span class="toc-main"><b>${esc(ch.title)}</b><span>${esc(ch.subtitle || "")}</span></span>
        <span class="toc-status">${locked ? "待識別" : "可讀"}</span>
      </button>`;
    }).join("");
  }

  function renderVolumeList() {
    el.volumeList.innerHTML = [
      ["志 · 二十卷", "待導入"], ["列傳 · 七十卷", "待導入"], ["載記 · 三十卷", "待導入"],
    ].map(([a, b]) => `<button class="volume-item" data-locked="1"><span>${a}</span><span>${b}</span></button>`).join("");
  }

  function renderChapterHead() {
    const b = state.book;
    const ch = state.chapter;
    if (!b || !ch) return;
    el.crumb.innerHTML = `<span>${esc(b.title)}</span><i>/</i><span>${esc(ch.volume)}</span><i>/</i><b>${esc(ch.title)}</b>`;
    el.chapterKicker.textContent = `${b.title} · ${ch.volume}`;
    el.chapterTitle.textContent = ch.title;
    el.chapterSub.textContent = ch.subtitle || "";
    el.chapterMeta.textContent = `${b.author || ""} · 據${b.edition || "原掃描本"}`;
    document.title = `${b.title} ${ch.volume} ${ch.title} · 青简`;
  }

  function renderChapterMeta() {
    const ch = state.chapter;
    if (!ch) return;
    el.statusText.textContent = `${ch.volume} · 已校對`;
    el.sideProgressText.textContent = `${ch.volume} · ${ch.subtitle || ""}`;
    el.posText.textContent = `第 1 段 / ${state.paragraphs.length}`;
  }

  function renderReader(preservePid = null) {
    state.suppressActive = true;
    el.readerText.innerHTML = "";
    el.readerEmpty.hidden = state.paragraphs.length > 0;
    el.readerScroll.classList.toggle("vertical", state.layout === "vertical");

    if (state.layout === "vertical") {
      el.readerText.className = "reader-text vertical";
      renderVertical();
    } else {
      el.readerText.className = "reader-text horizontal";
      renderHorizontal();
    }
    state.suppressActive = false;

    requestAnimationFrame(() => {
      if (state.layout === "vertical") {
        if (preservePid) scrollToPid(preservePid, false);
        else el.readerScroll.scrollLeft = el.readerScroll.scrollWidth;
      } else if (preservePid) {
        scrollToPid(preservePid, false);
      } else {
        el.readerScroll.scrollTop = 0;
      }
      updateActive(true);
    });
  }

  function renderVertical() {
    const height = Math.max(340, el.readerScroll.clientHeight - 4);
    // In vertical writing mode line-height controls the distance between
    // columns, while characters advance by roughly one em vertically.
    const advance = state.fontSize * 1.08;
    const base = Math.max(8, Math.floor((height - 52) / advance));
    const pieces = [];
    for (const p of state.paragraphs) {
      const marks = buildMarks(p.id);
      const tokens = tokenize(p.text);
      let i = 0;
      let first = true;
      while (i < tokens.length) {
        const limit = first ? Math.max(6, base - 2) : base;
        let count = 0;
        const startIdx = i;
        while (i < tokens.length && count < limit) { count += 1; i += 1; }
        const chunk = tokens.slice(startIdx, i);
        if (!chunk.length) break;
        const startOff = chunk[0].start;
        const endOff = chunk[chunk.length - 1].end;
        const isEnd = i >= tokens.length;
        pieces.push(
          `<div class="v-col${first ? " para-start" : ""}${isEnd ? " para-end" : ""}" data-pid="${p.id}" data-start="${startOff}" data-end="${endOff}">` +
          renderTokens(p.text.slice(startOff, endOff), p.id, startOff, marks) +
          `</div>`
        );
        first = false;
      }
    }
    el.readerText.innerHTML = pieces.join("");
    if (location.search.includes("debug")) {
      el.readerText.dataset.metrics = JSON.stringify({
        base, height, advance, scrollClientH: el.readerScroll.clientHeight,
        stageH: el.readerStage.clientHeight, cols: pieces.length,
      });
    }
  }

  function renderHorizontal() {
    el.readerText.innerHTML = state.paragraphs.map((p) => {
      const marks = buildMarks(p.id);
      return `<p class="hp" data-pid="${p.id}" data-start="0">${renderTokens(p.text, p.id, 0, marks)}</p>`;
    }).join("");
  }

  function tokenize(text) {
    const tokens = [];
    for (let i = 0; i < text.length; i++) {
      if (text[i] === "〔") {
        const j = text.indexOf("〕", i + 1);
        if (j > i && j - i <= 4) {
          tokens.push({ start: i, end: j + 1, text: text.slice(i, j + 1), marker: true });
          i = j;
          continue;
        }
      }
      if (text[i] === "[") {
        const j = text.indexOf("]", i + 1);
        if (j > i && j - i <= 3) {
          tokens.push({ start: i, end: j + 1, text: text.slice(i, j + 1), marker: true });
          i = j;
          continue;
        }
      }
      tokens.push({ start: i, end: i + 1, text: text[i] });
    }
    return tokens;
  }

  function markerNote(marker) {
    return state.footnotes.find((n) => n.marker === marker || cnNum(n.marker) === marker);
  }

  function renderTokens(text, pid, base, marks) {
    let html = "";
    for (let i = 0; i < text.length; i++) {
      const abs = base + i;
      if (text[i] === "〔" || text[i] === "[") {
        const close = text[i] === "〔" ? "〕" : "]";
        const j = text.indexOf(close, i + 1);
        if (j > i && j - i <= 4) {
          const marker = text.slice(i + 1, j);
          const note = markerNote(marker);
          if (note) {
            html += `<span class="fn-ref" data-marker="${esc(marker)}" data-pid="${pid}" data-start="${abs}" data-end="${abs + (j - i + 1)}"><span class="fn-bracket">${esc(text[i])}</span>${esc(marker)}<span class="fn-bracket">${esc(close)}</span></span>`;
          } else {
            for (let k = i; k <= j; k++) html += charSpan(text[k], pid, base + k, marks);
          }
          i = j;
          continue;
        }
      }
      html += charSpan(text[i], pid, abs, marks);
    }
    return html;
  }

  function charSpan(ch, pid, abs, marks) {
    const mark = marks.get(abs);
    let cls = "ch";
    let attr = "";
    if (mark) {
      cls += " " + Array.from(mark.classes).join(" ");
      attr = ` data-ann="${mark.ids.join(",")}"`;
    }
    return `<span class="${cls}" data-pid="${pid}" data-off="${abs}"${attr}>${esc(ch)}</span>`;
  }

  function buildMarks(pid) {
    const map = new Map();
    for (const ann of state.annotations) {
      if (Number(ann.paragraph_id) !== Number(pid)) continue;
      for (let i = Number(ann.start_offset); i < Number(ann.end_offset); i++) {
        let rec = map.get(i);
        if (!rec) { rec = { classes: new Set(), ids: [] }; map.set(i, rec); }
        rec.classes.add("ann-" + ann.kind);
        if (!rec.ids.includes(ann.id)) rec.ids.push(ann.id);
      }
    }
    return map;
  }

  function renderMarks() {
    el.markCount.textContent = String(state.annotations.length);
    if (!state.annotations.length) {
      el.marksList.innerHTML = `<div class="mark-empty">還沒有批注。<br>選中正文，寫下第一條考證。</div>`;
      return;
    }
    const sorted = [...state.annotations].sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)));
    el.marksList.innerHTML = sorted.map((ann) => {
      const p = state.paragraphs.find((x) => Number(x.id) === Number(ann.paragraph_id));
      const kind = ann.kind === "note" ? "批注" : ann.kind === "underline" ? "劃線" : "高亮";
      const note = ann.note ? `<div class="mk-note">${esc(ann.note)}</div>` : "";
      const page = p ? `第 ${p.page_start} 頁` : "";
      return `<button class="mark-item" data-ann-id="${esc(ann.id)}">
        <div class="mk-quote">${esc(ann.quote)}</div>
        ${note}
        <div class="mk-meta"><span class="mark-kind">${kind}</span><span>${page}</span></div>
      </button>`;
    }).join("");
  }

  function renderFootnotes() {
    if (!state.footnotes.length) {
      el.footnoteList.innerHTML = `<div class="mark-empty">本卷暫無校勘記。</div>`;
      return;
    }
    el.footnoteList.innerHTML = state.footnotes.map((n) => `<div class="footnote-item">
      <span class="fn-num">${esc(n.marker)}</span>
      <div class="fn-text">${esc(n.text)}<span class="fn-page">第 ${n.page || "—"} 頁</span></div>
    </div>`).join("");
  }

  // ---------- chapter ----------
  async function loadChapter(chapterId, targetPid = null) {
    const data = await api(`/api/books/${state.bookId}/chapters/${chapterId}`);
    state.chapter = data.chapter;
    state.chapterId = data.chapter.id;
    state.paragraphs = data.paragraphs || [];
    state.footnotes = data.footnotes || [];
    state.annotations = data.annotations || [];
    state.selectionTranslation = null;
    const restorePid = targetPid || (data.progress && data.progress.paragraph_id) || null;
    state.activePid = restorePid || state.paragraphs[0]?.id || null;

    renderChapterHead();
    renderChapterMeta();
    renderReader(restorePid);
    renderMarks();
    renderFootnotes();
    renderToc();
    updateTranslation();
    if (state.originalOpen) {
      el.originalPanel.hidden = false;
      el.originalBtn.classList.add("active");
      updateOriginal();
    }
    if (state.transOpen) el.translationPanel.hidden = false;
    history.replaceState(null, "", `#/read/${chapterId}`);
    saveProgress();
  }

  function scrollToPid(pid, smooth = true) {
    if (!pid) return;
    const selector = state.layout === "vertical" ? `.v-col[data-pid="${pid}"]` : `.hp[data-pid="${pid}"]`;
    const node = $(selector, el.readerText);
    if (!node) return;
    if (state.layout === "vertical") {
      const left = node.offsetLeft - (el.readerScroll.clientWidth - node.offsetWidth) / 2;
      el.readerScroll.scrollTo({ left, behavior: smooth ? "smooth" : "auto" });
    } else {
      const top = node.offsetTop - 82;
      el.readerScroll.scrollTo({ top, behavior: smooth ? "smooth" : "auto" });
    }
    setActive(pid);
  }

  function updateActive(force = false) {
    if (!state.paragraphs.length || state.suppressActive) return;
    const scrollRect = el.readerScroll.getBoundingClientRect();
    let best = null;
    let bestDist = Infinity;
    if (state.layout === "vertical") {
      const target = scrollRect.right - Math.min(110, scrollRect.width * 0.18);
      for (const node of $$(".v-col", el.readerText)) {
        const r = node.getBoundingClientRect();
        if (r.right < scrollRect.left - 4 || r.left > scrollRect.right + 4) continue;
        const d = Math.abs((r.left + r.width / 2) - target);
        if (d < bestDist) { bestDist = d; best = node; }
      }
    } else {
      const target = scrollRect.top + 90;
      for (const node of $$(".hp", el.readerText)) {
        const r = node.getBoundingClientRect();
        if (r.bottom < scrollRect.top + 10 || r.top > scrollRect.bottom) continue;
        const d = Math.abs(r.top - target);
        if (d < bestDist) { bestDist = d; best = node; }
      }
    }
    if (!best) return;
    const pid = Number(best.dataset.pid);
    if (force || pid !== Number(state.activePid)) setActive(pid);
  }

  function setActive(pid) {
    if (!pid) return;
    state.activePid = Number(pid);
    const p = state.paragraphs.find((x) => Number(x.id) === Number(pid));
    if (!p) return;
    el.posText.textContent = `第 ${p.order_no} 段 / ${state.paragraphs.length}`;
    if (state.panelTab === "trans") updateTranslation();
    if (state.originalOpen) updateOriginal();
    saveProgressDebounced();
  }

  function saveProgressDebounced() {
    clearTimeout(progressTimer);
    progressTimer = setTimeout(saveProgress, 900);
  }

  async function saveProgress() {
    if (!state.chapterId) return;
    try {
      await api("/api/progress", {
        method: "POST",
        body: JSON.stringify({ book_id: state.bookId, chapter_id: state.chapterId, paragraph_id: state.activePid }),
      });
    } catch (_) { /* quiet */ }
  }

  // ---------- translation ----------
  function updateTranslation() {
    if (state.panelTab !== "trans") return;
    el.transBody.hidden = false;
    el.notesBody.hidden = true;
    if (state.selectionTranslation) {
      el.transContext.textContent = `選段 · ${state.selectionTranslation.quote.length} 字`;
      el.transText.textContent = state.selectionTranslation.text;
      el.transText.classList.remove("loading");
      el.transModel.textContent = "選段今譯";
      el.translateCurrent.textContent = "回到本段";
      return;
    }
    const p = state.paragraphs.find((x) => Number(x.id) === Number(state.activePid));
    if (!p) {
      el.transContext.textContent = "—";
      el.transText.textContent = "選中正文中的一段，開始閱讀今譯。";
      el.transModel.textContent = "未生成";
      el.translateCurrent.textContent = "生成此段今譯";
      return;
    }
    el.transContext.textContent = `第 ${p.order_no} 段 · 第 ${p.page_start} 頁`;
    if (p.translation) {
      el.transText.textContent = p.translation;
      el.transText.classList.remove("loading");
      el.transModel.textContent = state.generated.has(Number(p.id)) ? "AI 今譯" : "人工校訂";
      el.translateCurrent.textContent = "重新生成此段今譯";
    } else {
      el.transText.textContent = "此段尚無今譯。可在設定中接入大模型接口，按段生成。";
      el.transText.classList.remove("loading");
      el.transModel.textContent = "未生成";
      el.translateCurrent.textContent = "生成此段今譯";
    }
    el.transBody.scrollTop = 0;
  }

  async function translateCurrent() {
    if (state.selectionTranslation) {
      state.selectionTranslation = null;
      updateTranslation();
      return;
    }
    const p = state.paragraphs.find((x) => Number(x.id) === Number(state.activePid));
    if (!p) return;
    el.transText.textContent = "正在生成今譯…";
    el.transText.classList.add("loading");
    el.transModel.textContent = "生成中";
    try {
      const res = await api("/api/translate", {
        method: "POST",
        body: JSON.stringify({ paragraph_id: p.id, book: state.book.title, chapter: `${state.chapter.volume} ${state.chapter.title}` }),
      });
      p.translation = res.translation;
      state.generated.add(Number(p.id));
      updateTranslation();
      toast("今譯已生成並緩存");
    } catch (err) {
      el.transText.classList.remove("loading");
      updateTranslation();
      toast(err.message, 5000);
      if (/API Key|配置/.test(err.message)) openSettings();
    }
  }

  async function translateSelection(quote) {
    state.transOpen = true;
    el.translationPanel.hidden = false;
    el.transBtn.classList.add("active");
    state.selectionTranslation = { quote, text: "正在翻譯選段…" };
    state.panelTab = "trans";
    setPanelTab("trans");
    updateTranslation();
    el.transText.classList.add("loading");
    try {
      const res = await api("/api/translate", {
        method: "POST",
        body: JSON.stringify({ text: quote, book: state.book.title, chapter: `${state.chapter.volume} ${state.chapter.title}` }),
      });
      state.selectionTranslation = { quote, text: res.translation };
      updateTranslation();
    } catch (err) {
      state.selectionTranslation = null;
      updateTranslation();
      toast(err.message, 5000);
      if (/API Key|配置/.test(err.message)) openSettings();
    }
  }

  // ---------- original ----------
  function updateOriginal() {
    const p = state.paragraphs.find((x) => Number(x.id) === Number(state.activePid));
    if (!p) return;
    const page = p.page_start || 49;
    el.originalPageLabel.textContent = `PDF 第 ${page} 頁`;
    const src = `/api/page/${state.bookId}/${page}`;
    if (el.originalImage.dataset.page !== String(page)) {
      el.originalImage.dataset.page = String(page);
      el.originalImage.src = src;
    }
  }

  function openImageViewer() {
    if (!el.originalImage.src) return;
    const viewer = document.createElement("div");
    viewer.className = "image-viewer";
    viewer.innerHTML = `<button aria-label="关闭">×</button><img src="${esc(el.originalImage.src)}" alt="原扫描页">`;
    viewer.addEventListener("click", (e) => {
      if (e.target === viewer || e.target.tagName === "BUTTON") viewer.remove();
    });
    document.body.appendChild(viewer);
  }

  // ---------- selection ----------
  function handleSelection() {
    if (state.editingAnn) return;
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount) { hideSelection(); return; }
    const range = sel.getRangeAt(0);
    const startEl = closestChar(range.startContainer);
    const endEl = closestChar(range.endContainer);
    if (!startEl || !endEl) { hideSelection(); return; }
    if (!el.readerText.contains(startEl) || !el.readerText.contains(endEl)) { hideSelection(); return; }
    if (startEl.dataset.pid !== endEl.dataset.pid) {
      hideSelection();
      toast("請在同一段內選擇文字");
      return;
    }
    const start = boundaryOffset(range.startContainer, range.startOffset, true);
    const end = boundaryOffset(range.endContainer, range.endOffset, false);
    if (start == null || end == null || start >= end) { hideSelection(); return; }
    const pid = Number(startEl.dataset.pid);
    const p = state.paragraphs.find((x) => Number(x.id) === pid);
    if (!p) { hideSelection(); return; }
    const quote = p.text.slice(start, end);
    if (!quote.trim()) { hideSelection(); return; }
    let rect = range.getBoundingClientRect();
    if (!rect.width && !rect.height) {
      const rects = range.getClientRects();
      if (rects.length) rect = rects[0];
    }
    state.pendingSelection = { pid, start, end, quote, rect };
    showSelection(rect);
  }

  function closestChar(node) {
    if (!node) return null;
    if (node.nodeType === 3) node = node.parentElement;
    return node.closest ? node.closest(".ch, .fn-ref") : null;
  }

  function boundaryOffset(node, offset, isStart) {
    const charEl = closestChar(node);
    if (!charEl) return null;
    if (charEl.classList.contains("fn-ref")) {
      return isStart ? Number(charEl.dataset.start) : Number(charEl.dataset.end);
    }
    const base = Number(charEl.dataset.off);
    if (node.nodeType === 3) {
      return base + (offset > 0 ? 1 : 0);
    }
    return isStart ? base : base + 1;
  }

  function showSelection(rect) {
    const menu = el.selectionMenu;
    menu.hidden = false;
    const width = menu.offsetWidth || 280;
    const height = menu.offsetHeight || 40;
    let left = rect.left + rect.width / 2;
    let top = rect.top - 10;
    left = Math.max(width / 2 + 10, Math.min(window.innerWidth - width / 2 - 10, left));
    if (top - height < 8) top = rect.bottom + height + 10;
    menu.style.left = `${left}px`;
    menu.style.top = `${top}px`;
  }

  function hideSelection() {
    el.selectionMenu.hidden = true;
    state.pendingSelection = null;
  }

  async function createMark(kind) {
    const sel = state.pendingSelection;
    if (!sel) return;
    hideSelection();
    try {
      const res = await api("/api/annotations", {
        method: "POST",
        body: JSON.stringify({
          book_id: state.bookId, chapter_id: state.chapterId, paragraph_id: sel.pid,
          start_offset: sel.start, end_offset: sel.end, quote: sel.quote, kind,
          color: kind === "note" ? "cinnabar" : "ochre",
        }),
      });
      state.annotations.push(res.annotation);
      state.activePid = sel.pid;
      renderReader(sel.pid);
      renderMarks();
      toast(kind === "underline" ? "已劃線" : "已高亮");
    } catch (err) {
      toast(err.message, 4000);
    }
  }

  function openNoteModal(quote, existing = null) {
    state.editingAnn = existing;
    el.noteQuote.textContent = quote;
    el.noteInput.value = existing ? existing.note : "";
    el.noteModal.hidden = false;
    setTimeout(() => el.noteInput.focus(), 50);
  }

  async function saveNote() {
    const note = el.noteInput.value.trim();
    if (!note) { toast("批注內容不能為空"); return; }
    if (state.editingAnn) {
      try {
        const res = await api(`/api/annotations/${encodeURIComponent(state.editingAnn.id)}`, {
          method: "PATCH", body: JSON.stringify({ note }),
        });
        const idx = state.annotations.findIndex((a) => a.id === res.annotation.id);
        if (idx >= 0) state.annotations[idx] = res.annotation;
        state.editingAnn = null;
        el.noteModal.hidden = true;
        const pid = state.activePid;
        renderReader(pid);
        renderMarks();
        toast("批注已更新");
      } catch (err) { toast(err.message, 4000); }
      return;
    }
    const sel = state.pendingSelection;
    if (!sel) { toast("選區已失效，請重新選擇"); return; }
    try {
      const res = await api("/api/annotations", {
        method: "POST",
        body: JSON.stringify({
          book_id: state.bookId, chapter_id: state.chapterId, paragraph_id: sel.pid,
          start_offset: sel.start, end_offset: sel.end, quote: sel.quote,
          kind: "note", color: "cinnabar", note,
        }),
      });
      state.annotations.push(res.annotation);
      el.noteModal.hidden = true;
      hideSelection();
      state.activePid = sel.pid;
      renderReader(sel.pid);
      renderMarks();
      toast("批注已保存");
    } catch (err) { toast(err.message, 4000); }
  }

  function openAnnotation(id) {
    const ann = state.annotations.find((a) => a.id === id);
    if (!ann) return;
    const p = state.paragraphs.find((x) => Number(x.id) === Number(ann.paragraph_id));
    el.annotationQuote.textContent = ann.quote;
    el.annotationText.textContent = ann.note || "（這是一條劃線標記，沒有文字批注。）";
    el.annotationMeta.textContent = p ? `第 ${p.order_no} 段 · 第 ${p.page_start} 頁` : "";
    el.annotationModal.dataset.id = id;
    el.annotationModal.hidden = false;
  }

  async function deleteAnnotation() {
    const id = el.annotationModal.dataset.id;
    if (!id) return;
    if (!confirm("刪除這條批注？")) return;
    try {
      await api(`/api/annotations/${encodeURIComponent(id)}`, { method: "DELETE" });
      state.annotations = state.annotations.filter((a) => a.id !== id);
      el.annotationModal.hidden = true;
      const pid = state.activePid;
      renderReader(pid);
      renderMarks();
      toast("已刪除");
    } catch (err) { toast(err.message, 4000); }
  }

  // ---------- footnote popover ----------
  function openFootnote(marker, anchor) {
    closeFootnote();
    const note = markerNote(marker);
    if (!note) return;
    const pop = document.createElement("div");
    pop.className = "fn-popover";
    pop.innerHTML = `<div class="fn-pop-head"><span>校勘記 · 〔${esc(note.marker)}〕</span><button aria-label="关闭">×</button></div>
      <div class="fn-pop-text">${esc(note.text)}</div>
      <div class="fn-pop-page">原書第 ${note.page || "—"} 頁</div>`;
    document.body.appendChild(pop);
    const r = anchor.getBoundingClientRect();
    const w = 320;
    let left = r.left + r.width / 2 - w / 2;
    left = Math.max(12, Math.min(window.innerWidth - w - 12, left));
    let top = r.bottom + 10;
    if (top + 180 > window.innerHeight) top = r.top - 190;
    pop.style.left = `${left}px`;
    pop.style.top = `${Math.max(12, top)}px`;
    pop.querySelector("button").addEventListener("click", closeFootnote);
  }

  function closeFootnote() {
    $$(".fn-popover").forEach((n) => n.remove());
  }

  // ---------- layout / theme / font ----------
  function applyLayout(layout, save = true) {
    state.layout = layout;
    el.layoutLabel.textContent = layout === "vertical" ? "竖排" : "横排";
    el.layoutBtn.classList.toggle("active", layout === "vertical");
    el.readerScroll.classList.toggle("vertical", layout === "vertical");
    $$("#layoutSeg button").forEach((b) => b.classList.toggle("active", b.dataset.layout === layout));
    if (state.chapter) {
      const pid = state.activePid;
      renderReader(pid);
    }
    if (save) saveReaderPrefs();
  }

  function setLayout(layout) {
    if (state.layout === layout) return;
    applyLayout(layout);
    toast(layout === "vertical" ? "已切換為豎排" : "已切換為橫排");
  }

  function applyTheme(theme) {
    state.theme = theme;
    document.body.dataset.theme = theme;
    const names = { paper: "紙色", moon: "月白", ink: "墨夜" };
    el.themeBtn.textContent = names[theme] || "紙色";
    $$("#themeSeg button").forEach((b) => b.classList.toggle("active", b.dataset.theme === theme));
    localStorage.setItem("qj-theme", theme);
  }

  function cycleTheme() {
    const order = ["paper", "moon", "ink"];
    const next = order[(order.indexOf(state.theme) + 1) % order.length];
    applyTheme(next);
    saveReaderPrefs();
  }

  function applyFont(size, save = true) {
    state.fontSize = Math.max(15, Math.min(34, Number(size) || 21));
    el.readerText.style.setProperty("--reader-size", state.fontSize + "px");
    el.fontValue.textContent = state.fontSize;
    el.fontRange.value = state.fontSize;
    el.fontRangeValue.textContent = state.fontSize + " px";
    localStorage.setItem("qj-font", state.fontSize);
    if (state.chapter) {
      const pid = state.activePid;
      renderReader(pid);
    }
    if (save) saveReaderPrefs();
  }

  function saveReaderPrefs() {
    clearTimeout(saveReaderPrefs._t);
    saveReaderPrefs._t = setTimeout(() => {
      api("/api/settings/reader", {
        method: "POST",
        body: JSON.stringify({ layout: state.layout, theme: state.theme, fontSize: state.fontSize, showTranslation: state.transOpen }),
      }).catch(() => {});
    }, 400);
    localStorage.setItem("qj-layout", state.layout);
  }

  // ---------- sidebar / panels ----------
  function setSideTab(tab) {
    $$(".side-tabs button").forEach((b) => b.classList.toggle("active", b.dataset.sideTab === tab));
    el.tocPane.hidden = tab !== "toc";
    el.marksPane.hidden = tab !== "marks";
  }

  function setPanelTab(tab) {
    state.panelTab = tab;
    $$(".panel-tabs button").forEach((b) => b.classList.toggle("active", b.dataset.panelTab === tab));
    el.transBody.hidden = tab !== "trans";
    el.notesBody.hidden = tab !== "notes";
    if (tab === "trans") updateTranslation();
  }

  function toggleTrans(force) {
    state.transOpen = typeof force === "boolean" ? force : !state.transOpen;
    el.translationPanel.hidden = !state.transOpen;
    el.transBtn.classList.toggle("active", state.transOpen);
    if (state.transOpen) updateTranslation();
    saveReaderPrefs();
  }

  function toggleOriginal(force) {
    state.originalOpen = typeof force === "boolean" ? force : !state.originalOpen;
    el.originalPanel.hidden = !state.originalOpen;
    el.originalBtn.classList.toggle("active", state.originalOpen);
    if (state.originalOpen) updateOriginal();
  }

  // ---------- settings ----------
  async function openSettings() {
    try {
      const data = await api("/api/settings");
      state.llm = data.llm;
      fillLlm(data.llm);
    } catch (_) {}
    await refreshOcrStatus();
    el.fontRange.value = state.fontSize;
    el.fontRangeValue.textContent = state.fontSize + " px";
    $$("#layoutSeg button").forEach((b) => b.classList.toggle("active", b.dataset.layout === state.layout));
    $$("#themeSeg button").forEach((b) => b.classList.toggle("active", b.dataset.theme === state.theme));
    if (state.ocr) {
      const done = state.ocr.done || 0;
      const avg = state.ocr.average_confidence;
      el.ocrState.textContent = avg ? `已識別 ${done} 頁 · 平均置信度 ${Math.round(avg * 100)}%` : "尚未開始";
    }
    el.settingsModal.hidden = false;
  }

  function fillLlm(llm) {
    el.llmBase.value = llm.base_url || "https://api.deepseek.com";
    el.llmModel.value = llm.model || "deepseek-chat";
    el.llmKey.value = "";
    el.llmKey.placeholder = llm.has_key ? "已配置（留空即保留）" : "sk-…";
    el.llmState.textContent = llm.has_key ? `已配置 · ${llm.model || ""}` : "未配置 · 今譯需先填寫 API Key";
  }

  async function saveLlm() {
    try {
      const res = await api("/api/settings/llm", {
        method: "POST",
        body: JSON.stringify({ base_url: el.llmBase.value.trim(), model: el.llmModel.value.trim(), api_key: el.llmKey.value.trim() }),
      });
      state.llm = res.llm;
      fillLlm(res.llm);
      toast("接口已保存");
    } catch (err) { toast(err.message, 4000); }
  }

  async function openOcrReview(pageNo) {
    const pages = (state.ocr?.pages || []).filter((p) => p.status === "done" || p.status === "reviewed");
    if (!pages.length) {
      toast("尚無識別結果，請先執行一次 OCR");
      return;
    }
    el.ocrPageSelect.innerHTML = pages
      .map((p) => `<option value="${p.page_no}">第 ${p.page_no} 頁${p.status === "reviewed" ? " · 已校" : ""}</option>`)
      .join("");
    el.ocrModal.hidden = false;
    await loadOcrPage(pageNo || pages[0].page_no);
  }

  async function loadOcrPage(pageNo) {
    try {
      const data = await api(`/api/ocr/pages/${state.bookId}/${pageNo}`);
      const lines = data.page.lines || [];
      el.ocrText.value = lines.map((l) => l.text || "").join("\n");
      el.ocrConfidence.textContent = `${Math.round((data.page.confidence || 0) * 100)}% · ${lines.length} 行`;
      el.ocrPageSelect.value = String(pageNo);
    } catch (err) {
      toast(err.message, 4000);
    }
  }

  async function saveOcrReview() {
    const page = Number(el.ocrPageSelect.value);
    const text = el.ocrText.value.trim();
    if (!page || !text) { toast("校樣內容不能為空"); return; }
    try {
      await api(`/api/ocr/pages/${state.bookId}/${page}`, { method: "POST", body: JSON.stringify({ text }) });
      await refreshOcrStatus();
      toast(`第 ${page} 頁校樣已保存`);
    } catch (err) { toast(err.message, 4000); }
  }

  async function refreshOcrStatus() {    try {
      const data = await api(`/api/ocr/status?book=${state.bookId}`);
      state.ocr = data.ocr;
      if (state.ocr.done) {
        const avg = state.ocr.average_confidence;
        el.ocrState.textContent = `已識別 ${state.ocr.done} 頁 · 平均置信度 ${Math.round((avg || 0) * 100)}%`;
      } else {
        el.ocrState.textContent = "尚未開始";
      }
    } catch (_) {}
  }

  async function startOcr() {
    const start = Number(el.ocrStart.value);
    const end = Number(el.ocrEnd.value);
    if (!start || !end || start < 1 || end < start) { toast("請填寫有效的頁碼範圍"); return; }
    const quality = $("#ocrQualitySeg button.active")?.dataset.quality || "fast";
    try {
      const res = await api("/api/ocr/run", {
        method: "POST",
        body: JSON.stringify({ book_id: state.bookId, start, end, quality }),
      });
      el.ocrProgress.hidden = false;
      el.ocrBar.style.width = "0%";
      el.ocrProgressPct.textContent = "0%";
      el.ocrProgressText.textContent = `排隊中 · 第 ${start}–${end} 頁`;
      toast("OCR 任務已開始");
      pollOcr(res.job.id);
    } catch (err) { toast(err.message, 4000); }
  }

  function pollOcr(jobId) {
    clearInterval(state.ocrPoll);
    state.ocrPoll = setInterval(async () => {
      try {
        const { job } = await api(`/api/ocr/jobs/${jobId}`);
        const pct = job.total ? Math.round((job.done / job.total) * 100) : 0;
        el.ocrBar.style.width = pct + "%";
        el.ocrProgressPct.textContent = pct + "%";
        el.ocrProgressText.textContent = `${job.message} · ${job.current} / ${job.end}`;
        if (job.status === "done" || job.status === "error" || job.status === "cancelled") {
          clearInterval(state.ocrPoll);
          el.ocrProgressText.textContent = job.message;
          if (job.status === "done") {
            toast(`OCR 完成：${job.done} 頁`);
            await refreshOcrStatus();
          } else {
            toast(job.message, 5000);
          }
        }
      } catch (err) {
        clearInterval(state.ocrPoll);
        toast(err.message, 4000);
      }
    }, 1400);
  }

  // ---------- search ----------
  function openSearch() {
    el.searchModal.hidden = false;
    el.searchInput.value = "";
    el.searchResults.innerHTML = `<div class="search-empty">輸入關鍵詞開始檢索</div>`;
    setTimeout(() => el.searchInput.focus(), 60);
  }

  function doSearch() {
    clearTimeout(searchTimer);
    const q = el.searchInput.value.trim();
    if (!q) {
      el.searchResults.innerHTML = `<div class="search-empty">輸入關鍵詞開始檢索</div>`;
      return;
    }
    searchTimer = setTimeout(async () => {
      try {
        const { results } = await api(`/api/search?book=${state.bookId}&q=${encodeURIComponent(q)}`);
        if (!results.length) {
          el.searchResults.innerHTML = `<div class="search-empty">沒有找到「${esc(q)}」</div>`;
          return;
        }
        el.searchResults.innerHTML = results.map((r, i) => {
          const snippet = esc(r.snippet).replace(new RegExp(escapeReg(q), "g"), (m) => `<mark>${m}</mark>`);
          return `<button class="search-item" data-result="${i}"><b>${esc(r.chapter)}</b><p>${snippet}</p></button>`;
        }).join("");
        el.searchResults._results = results;
      } catch (err) {
        el.searchResults.innerHTML = `<div class="search-empty">${esc(err.message)}</div>`;
      }
    }, 260);
  }

  async function jumpToSearch(result) {
    el.searchModal.hidden = true;
    if (result.chapter_id !== state.chapterId) {
      await loadChapter(result.chapter_id, result.paragraph_id);
    } else {
      scrollToPid(result.paragraph_id);
    }
  }

  function escapeReg(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }

  // ---------- library ----------
  function renderLibrary() {
    el.libraryGrid.innerHTML = HISTORIES.map(([title, meta]) => {
      const available = title === "晉書";
      return `<button class="book-tile ${available ? "available" : "locked"}" data-title="${title}" data-available="${available}">
        <span class="bt-title">${title}</span>
        <span class="bt-meta">${meta}</span>
      </button>`;
    }).join("");
  }

  // ---------- clock ----------
  function tickClock() {
    if (!el.clock) return;
    const d = new Date();
    el.clock.textContent = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  }

  function cnNum(marker) {
    const map = { "1": "一", "2": "二", "3": "三", "4": "四", "5": "五", "6": "六", "7": "七", "8": "八", "9": "九", "10": "十" };
    return map[marker] || marker;
  }

  // ---------- events ----------
  function bindEvents() {
    el.layoutBtn.addEventListener("click", () => setLayout(state.layout === "vertical" ? "horizontal" : "vertical"));
    el.transBtn.addEventListener("click", () => toggleTrans());
    el.originalBtn.addEventListener("click", () => toggleOriginal());
    el.closeTrans.addEventListener("click", () => toggleTrans(false));
    el.closeOriginal.addEventListener("click", () => toggleOriginal(false));
    el.fontMinus.addEventListener("click", () => applyFont(state.fontSize - 1));
    el.fontPlus.addEventListener("click", () => applyFont(state.fontSize + 1));
    el.searchBtn.addEventListener("click", openSearch);
    el.settingsBtn.addEventListener("click", openSettings);
    el.libraryBtn.addEventListener("click", () => { renderLibrary(); el.libraryModal.hidden = false; });
    el.bookCard.addEventListener("click", () => { renderLibrary(); el.libraryModal.hidden = false; });
    el.originalImage.addEventListener("click", openImageViewer);
    el.themeBtn.addEventListener("click", cycleTheme);
    el.focusBtn.addEventListener("click", () => {
      document.body.classList.toggle("focus");
      el.focusBtn.classList.toggle("active", document.body.classList.contains("focus"));
      setTimeout(() => { if (state.chapter) renderReader(state.activePid); }, 60);
    });

    $$(".side-tabs button").forEach((b) => b.addEventListener("click", () => setSideTab(b.dataset.sideTab)));
    $$(".panel-tabs button").forEach((b) => b.addEventListener("click", () => setPanelTab(b.dataset.panelTab)));

    el.tocList.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-chapter]");
      if (!btn) return;
      const ch = state.chapters.find((x) => x.id === btn.dataset.chapter);
      if (!ch) return;
      if (ch.status !== "ready") { toast("此卷尚未 OCR。可在設定中選擇頁碼範圍先識別。"); return; }
      loadChapter(ch.id);
    });
    el.volumeList.addEventListener("click", () => toast("志、列傳、載記尚未導入。先把對應 PDF 放入書庫，再按卷識別。"));

    el.marksList.addEventListener("click", (e) => {
      const item = e.target.closest("[data-ann-id]");
      if (!item) return;
      openAnnotation(item.dataset.annId);
    });

    el.selectionMenu.addEventListener("mousedown", (e) => e.preventDefault());
    el.selectionMenu.addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-act]");
      if (!btn) return;
      const act = btn.dataset.act;
      const sel = state.pendingSelection;
      if (!sel) return;
      if (act === "copy") {
        try {
          await navigator.clipboard.writeText(sel.quote);
          toast("已複製");
        } catch (_) { toast("複製失敗，請手動選擇"); }
        hideSelection();
      } else if (act === "note") {
        openNoteModal(sel.quote);
        el.selectionMenu.hidden = true;
      } else if (act === "translate") {
        const q = sel.quote;
        hideSelection();
        translateSelection(q);
      } else {
        createMark(act);
      }
    });

    el.readerText.addEventListener("mouseup", () => setTimeout(handleSelection, 0));
    el.readerText.addEventListener("touchend", () => setTimeout(handleSelection, 120));
    el.readerText.addEventListener("click", (e) => {
      const fn = e.target.closest(".fn-ref");
      if (fn) { openFootnote(fn.dataset.marker, fn); return; }
      const ch = e.target.closest(".ch[data-ann]");
      if (ch) {
        const ids = ch.dataset.ann.split(",");
        if (ids.length) openAnnotation(ids[0]);
      }
    });

    el.readerScroll.addEventListener("scroll", () => {
      if (activeTimer) return;
      activeTimer = requestAnimationFrame(() => {
        activeTimer = 0;
        updateActive();
      });
    }, { passive: true });
    el.readerScroll.addEventListener("wheel", (e) => {
      if (state.layout !== "vertical") return;
      if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
        e.preventDefault();
        el.readerScroll.scrollLeft -= e.deltaY;
      }
    }, { passive: false });

    document.addEventListener("mousedown", (e) => {
      if (!e.target.closest("#selectionMenu")) hideSelection();
      if (!e.target.closest(".fn-popover") && !e.target.closest(".fn-ref")) closeFootnote();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        hideSelection(); closeFootnote();
        ["noteModal", "settingsModal", "libraryModal", "searchModal", "annotationModal", "ocrModal"].forEach((id) => { if (el[id]) el[id].hidden = true; });
      }
      if (e.key === "Escape" && document.body.classList.contains("focus")) {
        document.body.classList.remove("focus");
        el.focusBtn.classList.remove("active");
      }
    });

    $$(".modal-backdrop").forEach((b) => b.addEventListener("mousedown", (e) => {
      if (e.target === b) b.hidden = true;
    }));
    $$("[data-close]").forEach((b) => b.addEventListener("click", () => { el[b.dataset.close].hidden = true; }));

    el.saveNote.addEventListener("click", saveNote);
    el.translateCurrent.addEventListener("click", translateCurrent);
    el.deleteAnnotation.addEventListener("click", deleteAnnotation);
    el.editAnnotation.addEventListener("click", () => {
      const id = el.annotationModal.dataset.id;
      const ann = state.annotations.find((a) => a.id === id);
      if (!ann) return;
      el.annotationModal.hidden = true;
      openNoteModal(ann.quote, ann);
    });

    $$("#themeSeg button").forEach((b) => b.addEventListener("click", () => { applyTheme(b.dataset.theme); saveReaderPrefs(); }));
    $$("#layoutSeg button").forEach((b) => b.addEventListener("click", () => setLayout(b.dataset.layout)));
    el.fontRange.addEventListener("input", () => applyFont(Number(el.fontRange.value), false));
    el.fontRange.addEventListener("change", () => saveReaderPrefs());
    el.saveLlm.addEventListener("click", saveLlm);
    el.startOcr.addEventListener("click", startOcr);
    el.viewOcr.addEventListener("click", () => openOcrReview());
    el.ocrPageSelect.addEventListener("change", () => loadOcrPage(Number(el.ocrPageSelect.value)));
    el.saveOcr.addEventListener("click", saveOcrReview);
    el.copyOcr.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(el.ocrText.value); toast("已複製識別初稿"); }
      catch (_) { toast("複製失敗"); }
    });
    $$("#ocrQualitySeg button").forEach((b) => b.addEventListener("click", () => {
      $$("#ocrQualitySeg button").forEach((x) => x.classList.toggle("active", x === b));
    }));

    el.searchInput.addEventListener("input", doSearch);
    el.searchResults.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-result]");
      if (!btn) return;
      const results = el.searchResults._results || [];
      jumpToSearch(results[Number(btn.dataset.result)]);
    });

    el.libraryGrid.addEventListener("click", (e) => {
      const tile = e.target.closest("[data-title]");
      if (!tile) return;
      if (tile.dataset.available === "true") {
        el.libraryModal.hidden = true;
      } else {
        toast("請先把該史 PDF 放入專案目錄，再按卷導入與 OCR。");
      }
    });

    el.emptyOcrBtn.addEventListener("click", openSettings);

    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        if (state.chapter && state.layout === "vertical") renderReader(state.activePid);
      }, 260);
    });
  }

  init();
})();
