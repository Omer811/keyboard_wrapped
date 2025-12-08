const SUMMARY_URL = "../data/summary.json";
const SAMPLE_URL = "../data/sample_summary.json";
const params = new URLSearchParams(window.location.search);
const forceSample = params.get("data") === "sample";
const sampleAlert = document.getElementById("sample-alert");

const wordChartColors = ["#fb7185", "#f472b6", "#a855f7", "#22d3ee", "#4ade80", "#fcd34d"];
const dateFormatter = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" });
const summarySections = {
  total: document.getElementById("total-events"),
  letters: document.getElementById("letters"),
  actions: document.getElementById("actions"),
  words: document.getElementById("words"),
  rage: document.getElementById("rage"),
  pauses: document.getElementById("pauses"),
};

let keyChart;
let timelineChart;
let wordChart;

function formatNumber(value) {
  return value.toLocaleString();
}

function buildCards(summary) {
  summarySections.total.textContent = formatNumber(summary.total_events);
  summarySections.letters.textContent = formatNumber(summary.letters);
  summarySections.actions.textContent = formatNumber(summary.actions);
  summarySections.words.textContent = formatNumber(summary.words);
  summarySections.rage.textContent = formatNumber(summary.rage_clicks);
  summarySections.pauses.textContent = formatNumber(summary.long_pauses);
}

function buildKeyChart(summary) {
  const sorted = Object.entries(summary.key_counts)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 12);
  const labels = sorted.map(([key]) => key);
  const data = sorted.map(([, value]) => value);

  if (keyChart) {
    keyChart.data.labels = labels;
    keyChart.data.datasets[0].data = data;
    keyChart.update();
    return;
  }

  const ctx = document.getElementById("key-chart").getContext("2d");
  keyChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Press count",
          data,
          backgroundColor: "#3b82f6",
          borderRadius: 6,
        },
      ],
    },
    options: {
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (context) => formatNumber(context.parsed.y) } },
      },
      scales: {
        y: { ticks: { callback: formatNumber }, beginAtZero: true },
      },
    },
  });
}

