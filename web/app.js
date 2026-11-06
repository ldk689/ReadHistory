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
    bookId: null,
    chapterId: null,
    book: null,
    chapters: [],
    chapter: null,
    paragraphs: [],
    footnotes: [],
    annotations: [],
    library: [],
    layout: localStorage.getItem("qj-layout") || "vertical",
    theme: localStorage.getItem("qj-theme") || "paper",
    fontFamily: localStorage.getItem("qj-font-family") || "song",
    fontSize: Number(localStorage.getItem("qj-font") || 21),
    notesOpen: false,
    originalOpen: false,
    activePid: null,
    pendingSelection: null,
    editingAnn: null,
    ocr: null,
    ocrPoll: null,
    importJob: null,
    importJobPoll: null,
    importing: {
      file: null,
      id: null,
      meta: null,
      suggestion: null,
      layout: "auto",
      quality: "fast",
      uploading: false,
      analyzing: false,
      forcedRetry: false,
    },
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
    if (!res.ok) throw new Error(data.error || `請求失敗 (${res.status})`);
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
    applyFontFamily(state.fontFamily, false);
    tickClock();
    setInterval(tickClock, 30000);

    try {
      const lib = await api("/api/library");
      state.library = lib.books || [];
      const settings = await api("/api/settings");
      const reader = settings.reader || {};
      if (reader.theme) state.theme = reader.theme;
      if (reader.layout) state.layout = reader.layout;
      if (reader.fontSize) state.fontSize = Number(reader.fontSize);
      if (reader.fontFamily) state.fontFamily = reader.fontFamily;
      if (typeof reader.notesOpen === "boolean") state.notesOpen = reader.notesOpen;
      applyTheme(state.theme);
      applyLayout(state.layout, false);
      applyFont(state.fontSize, false);
      applyFontFamily(state.fontFamily, false);

      const params = new URLSearchParams(location.search);
      const hash = location.hash.match(/#\/read\/([\w-]+)(?:\/([\w-]+))?/);
      let bookId = hash && hash[1];
      if (!bookId) {
        const remembered = localStorage.getItem("qj-book");
        bookId = [remembered, "jinshu", state.library[0]?.id].find((id) => id && state.library.some((b) => b.id === id));
      }
      if (!bookId) throw new Error("書庫是空的。請先在「書庫」中導入一本 PDF。");
      const chapterId = hash && hash[2] ? hash[2] : null;
      el.notesPanel.hidden = !state.notesOpen;
      el.notesBtn.classList.toggle("active", state.notesOpen);
      el.app.hidden = false;
      await openBook(bookId, chapterId);
      await refreshOcrStatus();
      if (params.get("settings") === "1") setTimeout(openSettings, 350);
      if (params.get("library") === "1") setTimeout(() => { renderLibrary(); el.libraryModal.hidden = false; }, 350);
      if (params.get("import") === "1") setTimeout(openImport, 350);
      if (params.get("search") === "1") setTimeout(openSearch, 350);
      requestAnimationFrame(() => {
        el.boot.classList.add("done");
        setTimeout(() => { el.boot.hidden = true; }, 600);
      });
    } catch (err) {
      el.boot.querySelector(".boot-text").textContent = "書卷未能展開：" + err.message;
      el.boot.querySelector(".boot-line").style.display = "none";
      toast(err.message, 5000);
    }
  }

  function cacheEls() {
    const ids = [
      "boot", "app", "crumb", "layoutBtn", "layoutLabel", "notesBtn", "originalBtn",
      "fontMinus", "fontPlus", "fontValue", "searchBtn", "settingsBtn", "bookCard",
      "sideCover", "sideTitle", "sideMeta", "sideProgress", "sideProgressText", "sideVolumeCount",
      "tocList", "volumeList", "tocPane", "marksPane", "marksList", "markCount",
      "libraryBtn", "importBtn", "chapterKicker", "chapterTitle", "chapterSub", "chapterMeta",
      "readerStage", "readerScroll", "readerText", "readerEmpty", "emptyOcrBtn",
      "originalPanel", "originalImage", "originalPageLabel", "closeOriginal",
      "notesPanel", "closeNotes", "notesBody", "notesIntro", "footnoteList", "statusText",
      "posText", "focusBtn", "themeBtn", "clock", "selectionMenu", "noteModal",
      "noteQuote", "noteInput", "saveNote", "settingsModal", "themeSeg", "layoutSeg", "fontSeg",
      "fontRange", "fontRangeValue", "ocrStart", "ocrEnd", "ocrQualitySeg", "ocrProgress",
      "ocrProgressText", "ocrProgressPct", "ocrBar", "ocrState", "startOcr",
      "ocrModal", "ocrPageSelect", "ocrConfidence", "ocrText", "copyOcr", "saveOcr", "viewOcr",
      "libraryModal", "libraryGrid", "importedGrid", "librarySummary", "libraryImportBtn",
      "searchModal", "searchTitle", "searchInput", "searchResults",
      "annotationModal", "annotationQuote", "annotationText", "annotationMeta",
      "deleteAnnotation", "editAnnotation", "toast",
      "importModal", "importDrop", "importFile", "importFileName", "importDropTitle",
      "importDetail", "importPreview", "importPreviewEmpty", "importBookTitle", "importAuthor",
      "importChapterTitle", "importLayoutSeg", "importRotation", "importDetectState", "importStart", "importEnd",
      "importQualitySeg", "importProgress", "importProgressText", "importProgressPct",
      "importProgressBar", "importAnalyzeBtn", "importCommitBtn", "importHint",
    ];
    ids.forEach((id) => { el[id] = document.getElementById(id); });
    el.boot.querySelector(".boot-text").textContent = "正在展開書卷";
  }

  function coverUrl(cover) {
    if (!cover) return "/assets/cover-jinshu.jpg";
    if (/^(https?:)?\/\//.test(cover) || cover.startsWith("/")) return cover;
    return "/assets/" + cover.replace(/^\.?\//, "");
  }

  function bookStatusLabel(book) {
    if (book.status === "importing") return "識別中";
    if (book.imported) return "已導入";
    return "樣章";
  }

  // ---------- book ----------
  async function openBook(bookId, chapterId = null) {
    state.bookId = bookId;
    localStorage.setItem("qj-book", bookId);
    const data = await api(`/api/books/${bookId}`);
    state.book = data.book;
    state.chapters = data.chapters || [];
    const wanted = chapterId && state.chapters.find((c) => c.id === chapterId);
    const libBook = state.library.find((b) => b.id === bookId);
    const progressId = libBook && libBook.progress && libBook.progress.chapter_id;
    const progressChapter = state.chapters.find((c) => c.id === progressId && c.status === "ready");
    const target = wanted || progressChapter || state.chapters.find((c) => c.status === "ready") || state.chapters[0];
    state.annotations = [];
    state.footnotes = [];
    state.paragraphs = [];
    state.chapter = null;
    state.chapterId = null;
    renderSidebar();
    if (target) {
      await loadChapter(target.id);
    } else {
      renderChapterHeadEmpty();
      renderReader();
    }
    await refreshOcrStatus();
  }

  function renderChapterHeadEmpty() {
    if (!state.book) return;
    el.crumb.innerHTML = `<span>${esc(state.book.title)}</span>`;
    el.chapterKicker.textContent = state.book.title;
    el.chapterTitle.textContent = state.book.imported ? "識別中" : "未展開";
    el.chapterSub.textContent = "";
    el.chapterMeta.textContent = state.book.author || "";
    el.statusText.textContent = bookStatusLabel(state.book);
    el.posText.textContent = "尚無正文";
    el.tocList.innerHTML = "";
    el.marksList.innerHTML = "";
  }

  function renderSidebar() {
    const b = state.book;
    if (!b) return;
    el.sideCover.src = coverUrl(b.cover);
    el.sideTitle.textContent = b.title;
    el.sideMeta.textContent = b.author || bookStatusLabel(b);
    const chapters = state.chapters.length || 1;
    const ready = state.chapters.filter((c) => c.status === "ready").length;
    el.sideProgress.style.width = Math.max(6, Math.round((ready / chapters) * 100)) + "%";
    el.sideProgressText.textContent = state.chapter
      ? `${state.chapter.volume || ""} · ${state.chapter.subtitle || state.chapter.title}`
      : "尚未展開";
    el.sideVolumeCount.textContent = `${chapters} 卷`;
    renderToc();
    renderVolumeList();
    el.markCount.textContent = String(state.annotations.length);
  }

  function renderToc() {
    const current = state.chapterId;
    if (!state.chapters.length) {
      el.tocList.innerHTML = `<div class="mark-empty">此書尚無目錄。</div>`;
      return;
    }
    el.tocList.innerHTML = state.chapters.map((ch) => {
      const locked = ch.status !== "ready";
      const label = ch.status === "importing" ? "識別中" : locked ? "待識別" : "可讀";
      return `<button class="toc-item ${ch.id === current ? "active" : ""} ${locked ? "locked" : ""}" data-chapter="${ch.id}">
        <span class="toc-vol">${esc(ch.volume || "")}</span>
        <span class="toc-main"><b>${esc(ch.title)}</b><span>${esc(ch.subtitle || "")}</span></span>
        <span class="toc-status">${label}</span>
      </button>`;
    }).join("");
  }

  function renderVolumeList() {
    if (state.book && state.book.imported) {
      const ch = state.chapters[0];
      el.volumeList.innerHTML = ch
        ? `<div class="volume-note">全書共 ${state.book.total_pages || 0} 頁；本次導入 ${ch.page_start || 1}–${ch.page_end || 1} 頁，機器識別後可直接閱讀與校對。</div>`
        : `<div class="volume-note">尚未建立卷次。</div>`;
      return;
    }
    el.volumeList.innerHTML = [
      ["志 · 二十卷", "待導入"], ["列傳 · 七十卷", "待導入"], ["載記 · 三十卷", "待導入"],
    ].map(([a, b]) => `<button class="volume-item" data-locked="1"><span>${a}</span><span>${b}</span></button>`).join("");
  }

  function renderChapterHead() {
    const b = state.book;
    const ch = state.chapter;
    if (!b || !ch) return;
    el.crumb.innerHTML = `<span>${esc(b.title)}</span><i>/</i><span>${esc(ch.volume)}</span><i>/</i><b>${esc(ch.title)}</b>`;
    el.chapterKicker.textContent = `${b.title} · ${ch.volume || ""}`;
    el.chapterTitle.textContent = ch.title;
    el.chapterSub.textContent = ch.subtitle || "";
    el.chapterMeta.textContent = [b.author, b.edition ? `據${b.edition}` : ""].filter(Boolean).join(" · ");
    document.title = `${b.title} ${ch.volume || ""} ${ch.title} · 青简`;
  }

  function renderChapterMeta() {
    const ch = state.chapter;
    if (!ch) return;
    const status = ch.status === "importing" ? "識別中"
      : state.book?.imported ? "機器識別 · 待校對"
      : "已校對";
    el.statusText.textContent = `${ch.volume || ""} · ${status}`;
    el.sideProgressText.textContent = `${ch.volume || ""} · ${ch.subtitle || ""}`;
    el.posText.textContent = state.paragraphs.length ? `第 1 段 / ${state.paragraphs.length}` : "尚無正文";
  }

  async function loadChapter(chapterId, targetPid = null) {
    const data = await api(`/api/books/${state.bookId}/chapters/${chapterId}`);
    state.chapter = data.chapter;
    state.chapterId = data.chapter.id;
    state.paragraphs = data.paragraphs || [];
    state.footnotes = data.footnotes || [];
    state.annotations = data.annotations || [];
    const restorePid = targetPid || (data.progress && data.progress.paragraph_id) || null;
    state.activePid = restorePid || state.paragraphs[0]?.id || null;

    renderChapterHead();
    renderChapterMeta();
    renderReader(restorePid);
    renderMarks();
    renderFootnotes();
    renderToc();
    if (state.notesOpen) el.notesPanel.hidden = false;
    if (state.originalOpen) {
      el.originalPanel.hidden = false;
      el.originalBtn.classList.add("active");
      updateOriginal();
    }
    history.replaceState(null, "", `#/read/${state.bookId}/${chapterId}`);
    saveProgress();
  }

  // ---------- rendering ----------
  function renderReader(preservePid = null) {
    state.suppressActive = true;
    el.readerText.innerHTML = "";
    const empty = state.paragraphs.length === 0;
    el.readerEmpty.hidden = !empty;
    el.readerText.hidden = empty;
    el.readerScroll.classList.toggle("vertical", state.layout === "vertical");
    if (empty) {
      const importing = state.chapter && state.chapter.status === "importing";
      const h2 = el.readerEmpty.querySelector("h2");
      const p = el.readerEmpty.querySelector("p");
      if (h2) h2.textContent = importing ? "正在識別此卷" : "此卷尚未展開";
      if (p) p.textContent = importing
        ? "OCR 正在逐頁識別。完成後本頁會自動更新；識別期間可以切到別的書。"
        : "掃描頁需要先經 OCR 與校對。可在設置中選擇頁碼範圍先識別，或直接導入一本 PDF。";
      el.emptyOcrBtn.hidden = importing;
    }
    if (!empty) {
      if (state.layout === "vertical") {
        el.readerText.className = "reader-text vertical";
        renderVertical();
      } else {
        el.readerText.className = "reader-text horizontal";
        renderHorizontal();
      }
    }
    state.suppressActive = false;

    requestAnimationFrame(() => {
      if (empty) return;
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
      el.marksList.innerHTML = `<div class="mark-empty">還沒有批註。<br>選中正文，寫下第一條考證。</div>`;
      return;
    }
    const sorted = [...state.annotations].sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)));
    el.marksList.innerHTML = sorted.map((ann) => {
      const p = state.paragraphs.find((x) => Number(x.id) === Number(ann.paragraph_id));
      const kind = ann.kind === "note" ? "批註" : ann.kind === "underline" ? "劃線" : "高亮";
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
    const ch = state.chapter;
    el.notesIntro.textContent = state.book?.imported
      ? "此書由 OCR 導入。校勘記需另行整理；正文中的〔一〕標記可點擊查看。"
      : "中華書局點校本的校勘記，隨正文標記顯示。";
    if (!state.footnotes.length) {
      el.footnoteList.innerHTML = `<div class="mark-empty">本卷暫無校勘記。</div>`;
      return;
    }
    el.footnoteList.innerHTML = state.footnotes.map((n) => `<div class="footnote-item">
      <span class="fn-num">${esc(n.marker)}</span>
      <div class="fn-text">${esc(n.text)}<span class="fn-page">第 ${n.page || "—"} 頁</span></div>
    </div>`).join("");
  }

  // ---------- navigation ----------
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

  // ---------- original ----------
  function updateOriginal() {
    const p = state.paragraphs.find((x) => Number(x.id) === Number(state.activePid));
    if (!p) return;
    const page = p.page_start || state.chapter?.page_start || 1;
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
    viewer.innerHTML = `<button aria-label="關閉">×</button><img src="${esc(el.originalImage.src)}" alt="原掃描頁">`;
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
    const width = menu.offsetWidth || 240;
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
    if (!note) { toast("批註內容不能為空"); return; }
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
        toast("批註已更新");
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
      toast("批註已保存");
    } catch (err) { toast(err.message, 4000); }
  }

  function openAnnotation(id) {
    const ann = state.annotations.find((a) => a.id === id);
    if (!ann) return;
    const p = state.paragraphs.find((x) => Number(x.id) === Number(ann.paragraph_id));
    el.annotationQuote.textContent = ann.quote;
    el.annotationText.textContent = ann.note || "（這是一條劃線標記，沒有文字批註。）";
    el.annotationMeta.textContent = p ? `第 ${p.order_no} 段 · 第 ${p.page_start} 頁` : "";
    el.annotationModal.dataset.id = id;
    el.annotationModal.hidden = false;
  }

  async function deleteAnnotation() {
    const id = el.annotationModal.dataset.id;
    if (!id) return;
    if (!confirm("刪除這條批註？")) return;
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
    pop.innerHTML = `<div class="fn-pop-head"><span>校勘記 · 〔${esc(note.marker)}〕</span><button aria-label="關閉">×</button></div>
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
    el.layoutLabel.textContent = layout === "vertical" ? "豎排" : "橫排";
    el.layoutBtn.classList.toggle("active", layout === "vertical");
    el.readerScroll.classList.toggle("vertical", layout === "vertical");
    $$("#layoutSeg button").forEach((b) => b.classList.toggle("active", b.dataset.layout === layout));
    if (state.chapter) {
      renderReader(state.activePid);
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

  function applyFontFamily(font, save = true) {
    state.fontFamily = ["song", "hei", "kai"].includes(font) ? font : "song";
    document.body.dataset.font = state.fontFamily;
    $$("#fontSeg button").forEach((b) => b.classList.toggle("active", b.dataset.font === state.fontFamily));
    localStorage.setItem("qj-font-family", state.fontFamily);
    if (save) saveReaderPrefs();
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
        body: JSON.stringify({
          layout: state.layout, theme: state.theme, fontSize: state.fontSize,
          fontFamily: state.fontFamily, notesOpen: state.notesOpen,
        }),
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

  function toggleNotes(force) {
    state.notesOpen = typeof force === "boolean" ? force : !state.notesOpen;
    el.notesPanel.hidden = !state.notesOpen;
    el.notesBtn.classList.toggle("active", state.notesOpen);
    if (state.notesOpen) renderFootnotes();
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
    await refreshOcrStatus();
    el.fontRange.value = state.fontSize;
    el.fontRangeValue.textContent = state.fontSize + " px";
    $$("#layoutSeg button").forEach((b) => b.classList.toggle("active", b.dataset.layout === state.layout));
    $$("#fontSeg button").forEach((b) => b.classList.toggle("active", b.dataset.font === state.fontFamily));
    $$("#themeSeg button").forEach((b) => b.classList.toggle("active", b.dataset.theme === state.theme));
    if (state.book) {
      const total = state.book.total_pages || 1;
      const ch = state.chapters[0];
      el.ocrStart.value = ch?.page_start || 1;
      el.ocrEnd.value = Math.min(ch?.page_end || total, (ch?.page_start || 1) + 3);
      el.ocrStart.max = total;
      el.ocrEnd.max = total;
    }
    if (state.ocr) {
      const done = state.ocr.done || 0;
      const avg = state.ocr.average_confidence;
      el.ocrState.textContent = avg ? `已識別 ${done} 頁 · 平均置信度 ${Math.round(avg * 100)}%` : "尚未開始";
    }
    el.settingsModal.hidden = false;
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

  async function refreshOcrStatus() {
    if (!state.bookId) return;
    try {
      const data = await api(`/api/ocr/status?book=${state.bookId}`);
      state.ocr = data.ocr;
    } catch (_) { return; }
    if (state.ocr.done) {
      const avg = state.ocr.average_confidence;
      el.ocrState.textContent = `已識別 ${state.ocr.done} 頁 · 平均置信度 ${Math.round((avg || 0) * 100)}%`;
    } else {
      el.ocrState.textContent = "尚未開始";
    }
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
      pollOcr(res.job, true);
    } catch (err) { toast(err.message, 4000); }
  }

  function pollOcr(job, reloadWhenDone = false) {
    clearInterval(state.ocrPoll);
    state.ocrPoll = setInterval(async () => {
      try {
        const { job: info } = await api(`/api/ocr/jobs/${job.id}`);
        const pct = info.total ? Math.round((info.done / info.total) * 100) : 0;
        el.ocrBar.style.width = pct + "%";
        el.ocrProgressPct.textContent = pct + "%";
        el.ocrProgressText.textContent = info.message;
        if (["done", "error", "cancelled"].includes(info.status)) {
          clearInterval(state.ocrPoll);
          el.ocrProgressText.textContent = info.message;
          if (info.status === "done") {
            toast(`OCR 完成：${info.done} 頁`);
            await refreshOcrStatus();
            if (reloadWhenDone && info.book_id === state.bookId && state.chapterId === info.chapter_id) {
              await loadChapter(state.chapterId);
              renderSidebar();
            }
          } else {
            toast(info.message, 5000);
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
    el.searchTitle.textContent = state.book ? `在《${state.book.title}》中查找` : "在書中查找";
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
  async function renderLibrary() {
    try {
      const lib = await api("/api/library");
      state.library = lib.books || [];
    } catch (_) { /* keep current */ }
    const imported = state.library.filter((b) => b.imported);
    const samples = state.library.filter((b) => !b.imported).length;
    el.librarySummary.textContent = `書庫 ${state.library.length} 部 · 導入 ${imported.length} 部${samples ? ` · 樣章 ${samples} 部` : ""} · 本地保存`;
    el.importedGrid.innerHTML = imported.length
      ? imported.map((b) => `<button class="book-tile imported ${b.id === state.bookId ? "current" : ""}" data-book="${b.id}">
          <span class="bt-state">${bookStatusLabel(b)}</span>
          <span class="bt-title">${esc(b.title)}</span>
          <span class="bt-meta">${esc(b.author || "導入本")} · ${b.total_pages || 0} 頁</span>
        </button>`).join("")
      : `<div class="library-empty">還沒有導入的書。點右上角「導入 PDF」，選擇一本掃描本即可。</div>`;

    el.libraryGrid.innerHTML = HISTORIES.map(([title, meta]) => {
      const book = state.library.find((b) => b.title === title);
      const available = Boolean(book);
      return `<button class="book-tile ${available ? "available" : "locked"}" data-title="${title}" data-book="${book ? book.id : ""}">
        <span class="bt-title">${title}</span>
        <span class="bt-meta">${meta}</span>
      </button>`;
    }).join("");
  }

  async function switchBook(bookId) {
    if (!bookId) return;
    if (bookId === state.bookId) { el.libraryModal.hidden = true; return; }
    try {
      el.libraryModal.hidden = true;
      await openBook(bookId);
    } catch (err) {
      toast(err.message, 4000);
    }
  }

  // ---------- import ----------
  function openImport() {
    state.importing = {
      file: null, id: null, meta: null, suggestion: null,
      layout: "auto", quality: "fast", uploading: false, analyzing: false,
    };
    el.importFile.value = "";
    el.importDetail.hidden = true;
    el.importProgress.hidden = true;
    el.importPreview.hidden = true;
    el.importPreviewEmpty.hidden = false;
    el.importFileName.textContent = "文件只保存在本機";
    el.importDropTitle.textContent = "選擇或拖入 PDF";
    el.importHint.textContent = "PDF 只保存在本機，不上傳。導入後可逐頁校對。";
    el.importAnalyzeBtn.disabled = true;
    el.importCommitBtn.disabled = true;
    $$("#importLayoutSeg button").forEach((b) => b.classList.toggle("active", b.dataset.layout === "auto"));
    el.importRotation.value = "auto";
    $$("#importQualitySeg button").forEach((b) => b.classList.toggle("active", b.dataset.quality === "fast"));
    el.importModal.hidden = false;
  }

  function pickImportFile(file) {
    if (!file) return;
    if (!/\.pdf$/i.test(file.name) && file.type !== "application/pdf") {
      toast("請選擇 PDF 文件");
      return;
    }
    state.importing.file = file;
    el.importFileName.textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(1)} MB`;
    el.importDropTitle.textContent = "更換文件";
    uploadImport(file);
  }

  function uploadImport(file) {
    const xhr = new XMLHttpRequest();
    state.importing.uploading = true;
    el.importDetail.hidden = true;
    el.importProgress.hidden = false;
    el.importProgressBar.style.width = "0%";
    el.importProgressPct.textContent = "0%";
    el.importProgressText.textContent = "正在讀取 PDF…";
    el.importCommitBtn.disabled = true;
    el.importAnalyzeBtn.disabled = true;
    xhr.open("POST", "/api/import/upload");
    xhr.setRequestHeader("Content-Type", "application/pdf");
    xhr.setRequestHeader("X-Filename", encodeURIComponent(file.name));
    xhr.upload.onprogress = (e) => {
      if (!e.lengthComputable) return;
      const pct = Math.round((e.loaded / e.total) * 100);
      el.importProgressBar.style.width = pct + "%";
      el.importProgressPct.textContent = pct + "%";
    };
    xhr.onload = () => {
      state.importing.uploading = false;
      let data = {};
      try { data = JSON.parse(xhr.responseText || "{}"); } catch (_) {}
      if (xhr.status < 200 || xhr.status >= 300) {
        el.importProgress.hidden = true;
        toast(data.error || "PDF 讀取失敗", 5000);
        return;
      }
      const meta = data.import;
      state.importing.id = meta.id;
      state.importing.meta = meta;
      state.importing.suggestion = null;
      el.importProgress.hidden = true;
      el.importDetail.hidden = false;
      el.importPreview.src = `/api/imports/${meta.id}/preview?t=${Date.now()}`;
      el.importPreview.hidden = false;
      el.importPreviewEmpty.hidden = true;
      el.importBookTitle.value = meta.title || "";
      el.importAuthor.value = meta.author || "";
      el.importChapterTitle.value = "全書";
      el.importStart.value = 1;
      el.importStart.max = meta.pages;
      el.importEnd.value = Math.min(meta.pages, 20);
      el.importEnd.max = meta.pages;
      el.importDetectState.textContent = `共 ${meta.pages} 頁。先試讀第 1 頁，判斷豎排或橫排…`;
      el.importAnalyzeBtn.disabled = false;
      el.importCommitBtn.disabled = false;
      analyzeImport();
    };
    xhr.onerror = () => {
      state.importing.uploading = false;
      el.importProgress.hidden = true;
      toast("PDF 上傳失敗，請重試", 5000);
    };
    xhr.send(file);
  }

  async function analyzeImport() {
    const imp = state.importing;
    if (!imp.id || imp.analyzing) return;
    imp.analyzing = true;
    el.importAnalyzeBtn.disabled = true;
    el.importCommitBtn.disabled = true;
    el.importDetectState.textContent = "正在試讀一兩頁，判斷版式與方向…（約 5–15 秒）";
    el.importProgress.hidden = false;
    el.importProgressBar.style.width = "35%";
    el.importProgressPct.textContent = "…";
    el.importProgressText.textContent = "首次識別會載入 OCR 模型";
    try {
      const payload = {
        id: imp.id,
        layout: imp.layout === "auto" ? "auto" : imp.layout,
        page: Number(el.importStart.value) || 1,
      };
      const res = await api("/api/import/analyze", { method: "POST", body: JSON.stringify(payload) });
      imp.suggestion = res.suggestion;
      const s = res.suggestion;
      const names = { vertical: "豎排", horizontal: "橫排" };
      const agree = imp.layout === "auto" || imp.layout === s.layout;
      el.importDetectState.innerHTML = `判斷：<b>${names[s.layout]}</b> · 置信度 ${Math.round((s.confidence || 0) * 100)}% · 掃描方向 ${s.rotation}°`
        + (agree ? "" : `（你手動選擇了${names[imp.layout]}，將以手動為準）`)
        + (s.pages && s.pages[0] ? `<br><span class="detect-sample">試讀：${esc(s.pages[0].sample || "").slice(0, 48)}…</span>` : "")
        + (s.warning ? `<br><span class="detect-warning">${esc(s.warning)}</span>` : "");
      el.importProgress.hidden = true;
      el.importCommitBtn.disabled = false;
      el.importHint.textContent = `將識別第 ${el.importStart.value}–${el.importEnd.value} 頁。頁數多時需要較長時間，可在識別期間先離開此視窗。`;
    } catch (err) {
      el.importDetectState.textContent = "自動判斷失敗：" + err.message + "。請手動選擇豎排或橫排，再按「重新識別版式」。";
      el.importProgress.hidden = true;
      el.importCommitBtn.disabled = !imp.id;
    } finally {
      imp.analyzing = false;
      el.importAnalyzeBtn.disabled = !imp.id;
      if (imp.layout !== "auto" && imp.suggestion && imp.suggestion.layout !== imp.layout && !imp.forcedRetry) {
        imp.forcedRetry = true;
        setTimeout(analyzeImport, 120);
      }
    }
  }

  async function commitImport() {
    const imp = state.importing;
    if (!imp.id || !imp.meta) return;
    const start = Number(el.importStart.value);
    const end = Number(el.importEnd.value);
    if (!start || !end || start < 1 || end < start || end > imp.meta.pages) {
      toast("請填寫有效的頁碼範圍");
      return;
    }
    const layout = imp.layout === "auto" ? imp.suggestion?.layout : imp.layout;
    if (!layout) { toast("請先按「重新識別版式」，或手動選擇豎排/橫排"); return; }
    const rotation = el.importRotation.value !== "auto"
      ? Number(el.importRotation.value)
      : (imp.suggestion && imp.suggestion.layout === layout ? imp.suggestion.rotation : 0);
    const quality = $("#importQualitySeg button.active")?.dataset.quality || "fast";
    el.importCommitBtn.disabled = true;
    el.importAnalyzeBtn.disabled = true;
    el.importProgress.hidden = false;
    el.importProgressBar.style.width = "6%";
    el.importProgressPct.textContent = "0%";
    el.importProgressText.textContent = "正在建立書庫與卷次…";
    try {
      const res = await api("/api/import/commit", {
        method: "POST",
        body: JSON.stringify({
          id: imp.id,
          title: el.importBookTitle.value.trim(),
          author: el.importAuthor.value.trim(),
          chapter_title: el.importChapterTitle.value.trim(),
          layout, rotation, start, end, quality,
        }),
      });
      imp.id = null;
      state.importJob = res.job;
      el.importModal.hidden = true;
      toast(`已開始識別《${res.book.title}》：第 ${start}–${end} 頁`, 4200);
      await openBook(res.book.id, res.chapter.id);
      pollImportJob(res.job, res.book.id, res.chapter.id);
    } catch (err) {
      toast(err.message, 5000);
      el.importProgress.hidden = true;
      el.importCommitBtn.disabled = false;
      el.importAnalyzeBtn.disabled = false;
    }
  }

  function pollImportJob(job, bookId, chapterId) {
    clearInterval(state.importJobPoll);
    state.importJobPoll = setInterval(async () => {
      try {
        const { job: info } = await api(`/api/ocr/jobs/${job.id}`);
        state.importJob = info;
        if (state.bookId === bookId) {
          el.statusText.textContent = info.status === "running"
            ? `識別中 · 第 ${info.current} / ${info.end} 頁`
            : info.message;
          if (state.chapterId === chapterId && info.status === "running" && info.done > 0) {
            const data = await api(`/api/books/${bookId}/chapters/${chapterId}`);
            if ((data.paragraphs || []).length !== state.paragraphs.length) {
              state.paragraphs = data.paragraphs || [];
              state.chapter = data.chapter;
              renderReader(state.activePid);
              renderChapterMeta();
              renderSidebar();
            }
          }
        }
        if (["done", "error", "cancelled"].includes(info.status)) {
          clearInterval(state.importJobPoll);
          if (info.status === "done") {
            toast(`《${state.book?.title || "新書"}》識別完成：${info.done} 頁`, 4000);
            await renderLibrary();
            if (state.bookId === bookId) {
              await openBook(bookId, chapterId);
            }
          } else {
            toast(info.message, 6000);
          }
        }
      } catch (err) {
        clearInterval(state.importJobPoll);
        toast(err.message, 4000);
      }
    }, 1800);
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
    el.notesBtn.addEventListener("click", () => toggleNotes());
    el.originalBtn.addEventListener("click", () => toggleOriginal());
    el.closeNotes.addEventListener("click", () => toggleNotes(false));
    el.closeOriginal.addEventListener("click", () => toggleOriginal(false));
    el.fontMinus.addEventListener("click", () => applyFont(state.fontSize - 1));
    el.fontPlus.addEventListener("click", () => applyFont(state.fontSize + 1));
    el.searchBtn.addEventListener("click", openSearch);
    el.settingsBtn.addEventListener("click", openSettings);
    el.libraryBtn.addEventListener("click", () => { renderLibrary(); el.libraryModal.hidden = false; });
    el.bookCard.addEventListener("click", () => { renderLibrary(); el.libraryModal.hidden = false; });
    el.importBtn.addEventListener("click", openImport);
    el.libraryImportBtn.addEventListener("click", () => { el.libraryModal.hidden = true; openImport(); });
    el.originalImage.addEventListener("click", openImageViewer);
    el.themeBtn.addEventListener("click", cycleTheme);
    el.focusBtn.addEventListener("click", () => {
      document.body.classList.toggle("focus");
      el.focusBtn.classList.toggle("active", document.body.classList.contains("focus"));
      setTimeout(() => { if (state.chapter) renderReader(state.activePid); }, 60);
    });

    $$(".side-tabs button").forEach((b) => b.addEventListener("click", () => setSideTab(b.dataset.sideTab)));

    el.tocList.addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-chapter]");
      if (!btn) return;
      const ch = state.chapters.find((x) => x.id === btn.dataset.chapter);
      if (!ch) return;
      if (ch.status === "importing") { toast("此卷仍在識別中"); return; }
      if (ch.status !== "ready") { toast("此卷尚未 OCR。可在設置中選擇頁碼範圍先識別。"); return; }
      await loadChapter(ch.id);
    });
    el.volumeList.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-chapter]");
      if (btn) { loadChapter(btn.dataset.chapter); return; }
      if (e.target.closest("[data-locked]")) toast("志、列傳、載記尚未導入。可導入對應 PDF 後建立卷次。");
    });

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
        ["noteModal", "settingsModal", "libraryModal", "searchModal", "annotationModal", "ocrModal", "importModal"].forEach((id) => { if (el[id]) el[id].hidden = true; });
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
    $$("#fontSeg button").forEach((b) => b.addEventListener("click", () => {
      applyFontFamily(b.dataset.font);
      toast(b.dataset.font === "kai" ? "已切換為楷體（優先使用本機霞鶩文楷/楷體）" : b.dataset.font === "hei" ? "已切換為黑體" : "已切換為宋體");
    }));
    el.fontRange.addEventListener("input", () => applyFont(Number(el.fontRange.value), false));
    el.fontRange.addEventListener("change", () => saveReaderPrefs());
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
    $$("#importQualitySeg button").forEach((b) => b.addEventListener("click", () => {
      $$("#importQualitySeg button").forEach((x) => x.classList.toggle("active", x === b));
    }));

    el.searchInput.addEventListener("input", doSearch);
    el.searchResults.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-result]");
      if (!btn) return;
      const results = el.searchResults._results || [];
      jumpToSearch(results[Number(btn.dataset.result)]);
    });

    el.importedGrid.addEventListener("click", (e) => {
      const tile = e.target.closest("[data-book]");
      if (tile) switchBook(tile.dataset.book);
    });
    el.libraryGrid.addEventListener("click", (e) => {
      const tile = e.target.closest("[data-title]");
      if (!tile) return;
      if (tile.dataset.book) switchBook(tile.dataset.book);
      else toast("這部史書尚未導入。點「導入 PDF」，選擇你自己的掃描本。");
    });

    // import modal
    el.importDrop.addEventListener("click", (e) => {
      if (e.target !== el.importFile) el.importFile.click();
    });
    el.importFile.addEventListener("change", () => pickImportFile(el.importFile.files[0]));
    el.importDrop.addEventListener("dragover", (e) => { e.preventDefault(); el.importDrop.classList.add("drag"); });
    el.importDrop.addEventListener("dragleave", () => el.importDrop.classList.remove("drag"));
    el.importDrop.addEventListener("drop", (e) => {
      e.preventDefault();
      el.importDrop.classList.remove("drag");
      const file = e.dataTransfer.files && e.dataTransfer.files[0];
      pickImportFile(file);
    });
    $$("#importLayoutSeg button").forEach((b) => b.addEventListener("click", () => {
      state.importing.layout = b.dataset.layout;
      state.importing.forcedRetry = false;
      $$("#importLayoutSeg button").forEach((x) => x.classList.toggle("active", x === b));
      if (state.importing.id && b.dataset.layout !== "auto") analyzeImport();
    }));
    el.importAnalyzeBtn.addEventListener("click", analyzeImport);
    el.importCommitBtn.addEventListener("click", commitImport);
    el.importStart.addEventListener("change", () => {
      if (!state.importing.id) return;
      state.importing.suggestion = null;
      el.importDetectState.textContent = "起始頁已變更，請按「重新識別版式」重新判斷，或手動選擇版式與方向。";
      el.importCommitBtn.disabled = true;
      el.importAnalyzeBtn.disabled = false;
    });
    el.importEnd.addEventListener("change", () => {
      el.importHint.textContent = `將識別第 ${el.importStart.value}–${el.importEnd.value} 頁。頁數多時需要較長時間。`;
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
