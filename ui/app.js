const CONFIG_URLS = ["./config/app.json", "../config/app.json"];
const DEFAULT_SUMMARY_PATH = "../data/summary.json";
const DEFAULT_GPT_PATH = "../data/gpt_insights.json";
const WORD_CHART_COLORS = ["#fb7185", "#f472b6", "#a855f7", "#22d3ee", "#4ade80", "#fde68a"];

const layoutRows = [
  ["Tab", "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "Backspace"],
  ["Caps", "A", "S", "D", "F", "G", "H", "J", "K", "L", ";", "Enter"],
  ["Shift", "Z", "X", "C", "V", "B", "N", "M", ",", ".", "/", "Shift"],
  ["Ctrl", "Option", "Cmd", "Space", "Cmd", "Option", "Ctrl"],
];

const leftHandKeys = new Set([
  "q",
  "w",
  "e",
  "r",
  "t",
  "a",
  "s",
  "d",
  "f",
  "g",
  "z",
  "x",
  "c",
  "v",
  "b",
]);

const letterSet = new Set("abcdefghijklmnopqrstuvwxyz".split(""));

const layoutSpans = {
  Tab: 2,
  Backspace: 2,
  Caps: 2,
  Enter: 2,
  Shift: 2,
  Ctrl: 2,
  Win: 1,
  Alt: 1,
  Option: 1,
  Cmd: 1,
  Space: 4,
};

const builders = {
  overview: buildOverviewCube,
  keys: buildKeysCube,
  words: buildWordsCube,
  transitions: buildTransitionsCube,
  layout: buildLayoutCube,
  heatmap: buildHeatmapCube,
  story: buildStoryCube,
  gpt: buildGPTCube,
  presser: buildPresserCube,
};

let CURRENT_UI_TEXT = {};
const DEFAULT_VISUAL = {
  word_pie_limit: 20,
  transition_limit: 8,
  heatmap_top_words: 24,
  word_flow_neighbors: 3,
  layout_neighbor_limit: 3,
  layout_show_full_adjacency: false,
  story_card_width: 320,
};
let CURRENT_VISUAL = { ...DEFAULT_VISUAL };
const CONFIG_STATUS_EL = document.getElementById("config-status");
let configStatusTimer = null;

function buildAssetCandidates(rawPath) {
  const trimmed = (rawPath || "").trim();
  if (!trimmed) return [];
  if (trimmed.startsWith("http") || trimmed.startsWith("/")) {
    return [trimmed];
  }
  const cleaned = trimmed.replace(/^(\.\/)+/, "").replace(/^(\.\.\/)+/, "");
  const candidates = [];
  const add = (value) => {
    if (!value) return;
    if (!candidates.includes(value)) {
      candidates.push(value);
    }
  };
  add(`./${cleaned}`);
  add(`../${cleaned}`);
  if (trimmed.startsWith("./") || trimmed.startsWith("../")) {
    add(trimmed);
  }
  return candidates.filter(Boolean);
}

async function loadJsonWithFallback(candidates, label = "asset") {
  const attempts = [];
  for (const candidate of candidates) {
    try {
      const payload = await loadJson(candidate);
      updateConfigStatus(`Loaded ${label} from ${candidate}`, "info");
      return payload;
    } catch (error) {
      attempts.push({ candidate, error });
      console.warn(`Asset fetch failed for ${candidate}:`, error);
    }
  }
  const error = new Error(
    attempts.length
      ? `Unable to load ${label} after ${attempts.length} attempts.`
      : `No ${label} candidates provided.`
  );
  error.attempts = attempts;
  throw error;
}

async function fetchGPTInsight(candidates) {
  if (!Array.isArray(candidates) || !candidates.length) {
    throw new Error("No GPT insight path configured.");
  }
  return loadJsonWithFallback(candidates, "GPT insight");
}

function applyUiText(uiText = {}) {
  const setContent = (id, value, useHtml = false) => {
    if (!value) return;
    const el = document.getElementById(id);
    if (!el) return;
    if (useHtml) {
      el.innerHTML = value;
    } else {
      el.textContent = value;
    }
  };
  setContent("hero-eyebrow", uiText.hero_eyebrow);
  setContent("hero-title", uiText.hero_title);
  setContent("hero-lede", uiText.hero_lede);
  setContent("hero-cta", uiText.hero_cta);
  setContent("control-hint", uiText.control_hint, true);
  setContent("footer-note", uiText.footer_note, true);
}

function applyStoryCardWidth(value) {
  const fallback = DEFAULT_VISUAL.story_card_width;
  const width = Number.isFinite(Number(value)) ? Math.max(220, Number(value)) : fallback;
  document.documentElement.style.setProperty("--story-card-width", `${width}px`);
}

function updateConfigStatus(message, tone = "info", sticky = false) {
  if (!CONFIG_STATUS_EL) return;
  CONFIG_STATUS_EL.textContent = message;
  CONFIG_STATUS_EL.classList.toggle("error", tone === "error");
  CONFIG_STATUS_EL.classList.add("active");
  if (configStatusTimer) {
    clearTimeout(configStatusTimer);
    configStatusTimer = null;
  }
  if (tone === "info" && !sticky) {
    configStatusTimer = setTimeout(() => {
      CONFIG_STATUS_EL.classList.remove("active");
    }, 4000);
  }
}

function formatNumber(value) {
  if (value === undefined || value === null) return "—";
  return value.toLocaleString();
}

function createCubeElement(configItem, summary, summaryError, gptUrl, mode) {
  const cube = document.createElement("section");
  cube.className = "cube";
  cube.dataset.cubeId = configItem.id;

  const header = document.createElement("header");
  const title = document.createElement("h2");
  title.textContent = configItem.label;
  const hint = document.createElement("p");
  hint.className = "hint";
  hint.textContent = configItem.description;
  header.appendChild(title);
  header.appendChild(hint);
  cube.appendChild(header);

  const content = document.createElement("div");
  content.className = "cube-content";
  cube.appendChild(content);

  if (!summary && configItem.id !== "gpt") {
    content.innerHTML = `<p class="hint">Summary not available (${summaryError?.message || "missing"})</p>`;
    return cube;
  }

  const builder = builders[configItem.id];
  if (builder) {
    builder(content, summary, mode, gptUrl);
  } else {
    content.innerHTML = "<p class='hint'>This cube is still baking.</p>";
  }

  return cube;
}

async function loadJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${url} (${response.status})`);
  }
  return response.json();
}

async function loadConfig() {
  const attempts = [];
  for (const candidate of CONFIG_URLS) {
    try {
      const result = await loadJson(candidate);
      updateConfigStatus(`Config loaded from ${candidate}`, "info");
      return result;
    } catch (error) {
      console.warn(`Config fetch failed for ${candidate}:`, error);
      attempts.push({ candidate, error });
    }
  }
  const last = attempts[attempts.length - 1];
  const fallbackError = new Error(
    last
      ? `Unable to load config after ${attempts.length} attempts; last try ${last.candidate}`
      : "Unable to load config"
  );
  fallbackError.attempts = attempts;
  if (last) {
    updateConfigStatus(
      `Unable to load config. Last try: ${last.candidate} (${last.error.message})`,
      "error",
      true
    );
  } else {
    updateConfigStatus("Unable to load config.", "error", true);
  }
  throw fallbackError;
}

function averageInterval(summary) {
  const stats = summary?.interval_stats || {};
  if (!stats.count) return 0;
  return Math.round(stats.total_ms / stats.count);
}

function averagePressLength(summary) {
  const lengths = summary?.key_press_lengths || {};
  let total = 0;
  let count = 0;
  Object.values(lengths).forEach((stats) => {
    total += stats.total_ms || 0;
    count += stats.count || 0;
  });
  if (!count) return 0;
  return Math.round(total / count);
}

function computeTypingProfile(summary) {
  const profile = summary?.typing_profile || {};
  const intervalStats = summary?.interval_stats || {};
  const keyLengths = summary?.key_press_lengths || {};
  const avgInterval =
    profile.avg_interval ||
    (intervalStats.count ? intervalStats.total_ms / intervalStats.count : 0);
  const totalPressMs = Object.values(keyLengths).reduce(
    (sum, stats) => sum + (stats.total_ms || 0),
    0
  );
  const totalPressCount = Object.values(keyLengths).reduce(
    (sum, stats) => sum + (stats.count || 0),
    0
  );
  const avgPressLength =
    profile.avg_press_length || (totalPressCount ? totalPressMs / totalPressCount : 0);
  const wpm = profile.wpm || (avgInterval ? 60000 / avgInterval : 0);
  const longPauseRate =
    profile.long_pause_rate ?? ((summary?.long_pauses || 0) / Math.max(1, summary?.total_events || 1));
  return {
    avg_interval: Math.max(0, Math.round(avgInterval)),
    avg_press_length: Math.max(0, Math.round(avgPressLength)),
    wpm: Math.max(0, Math.round(wpm)),
    long_pause_rate: Math.round(longPauseRate * 1000) / 1000,
  };
}

function estimateKeyboardAge(summary) {
  const typing = computeTypingProfile(summary);
  const interval = typing.avg_interval || 500;
  const press = typing.avg_press_length || 200;
  const score =
    (typing.wpm / 120) * 3 + (500 / Math.max(interval, 1)) * 1.5 + (200 / Math.max(press, 1));
  return Number(Math.max(0.5, Math.min(12, score)).toFixed(1));
}

function buildStatGrid(container, stats) {
  const statGrid = document.createElement("div");
  statGrid.className = "stat-grid";
  stats.forEach(([label, value]) => {
    const card = document.createElement("article");
    const title = document.createElement("h3");
    title.textContent = label;
    const valueEl = document.createElement("p");
    valueEl.textContent = value;
    card.appendChild(title);
    card.appendChild(valueEl);
    statGrid.appendChild(card);
  });
  container.appendChild(statGrid);
}

function buildOverviewCube(container, summary) {
  const stats = [
    ["Total presses", formatNumber(summary.total_events)],
    ["Letter keys", formatNumber(summary.letters)],
    ["Action keys", formatNumber(summary.actions)],
    ["Words formed", formatNumber(summary.words)],
    ["Rage bursts", formatNumber(summary.rage_clicks)],
    ["Long pauses", formatNumber(summary.long_pauses)],
    ["Avg interval (ms)", formatNumber(averageInterval(summary))],
    ["Avg press (ms)", formatNumber(averagePressLength(summary))],
  ];
  buildStatGrid(container, stats);
}

function buildKeyChart(canvas, summary) {
  const entries = Object.entries(summary.key_counts || {});
  const sorted = entries
    .sort(([, a], [, b]) => b - a)
    .slice(0, 12);
  const labels = sorted.map(([key]) => key);
  const data = sorted.map(([, value]) => value);
  new Chart(canvas.getContext("2d"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Press count",
          data,
          backgroundColor: "#38bdf8",
          borderRadius: 6,
        },
      ],
    },
    options: {
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (ctx) => formatNumber(ctx.parsed.y) } },
      },
      scales: {
        y: { ticks: { callback: formatNumber }, beginAtZero: true },
      },
    },
  });
}

function buildActivityChart(canvas, summary) {
  const entries = Object.entries(summary.daily_activity || {});
  entries.sort((a, b) => new Date(a[0]) - new Date(b[0]));
  const labels = entries.slice(-30).map(([date]) => date);
  const data = entries.slice(-30).map(([, value]) => value);
  new Chart(canvas.getContext("2d"), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Daily pressure",
          data,
          borderColor: "#f472b6",
          backgroundColor: "rgba(244, 114, 182, 0.25)",
          fill: true,
          tension: 0.3,
        },
      ],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        y: { ticks: { callback: formatNumber }, beginAtZero: true },
      },
    },
  });
}

function buildKeysCube(container, summary) {
  const wrapper = document.createElement("div");
  wrapper.className = "chart-wrapper";
  const keyCanvas = document.createElement("canvas");
  const activityCanvas = document.createElement("canvas");
  wrapper.appendChild(keyCanvas);
  wrapper.appendChild(activityCanvas);
  container.appendChild(wrapper);
  buildKeyChart(keyCanvas, summary);
  buildActivityChart(activityCanvas, summary);
  const hint = document.createElement("p");
  hint.className = "hint";
  hint.textContent =
    "Daily pressure stacks each day’s total key activity so you can spot high-energy spikes, long stretches, or sudden calm days.";
  container.appendChild(hint);
}

function buildWordChart(canvas, summary) {
  const entries = Object.entries(summary.word_counts || {});
  const limit = Math.max(6, CURRENT_VISUAL.word_pie_limit || 6);
  const sorted = entries.sort(([, a], [, b]) => b - a).slice(0, limit);
  const labels = sorted.map(([word]) => word);
  const data = sorted.map(([, value]) => value);
  new Chart(canvas.getContext("2d"), {
    type: "doughnut",
    data: {
      labels,
      datasets: [
        {
          label: "Word share",
          data,
          backgroundColor: sorted.map((_, idx) => WORD_CHART_COLORS[idx % WORD_CHART_COLORS.length]),
          borderWidth: 0,
        },
      ],
    },
    options: {
      cutout: "65%",
      plugins: {
        legend: { position: "bottom", labels: { boxWidth: 12 } },
        tooltip: { callbacks: { label: (ctx) => formatNumber(ctx.parsed) } },
      },
    },
  });
}

function buildWordsCube(container, summary) {
  const chartWrapper = document.createElement("div");
  chartWrapper.className = "chart-wrapper";
  const wordCanvas = document.createElement("canvas");
  chartWrapper.appendChild(wordCanvas);
  container.appendChild(chartWrapper);
  buildWordChart(wordCanvas, summary);
}

function buildTransitionsCube(container, summary) {
  const panel = document.createElement("div");
  panel.className = "list-panel word-transition-panel";
  const title = document.createElement("p");
  title.className = "hint";
  title.textContent = "Most frequent word-to-word journeys.";
  panel.appendChild(title);
  const list = document.createElement("ul");
  const transitions = computeWordTransitions(summary);
  const limit = Math.max(6, CURRENT_VISUAL.transition_limit || 8);
  if (!transitions.length) {
    const empty = document.createElement("li");
    empty.textContent = "Type to form transitions.";
    list.appendChild(empty);
  } else {
    transitions.slice(0, limit).forEach(({ from, to, count }) => {
      const li = document.createElement("li");
      li.innerHTML = `<span>${from} → ${to}</span><span>${formatNumber(count)}</span>`;
      list.appendChild(li);
    });
  }
  panel.appendChild(list);
  container.appendChild(panel);
}

function computeWordTransitions(summary) {
  const merged = [];
  Object.entries(summary.word_pairs || {}).forEach(([from, nexts]) => {
    Object.entries(nexts).forEach(([to, count]) => {
      merged.push({ from, to, count });
    });
  });
  merged.sort((a, b) => b.count - a.count);
  return merged;
}

function computeStoryCards(summary) {
  const cards = [];
  const typing = computeTypingProfile(summary);
  const keyboardAge = estimateKeyboardAge(summary);
  cards.push({
    tag: "Keyboard Age",
    title: `${keyboardAge} years old`,
    body: `Tempo: ${typing.avg_interval}ms pauses, ${typing.avg_press_length}ms holds, ${typing.wpm} WPM energy across ${formatNumber(
      summary.total_events
    )} presses.`,
  });
  const persona = summarizePersona(summary);
  cards.push(persona);
  cards.push({
    tag: "GPT tempo",
    title: `${typing.wpm} WPM rhythm`,
    body: `GPT senses ${Math.round(typing.long_pause_rate * 100)}% long pauses and suggests sweetening the ${typing.avg_press_length}ms holds to keep the profile humming.`,
  });
  const rage = highlight_rage_day(summary);
  cards.push({
    tag: "Standout day",
    title: rage ? `${rage[0]} rage wave` : "Calm streak",
    body: rage
      ? `You recorded ${formatNumber(rage[1])} rage bursts that day.`
      : "No major rage outbursts yet—your typing stays steady.",
  });
  const wordDay = highlight_word_day(summary);
  cards.push({
    tag: "Vocabulary",
    title: wordDay
      ? `${wordDay.date} word feast`
      : "Word smoke signals",
    body: wordDay
      ? `Top word ${wordDay.topWord} (${formatNumber(wordDay.topValue)}) out of ${formatNumber(wordDay.total)} typed segments.`
      : "Keep typing to discover a signature word day.",
  });
  return cards;
}

function summarizePersona(summary) {
  const total = Math.max(1, summary.total_events);
  const letterRatio = summary.letters / total;
  const rageRatio = summary.rage_clicks / total;
  const actionRatio = summary.actions / total;
  const signature = Object.entries(summary.word_counts || {})
    .sort(([, a], [, b]) => b - a)[0]?.[0] || "your own cadence";
  if (rageRatio > 0.02) {
    return {
      tag: "GPT persona",
      title: "Blazing Editor",
      body: `Rapid edits and quick fixes define you. ${signature} keeps reappearing when the tempo spikes.`,
    };
  }
  if (letterRatio > 0.85) {
    return {
      tag: "GPT persona",
      title: "Midnight Wordsmith",
      body: `Letters dominate and long-form flow is your zone. ${signature} is your poetic motif.`,
    };
  }
  if (actionRatio > 0.35) {
    return {
      tag: "GPT persona",
      title: "Navigator",
      body: `Modifiers and navigation keys stay busy while ${signature} steadies your typing path.`,
    };
  }
  return {
    tag: "GPT persona",
    title: "Steady Storyteller",
    body: `${signature} is the motif that keeps your balanced sessions resilient.`,
  };
}

function buildStoryCube(container, summary, mode, gptUrl) {
  const wrapper = document.createElement("div");
  wrapper.className = "story-grid-wrapper";
  const grid = document.createElement("div");
  grid.className = "story-grid";
  wrapper.appendChild(grid);
  container.appendChild(wrapper);
  const renderCards = (cards) => {
    grid.innerHTML = "";
    cards.forEach((card) => {
      const node = createStoryCard(card);
      grid.appendChild(node);
    });
    attachStoryHighlight(grid);
  };

  const fallbackCards = computeStoryCards(summary);
  renderCards(fallbackCards);

  if (!gptUrl) {
    return;
  }

  fetchGPTInsight(gptUrl)
    .then((payload) => {
      const structured = payload?.structured;
      if (structured?.insights?.length) {
        renderCards(structured.insights);
      } else if (payload?.analysis_text) {
        renderCards([
          {
            tag: "AI narrative",
            title: mode === "sample" ? "Sample insight" : "AI narrative",
            body: payload.analysis_text.trim(),
          },
        ]);
      }
    })
    .catch(() => {
      const hint = document.createElement("p");
      hint.className = "hint";
      hint.textContent = "AI insight missing; run the GPT script with an API key.";
      container.appendChild(hint);
    });
}

function createStoryCard(card) {
  const block = document.createElement("article");
  block.className = "story-card";
  const formattedTag = formatStoryTag(card.tag);
  block.innerHTML = `<p class="story-tag">${formattedTag}</p><h3>${card.title}</h3><p>${card.body}</p>`;
  return block;
}

function formatStoryTag(text) {
  if (!text) return "";
  return text
    .replace(/[_-]+/g, " ")
    .split(" ")
    .map((word) => (word ? `${word[0].toUpperCase()}${word.slice(1)}` : ""))
    .filter(Boolean)
    .join(" ");
}

function buildTransitions(summary) {
  const after = summary.key_pairs || {};
  const before = {};
  Object.entries(after).forEach(([from, nexts]) => {
    Object.entries(nexts).forEach(([to, count]) => {
      before[to] = before[to] || {};
      before[to][from] = (before[to][from] || 0) + count;
    });
  });
  return { before, after };
}

function buildLayoutCube(container, summary) {
  const description = document.createElement("p");
  description.className = "hint";
  description.textContent =
    "Reframing of your keyboard, modifiers locked in place, letters flow to keep both hands active.";
  container.appendChild(description);

  const adjacency = computeAdjacency(summary);
  const { before, after } = buildTransitions(summary);
  const layoutNeighborLimit = CURRENT_VISUAL.layout_neighbor_limit || 3;
  const layoutShowFullNeighbors = CURRENT_VISUAL.layout_show_full_adjacency || false;
  const limitNeighbors = (entries) =>
    layoutShowFullNeighbors ? entries : entries.slice(0, layoutNeighborLimit);
  const letterOrder = Array.from(letterSet).sort(
    (a, b) => (adjacency[b] || 0) - (adjacency[a] || 0)
  );

  const letterPositions = [];
  layoutRows.forEach((row, rowIndex) =>
    row.forEach((key, colIndex) => {
      const lower = key.toLowerCase();
      if (letterSet.has(lower)) {
        letterPositions.push({ rowIndex, colIndex, key: key.toLowerCase() });
      }
    })
  );

  const leftPositions = letterPositions.filter((pos) => leftHandKeys.has(pos.key));
  const rightPositions = letterPositions.filter((pos) => !leftHandKeys.has(pos.key));

  const placement = new Map();
  let leftIndex = 0;
  let rightIndex = 0;
  let fillLeft = true;
  letterOrder.forEach((letter) => {
    if ((fillLeft && leftIndex < leftPositions.length) || rightIndex >= rightPositions.length) {
      const pos = leftPositions[leftIndex++] || rightPositions[rightIndex++];
      placement.set(`${pos.rowIndex}-${pos.colIndex}`, letter.toUpperCase());
    } else {
      const pos = rightPositions[rightIndex++] || leftPositions[leftIndex++];
      placement.set(`${pos.rowIndex}-${pos.colIndex}`, letter.toUpperCase());
    }
    fillLeft = !fillLeft;
  });

  const grid = document.createElement("div");
  grid.className = "layout-grid";
  const cellsByKey = new Map();
  const highlighted = new Set();

  function markNeighborCell(keyName, className, strength = 0.3, color) {
    const normalized = keyName.toLowerCase();
    (cellsByKey.get(normalized) || []).forEach((cell) => {
      cell.classList.add(className);
      cell.style.setProperty("--neighbor-strength", Math.min(Math.max(strength, 0), 1));
      if (color) {
        cell.style.setProperty("--neighbor-color", color);
      }
      highlighted.add(cell);
    });
  }

  function resetNeighborHighlights() {
    highlighted.forEach((cell) => {
      cell.classList.remove("layout-key--neighbor-before", "layout-key--neighbor-after");
      cell.style.removeProperty("--neighbor-strength");
      cell.style.removeProperty("--neighbor-color");
    });
    highlighted.clear();
  }

  function colorForNeighbor(isBefore, ratio) {
    const baseHue = isBefore ? 340 : 190;
    const hue = baseHue + (isBefore ? -ratio * 10 : ratio * 12);
    const saturation = 68 + ratio * 15;
    const lightness = 60 - ratio * 12;
    return `hsla(${Math.round(hue)}, ${Math.round(Math.min(Math.max(saturation, 60), 92))}%, ${Math.round(
      Math.max(lightness, 33)
    )}%, 0.85)`;
  }

  layoutRows.forEach((row, rowIndex) => {
    row.forEach((key, colIndex) => {
      const cell = document.createElement("button");
      cell.type = "button";
      cell.className = "layout-key";
      const span = layoutSpans[key] || 1;
      cell.style.gridColumn = `span ${span}`;
      const lower = key.toLowerCase();
      let display = key;
      if (letterSet.has(lower)) {
        display = placement.get(`${rowIndex}-${colIndex}`) || key;
        const orderedBefore = Object.entries(before[display.toLowerCase()] || {}).sort(([, a], [, b]) => b - a);
        const orderedAfter = Object.entries(after[display.toLowerCase()] || {}).sort(([, a], [, b]) => b - a);
        const hintBefore = limitNeighbors(orderedBefore).map(([neighbor]) => neighbor.toUpperCase());
        const hintAfter = limitNeighbors(orderedAfter).map(([neighbor]) => neighbor.toUpperCase());
        cell.dataset.hint = `Before: ${hintBefore.join(", ") || "—"} · After: ${
          hintAfter.join(", ") || "—"
        }`;
      } else {
        cell.dataset.hint = key;
      }
      cell.textContent = display;
      const normalizedKey = display.toLowerCase();
      const normalizedBase = key.toLowerCase();
      [normalizedKey, normalizedBase].forEach((name) => {
        cellsByKey.set(name, (cellsByKey.get(name) || []).concat(cell));
      });

      const normalizedDisplay = display.toLowerCase();
      cell.addEventListener("mouseenter", () => {
        resetNeighborHighlights();
        const prevEntries = Object.entries(before[normalizedDisplay] || {}).sort(([, a], [, b]) => b - a);
        const nextEntries = Object.entries(after[normalizedDisplay] || {}).sort(([, a], [, b]) => b - a);
        const maxPrev = prevEntries[0]?.[1] || 1;
        const maxNext = nextEntries[0]?.[1] || 1;
        const shownPrev = limitNeighbors(prevEntries);
        const shownNext = limitNeighbors(nextEntries);
        shownPrev.forEach(([neighbor, count]) => {
          const ratio = count / Math.max(maxPrev, 1);
          markNeighborCell(
            neighbor,
            "layout-key--neighbor-before",
            ratio,
            colorForNeighbor(true, ratio)
          );
        });
        shownNext.forEach(([neighbor, count]) => {
          const ratio = count / Math.max(maxNext, 1);
          markNeighborCell(
            neighbor,
            "layout-key--neighbor-after",
            ratio,
            colorForNeighbor(false, ratio)
          );
        });
        cell.classList.add("layout-key--active");
      });
      cell.addEventListener("mouseleave", () => {
        resetNeighborHighlights();
        cell.classList.remove("layout-key--active");
      });
      grid.appendChild(cell);
    });
  });

  container.appendChild(grid);
}

function computeAdjacency(summary) {
  const adjacency = {};
  Object.entries(summary.key_pairs || {}).forEach(([from, nexts]) => {
    const lowerFrom = from.toLowerCase();
    if (!letterSet.has(lowerFrom)) return;
    Object.entries(nexts).forEach(([to, count]) => {
      const lowerTo = to.toLowerCase();
      if (!letterSet.has(lowerTo)) return;
      adjacency[lowerFrom] = (adjacency[lowerFrom] || 0) + count;
      adjacency[lowerTo] = (adjacency[lowerTo] || 0) + count;
    });
  });
  return adjacency;
}

function buildHeatmapCube(container, summary) {
  const info = document.createElement("p");
  info.className = "hint";
  info.textContent =
    CURRENT_UI_TEXT.heatmap_flow_hint ||
    "Color tracks frequency, diversity, and the rhythm of your favorite words.";
  container.appendChild(info);

  const bubbleWrapper = document.createElement("div");
  bubbleWrapper.className = "word-bubbles bubble-cluster";
  const entries = Object.entries(summary.word_counts || {}).sort(([, a], [, b]) => b - a);
  const shapes = summary.word_shapes || {};
  const neighbors = summary.word_pairs || {};
  const limit = Math.max(6, CURRENT_VISUAL.heatmap_top_words || 24);
  const maxCount = entries[0]?.[1] || 1;

  const flowPanel = buildHeatmapFlowPanel(shapes);

  let activeBubble = null;
  entries.slice(0, limit).forEach(([word, count]) => {
    const button = document.createElement("button");
    button.className = "word-bubble";
    const diversity = new Set([
      ...Object.keys(neighbors[word] || {}),
      ...Object.entries(neighbors)
        .filter(([, next]) => next[word])
        .map(([from]) => from),
    ]).size;
    const color = colorFromFrequency(count, maxCount, diversity);
    const secondary = `hsl(${Math.max(color.hue - 16, 0)}, ${Math.max(color.saturation - 18, 40)}%, ${Math.max(
      color.lightness - 12,
      28
    )}%)`;
    button.style.background = `radial-gradient(circle at 28% 28%, ${color.value}, ${secondary})`;
    button.style.boxShadow = `0 10px 30px rgba(5, 5, 15, ${0.3 + Math.min(diversity / 25, 0.4)})`;
    button.style.transform = `translate(${(Math.random() - 0.5) * 6}px, ${(Math.random() - 0.5) * 6}px)`;
    const scale = 1 + (count / maxCount) * 0.7;
    button.style.setProperty("--scale", scale.toFixed(2));
    button.textContent = word;
    button.title = `${word}: ${count} hits`;
    button.addEventListener("click", () => {
      flowPanel.update(word, count);
      setActiveBubble(button);
    });
    bubbleWrapper.appendChild(button);
    if (!activeBubble) {
      activeBubble = button;
      button.classList.add("word-bubble--active");
      flowPanel.update(word, count);
    }
  });

  function setActiveBubble(button) {
    if (activeBubble) {
      activeBubble.classList.remove("word-bubble--active");
    }
    activeBubble = button;
    activeBubble.classList.add("word-bubble--active");
  }

  container.appendChild(bubbleWrapper);
  container.appendChild(flowPanel.panel);
}

function colorFromFrequency(count, maxCount, diversity) {
  const freq = Math.min(1, count / maxCount);
  const div = Math.min(1, diversity / 12);
  const hue = 220 - freq * 110;
  const saturation = 60 + div * 25;
  const lightness = 60 - freq * 22 + div * 10;
  return {
    value: `hsl(${Math.round(hue)}, ${Math.round(Math.min(saturation, 90))}%, ${Math.round(
      Math.max(lightness, 32)
    )}%)`,
    hue,
    saturation,
    lightness,
  };
}

function buildHeatmapFlowPanel(shapes) {
  const panel = document.createElement("div");
  panel.className = "word-flow-panel";
  const shapeHolder = document.createElement("div");
  shapeHolder.className = "word-flow-shape";
  panel.appendChild(shapeHolder);
  function updateWordShape(word, count) {
    shapeHolder.innerHTML = "";
    const card = createWordShapeCard(word, count, shapes[word] || []);
    shapeHolder.appendChild(card);
  }

  function update(word, count) {
    if (!word) return;
    updateWordShape(word, count);
  }

  return { panel, update };
}
function createWordShapeCard(word, count, records) {
  const card = document.createElement("article");
  card.className = "word-shape-card";

  const countRow = document.createElement("div");
  countRow.className = "word-shape-count-row";
  const label = document.createElement("span");
  label.className = "word-shape-word-label";
  label.textContent = word;
  const hits = document.createElement("strong");
  hits.textContent = `${formatNumber(count)} hits`;
  countRow.appendChild(label);
  countRow.appendChild(hits);
  card.appendChild(countRow);

  const row = document.createElement("div");
  row.className = "word-shape-row";
  const averages = computeWordLetterAverages(records, word.length);
  const spans = word.split("").map((letter, index) => {
    const span = document.createElement("span");
    const duration = averages[index] || 0;
    span.style.background = wordShapeLetterColor(duration);
    span.textContent = letter.toUpperCase();
    row.appendChild(span);
    return span;
  });
  card.appendChild(row);

  const durationGraph = document.createElement("canvas");
  durationGraph.className = "word-shape-duration-graph";
  durationGraph.height = 60;
  card.appendChild(durationGraph);

  requestAnimationFrame(() => {
    const targetWidth = Math.max(200, word.length * 40);
    row.style.width = `${targetWidth}px`;
    durationGraph.width = targetWidth;
    durationGraph.style.width = `${targetWidth}px`;
    const positions = computeGraphXPositions(word.length, targetWidth, 14);
    drawDurationGraph(durationGraph, averages, positions, word);
    positionLetters(spans, positions);
  });

  return card;
}

function computeWordLetterAverages(records, length) {
  if (!records.length) {
    return Array(length).fill(0);
  }
  const totals = Array(length).fill(0);
  const counts = Array(length).fill(0);
  records.forEach((record) => {
    (record.durations || []).forEach((duration, index) => {
      if (index >= length) return;
      totals[index] += duration || 0;
      counts[index] += 1;
    });
  });
  return totals.map((total, index) => (counts[index] ? total / counts[index] : 0));
}

function drawDurationGraph(canvas, averages, positions, word) {
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const maxDuration = Math.max(...averages, 1);
  const padding = 14;
  ctx.lineWidth = 3;
  const gradient = ctx.createLinearGradient(0, 0, canvas.width, 0);
  gradient.addColorStop(0, "rgba(147, 51, 234, 0.9)");
  gradient.addColorStop(1, "rgba(34, 197, 94, 0.9)");
  ctx.strokeStyle = gradient;
  ctx.beginPath();
  averages.forEach((duration, idx) => {
    const ratio = duration / maxDuration;
    const x = positions[idx];
    const y = canvas.height - padding - ratio * (canvas.height - padding * 2);
    if (idx === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });
  ctx.stroke();
  ctx.globalCompositeOperation = "destination-over";
  ctx.fillStyle = "rgba(15, 23, 42, 0.5)";
  ctx.beginPath();
  averages.forEach((duration, idx) => {
    const ratio = duration / maxDuration;
    const x = positions[idx];
    const y = canvas.height - padding - ratio * (canvas.height - padding * 2);
    ctx.lineTo(x, canvas.height - padding);
    ctx.lineTo(x, y);
  });
  ctx.lineTo(canvas.width - padding, canvas.height - padding);
  ctx.closePath();
  ctx.fill();
  ctx.globalCompositeOperation = "source-over";
  averages.forEach((duration, idx) => {
    const ratio = duration / maxDuration;
    const x = positions[idx];
    const y = canvas.height - padding - ratio * (canvas.height - padding * 2);
    ctx.beginPath();
    ctx.arc(x, y, 4, 0, Math.PI * 2);
    ctx.fillStyle = wordShapeLetterColor(duration);
    ctx.fill();
    ctx.strokeStyle = "#0f172a";
    ctx.stroke();
  });
}

function wordShapeLetterColor(duration) {
  const clamped = Math.min(Math.max(duration || 180, 160), 520);
  const ratio = (clamped - 160) / 360;
  const hue = 240 - ratio * 110;
  const light = 55 - ratio * 18;
  return `hsl(${Math.round(hue)}, 78%, ${Math.max(light, 32)}%)`;
}

function attrElement(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text) el.textContent = text;
  return el;
}

function buildPresserCube(container, summary) {
  const typing = computeTypingProfile(summary);
  const avgPress = Math.max(0, typing.avg_press_length || 0);
  const ratio = Math.min(1, Math.max(0, (avgPress - 120) / 220));
  const percentile = Math.round(ratio * 100);
  const stages = [
    { label: "Feather touch", max: 0.33, color: "hsla(203, 95%, 52%, 0.7)" },
    { label: "Balanced press", max: 0.66, color: "hsla(142, 74%, 45%, 0.7)" },
    { label: "Hammer strike", max: 1, color: "hsla(14, 93%, 54%, 0.7)" },
  ];
  const stage = stages.find((entry) => ratio <= entry.max) || stages[stages.length - 1];

  const gauge = document.createElement("div");
  gauge.className = "presser-gauge";
  const track = document.createElement("div");
  track.className = "presser-track";
  const fill = document.createElement("div");
  fill.className = "presser-fill";
  fill.style.width = `${Math.round(ratio * 100)}%`;
  fill.style.setProperty("--presser-intensity", ratio);
  track.appendChild(fill);
  gauge.appendChild(track);
  container.appendChild(gauge);

  const scale = document.createElement("div");
  scale.className = "presser-scale";
  const gradient = document.createElement("div");
  gradient.className = "presser-scale-track";
  scale.appendChild(gradient);
  const tumbler = document.createElement("div");
  tumbler.className = "presser-scale-indicator";
  tumbler.style.left = `${Math.round(ratio * 100)}%`;
  scale.appendChild(tumbler);
  const scaleLabel = document.createElement("span");
  scaleLabel.className = "presser-scale-label";
  scaleLabel.textContent = `${stage.label} · ${avgPress}ms avg hold`;
  scale.appendChild(scaleLabel);
  container.appendChild(scale);

  const legend = document.createElement("div");
  legend.className = "presser-scale-legend";
  stages.forEach((entry) => {
    const marker = document.createElement("span");
    marker.textContent = entry.label;
    marker.style.color = entry.color;
    legend.appendChild(marker);
  });
  container.appendChild(legend);

  const scoreValue = Math.round(ratio * 100);
  const scoreBadge = document.createElement("div");
  scoreBadge.className = "presser-score";
  scoreBadge.innerHTML = `<span>Pressure score</span><strong>${scoreValue}</strong>`;
  container.appendChild(scoreBadge);

  const percent = document.createElement("p");
  percent.className = "presser-hint";
  percent.textContent = `Avg hold ${avgPress}ms places you at the ${percentile}th percentile of the global presser scale and keeps you in the ${stage.label} comfort zone.`;
  container.appendChild(percent);
}

async function buildGPTCube(container, summary, mode, gptCandidates) {
  const box = document.createElement("div");
  box.className = "gpt-box";
  const status = document.createElement("p");
  status.className = "gpt-status";
  status.textContent = "Loading AI insight…";
  const subtitle = document.createElement("p");
  subtitle.className = "hint ai-cube-subtitle";
  subtitle.textContent = CURRENT_UI_TEXT.ai_cube_subtitle || "Persona & keyboard age";
  const message = document.createElement("div");
  message.textContent =
    "Run `gpt_insights.py` with a configured OpenAI key to refresh the GPT narrative and hear why it chose this persona, keyboard age, and detailed stories.";
  box.appendChild(status);
  box.appendChild(subtitle);
  box.appendChild(message);
  container.appendChild(box);
  try {
    const payload = await fetchGPTInsight(gptCandidates);
    status.textContent = `AI (${mode} mode)`;
    message.textContent = payload.analysis;
  } catch (error) {
    status.textContent = "AI insight missing";
    updateConfigStatus(`AI insight unavailable: ${error.message}`, "error", true);
  }
}

function computeGraphXPositions(wordLength, width, padding = 14) {
  const positions = [];
  if (!wordLength) {
    return positions;
  }
  const available = Math.max(width - padding * 2, 0);
  const step = Math.max(wordLength - 1, 1);
  for (let idx = 0; idx < wordLength; idx += 1) {
    positions.push(padding + (idx * available) / step);
  }
  return positions;
}

function positionLetters(spans, positions) {
  spans.forEach((span, idx) => {
    const x = positions[idx] ?? 0;
    span.style.left = `${x}px`;
  });
}

function highlight_rage_day(summary) {
  const entries = Object.entries(summary?.daily_rage || {});
  if (!entries.length) return null;
  return entries.reduce(
    (best, entry) =>
      !best || entry[1] > best[1] ? entry : best,
    null
  );
}

function highlight_word_day(summary) {
  const entries = Object.entries(summary?.daily_word_counts || {});
  let best = null;
  const summedNeighbors = entries.map(([date, counts]) => {
    const total = Object.values(counts || {}).reduce((sum, value) => sum + value, 0);
    const topEntry = Object.entries(counts || {}).reduce(
      (prev, current) => (current[1] > prev[1] ? current : prev),
      [null, 0]
    );
    return { date, total, topWord: topEntry[0], topValue: topEntry[1] };
  });
  summedNeighbors.forEach((entry) => {
    if (!entry.topWord) return;
    if (!best || entry.total > best.total) {
      best = entry;
    }
  });
  return best;
}


function attachStoryHighlight(grid) {
  if (!grid) return;
  const cards = Array.from(grid.children);
  const updateActive = () => {
    const containerRect = grid.getBoundingClientRect();
    const centerX = containerRect.left + containerRect.width / 2;
    let closest = null;
    let minDistance = Infinity;
    cards.forEach((card) => {
      const rect = card.getBoundingClientRect();
      const cardCenter = rect.left + rect.width / 2;
      const distance = Math.abs(centerX - cardCenter);
      if (distance < minDistance) {
        minDistance = distance;
        closest = card;
      }
    });
    cards.forEach((card) =>
      card.classList.toggle("story-card--active", card === closest)
    );
  };
  if (grid.__storyHighlight__) {
    grid.removeEventListener("scroll", grid.__storyHighlight__);
  }
  grid.__storyHighlight__ = updateActive;
  grid.addEventListener("scroll", updateActive, { passive: true });
  requestAnimationFrame(updateActive);
}

function buildCube(cubeConfig, stack, summary, summaryError, gptUrl, mode) {
  const cube = createCubeElement(cubeConfig, summary, summaryError, gptUrl, mode);
  stack.appendChild(cube);
}

async function init() {
  try {
    const config = await loadConfig();
    CURRENT_UI_TEXT = config.ui_text || {};
    CURRENT_VISUAL = { ...DEFAULT_VISUAL, ...(config.visual || {}) };
    applyStoryCardWidth(CURRENT_VISUAL.story_card_width);
    applyUiText(CURRENT_UI_TEXT);
    const mode = config.mode === "sample" ? "sample" : "real";
    const data = config.data || {};
    const summaryCandidates = buildAssetCandidates(
      data[`${mode}_summary`] || DEFAULT_SUMMARY_PATH
    );
    const gptCandidates = buildAssetCandidates(
      data[`${mode}_gpt`] || DEFAULT_GPT_PATH
    );
    let summary = null;
    let summaryError = null;
    try {
      summary = await loadJsonWithFallback(summaryCandidates, "summary");
    } catch (error) {
      summaryError = error;
      updateConfigStatus(`Summary load failed: ${error.message}`, "error", true);
    }
    const stack = document.getElementById("cube-stack");
    stack.innerHTML = "";
    const cubes = (config.cubes || [])
      .slice()
      .sort((a, b) => (a.order || 0) - (b.order || 0));
    cubes.forEach((cube) => {
      if (cube.enabled === false) return;
      buildCube(cube, stack, summary, summaryError, gptCandidates, mode);
    });
  } catch (error) {
    const stack = document.getElementById("cube-stack");
    let detailHtml = "";
    if (Array.isArray(error.attempts) && error.attempts.length) {
      detailHtml = `<ul class="config-error-list">${error.attempts
        .map(
          (attempt) =>
            `<li>${attempt.candidate}: ${attempt.error.message || attempt.error}</li>`
        )
        .join("")}</ul>`;
    }
    stack.innerHTML = `<p class="hint config-error">Unable to load config: ${error.message}</p>${detailHtml}`;
  }
}

init().catch((error) => {
  console.error("Unable to render dashboard", error);
});