function buildTimeline(summary) {
  const entries = Object.entries(summary.daily_activity);
  entries.sort((a, b) => new Date(a[0]) - new Date(b[0]));

  const labels = entries.slice(-30).map(([date]) => date);
  const data = entries.slice(-30).map(([, value]) => value);

  if (timelineChart) {
    timelineChart.data.labels = labels;
    timelineChart.data.datasets[0].data = data;
    timelineChart.update();
    return;
  }

  const ctx = document.getElementById("activity-chart").getContext("2d");
  timelineChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Daily pressure",
          data,
          borderColor: "#ef4444",
          backgroundColor: "rgba(239, 68, 68, 0.2)",
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

async function loadSummary(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to load ${url}`);
  }
  return response.json();
}

function buildWordChart(summary) {
  const entries = Object.entries(summary.word_counts ?? {});
  const sorted = entries.sort(([, a], [, b]) => b - a).slice(0, 6);
  const hasData = sorted.length > 0;
  const labels = hasData ? sorted.map(([word]) => word) : ["no words yet"];
  const data = hasData ? sorted.map(([, value]) => value) : [1];
  const backgroundColor = hasData
    ? wordChartColors.slice(0, labels.length)
    : ["#d1d5db"];

  if (wordChart) {
    wordChart.data.labels = labels;
    wordChart.data.datasets[0].data = data;
    wordChart.data.datasets[0].backgroundColor = backgroundColor;
    wordChart.update();
    return;
  }

  const ctx = document.getElementById("word-chart").getContext("2d");
  wordChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [
        {
          label: "Word share",
          data,
          backgroundColor,
          borderWidth: 0,
        },
      ],
    },
    options: {
      cutout: "65%",
      plugins: {
        legend: { position: "bottom", labels: { boxWidth: 12 } },
        tooltip: { callbacks: { label: (context) => formatNumber(context.parsed) } },
      },
    },
  });
}

function buildWordFlow(summary) {
  const pairs = summary.word_pairs || {};
  const merged = [];
  Object.entries(pairs).forEach(([from, nexts]) => {
    Object.entries(nexts).forEach(([to, count]) => {
      merged.push({ from, to, count });
    });
  });
  merged.sort((a, b) => b.count - a.count);
  const list = document.getElementById("bigram-list");
  list.innerHTML = "";

  if (!merged.length) {
    list.innerHTML =
      '<li class="muted">No word transitions yet. Keep typing for a richer story.</li>';
    return;
  }

  merged.slice(0, 8).forEach(({ from, to, count }) => {
    const item = document.createElement("li");
    item.innerHTML = `
      <span class="chain">${from} → ${to}</span>
      <span class="value">${formatNumber(count)}</span>
    `;
    list.appendChild(item);
  });
}

async function init() {
  let summary;
  if (forceSample) {
    summary = await loadSummary(SAMPLE_URL);
    sampleAlert.hidden = false;
  } else {
    try {
      summary = await loadSummary(SUMMARY_URL);
    } catch (primaryError) {
      console.warn("Primary summary missing, falling back to the sample data.", primaryError);
      summary = await loadSummary(SAMPLE_URL);
      sampleAlert.hidden = false;
    }
  }

  buildCards(summary);
  buildKeyChart(summary);
  buildTimeline(summary);
  buildWordChart(summary);
  buildWordFlow(summary);
  buildStoryFeed(summary);
}

function formatDateLabel(label) {
  if (!label) return "Unknown day";
  const parsed = new Date(label);
  if (Number.isNaN(parsed.getTime())) {
    return label;
  }
  return dateFormatter.format(parsed);
}

function computeKeyboardAge(summary) {
  const rawYears = summary.total_events / 125000;
  const fitted = Math.min(12, Math.max(0.5, rawYears));
  return Number(fitted.toFixed(1));
}

function derivePersona(summary) {
  const totalEvents = Math.max(summary.total_events, 1);
  const letterRatio = summary.letters / totalEvents;
  const rageRatio = summary.rage_clicks / totalEvents;
  const actionRatio = summary.actions / totalEvents;
  const sortedWords = Object.entries(summary.word_counts || {}).sort(([, a], [, b]) => b - a);
  const signature = sortedWords[0]?.[0] ?? "your own pace";
  if (rageRatio > 0.02) {
    return {
      badge: "GPT persona",
      title: "Blazing Editor",
      body: `Rapid edits and frustration bursts make ${signature} your battle cry. This keyboard persona thrives on powerful, punchy sessions.`,
    };
  }
  if (letterRatio > 0.85) {
    return {
      badge: "GPT persona",
      title: "Midnight Wordsmith",
      body: `Letters rule the day and the night, leaning into long-form flow. ${signature} is your signature word for a poetic rhythm.`,
    };
  }
  if (actionRatio > 0.35) {
    return {
      badge: "GPT persona",
      title: "Navigator",
      body: `Modifiers and arrows keep you precise. ${signature} is the word that anchors your tactical typing story.`,
    };
  }
  return {
    badge: "GPT persona",
    title: "Steady Storyteller",
    body: `Balanced tweaks with thoughtful pacing. ${signature} pops up so often it feels like your personal motif.`,
  };
}

function highlightRageDay(summary) {
  const entries = Object.entries(summary.daily_rage || {});
  if (!entries.length) {
    return null;
  }
  return entries.reduce(
    (best, [date, count]) => (count > best.rank ? { date, count, rank: count } : best),
    { date: null, count: 0, rank: -1 }
  );
}

function highlightWordDay(summary) {
  const entries = Object.entries(summary.daily_word_counts || {});
  let best = { date: null, total: 0, topWord: null, topValue: 0 };
  entries.forEach(([date, counts]) => {
    const total = Object.values(counts).reduce((sum, val) => sum + val, 0);
    const [topWord, topValue] = Object.entries(counts).reduce(
      (bestWord, [word, count]) => (count > bestWord[1] ? [word, count] : bestWord),
      [null, 0]
    );
    if (total > best.total) {
      best = { date, total, topWord, topValue };
    }
  });
  return best.date ? best : null;
}

function createStoryCard({ tag, title, body, accent }) {
  const card = document.createElement("article");
  card.className = "story-card";
  if (accent) {
    card.style.setProperty("--accent", accent);
  }
  card.innerHTML = `
    <p class="story-tag">${tag}</p>
    <h3>${title}</h3>
    <p>${body}</p>
  `;
  return card;
}

function buildStoryFeed(summary) {
  const feed = document.getElementById("story-feed");
  if (!feed) {
    return;
  }
  feed.innerHTML = "";

  const activeDays = Object.values(summary.daily_activity || {}).filter(Boolean).length || 1;
  const avgPerDay = Math.round(summary.total_events / activeDays);
  const keyboardAge = computeKeyboardAge(summary);
  const ageCard = createStoryCard({
    tag: "Keyboard Age",
    title: `${keyboardAge} years old`,
    body: `You're about ${keyboardAge} keyboard years in—${formatNumber(summary.total_events)} presses logged this year (${formatNumber(
      avgPerDay
    )} per active day).`,
    accent: "#a855f7",
  });

  const persona = derivePersona(summary);
  const personaCard = createStoryCard({
    tag: persona.badge,
    title: persona.title,
    body: persona.body,
    accent: "#22d3ee",
  });

  const rageHighlight = highlightRageDay(summary);
  const rageCard = createStoryCard({
    tag: "Standout day",
    title: rageHighlight ? `${formatDateLabel(rageHighlight.date)} rage wave` : "Calm streak",
    body: rageHighlight
      ? `You registered ${formatNumber(rageHighlight.count)} rage bursts on that day. People who type like you tend to battle bugs head-on.`
      : "No huge rage surges yet—your typing stays balanced.",
    accent: "#fb7185",
  });

  const wordHighlight = highlightWordDay(summary);
  const wordCard = createStoryCard({
    tag: "Vocabulary",
    title: wordHighlight
      ? `${formatDateLabel(wordHighlight.date)} word feast`
      : "Word smoke signals",
    body: wordHighlight
      ? `That day your top word was “${wordHighlight.topWord}” (${formatNumber(wordHighlight.topValue)} hits) among ${formatNumber(
          wordHighlight.total
        )} typed segments.`
      : "Keep typing to discover a standout word day.",
    accent: "#fcd34d",
  });

  feed.append(ageCard, personaCard, rageCard, wordCard);
}
init().catch((error) => {
  console.error("Unable to render dashboard", error);
});
