#!/usr/bin/env python3
"""Generate a synthetic year of typing summary for the sample data set."""
import json
import math
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(490)

WORDS = [
    "pulse",
    "glimmer",
    "code",
    "verse",
    "flux",
    "orbit",
    "drift",
    "spark",
    "tone",
    "loom",
    "craft",
    "night",
    "frame",
    "echo",
    "shift",
]
LETTERS = list("abcdefghijklmnopqrstuvwxyz")
ACTIONS = ["space", "enter", "tab", "shift", "backspace"]
START = date(2023, 1, 1)
DAYS = 365

word_counts = {word: 0 for word in WORDS}
daily_activity = {}
daily_rage = {}
daily_word_counts = {}

for offset in range(DAYS):
    current = START + timedelta(days=offset)
    label = current.isoformat()
    wave = math.sin(offset / 30)
    activity = int(1200 + 500 * wave + random.randint(-250, 250))
    daily_activity[label] = max(activity, 420)

    rage = random.randint(0, 26)
    if current.weekday() in {4, 5}:
        rage += random.randint(0, 18)
    if current.day == 1:
        rage += 10
    daily_rage[label] = rage

    day_words = {}
    for word in random.sample(WORDS, 4):
        bonus = 30 if word in {"code", "pulse", "craft"} and current.month in {3, 6, 9} else 0
        count = random.randint(60, 220) + bonus
        day_words[word] = count
        word_counts[word] += count
    daily_word_counts[label] = day_words

key_counts = {}
for letter in LETTERS:
    base = random.randint(6500, 21000)
    key_counts[letter] = base
for action in ACTIONS:
    key_counts[action] = random.randint(2400, 8400)

device_meta = {
    "platform": "macOS",
    "machine": "MacBookAir10",
    "processor": "Apple M1",
}

word_pairs = {}
for word in WORDS:
    targets = random.sample([w for w in WORDS if w != word], 4)
    word_pairs[word] = {target: random.randint(120, 460) for target in targets}

key_pairs = {}
all_keys = LETTERS + ACTIONS
for key in all_keys:
    neighbors = random.sample([k for k in all_keys if k != key], 5)
    key_pairs[key] = {neighbor: random.randint(45, 200) for neighbor in neighbors}

word_durations = {}
for word, total in word_counts.items():
    avg = random.randint(310, 570)
    word_durations[word] = {
        "count": total,
        "total_ms": total * avg,
        "fastest_ms": random.randint(160, 260),
        "slowest_ms": random.randint(520, 1020),
    }

key_press_lengths = {}
for key in all_keys:
    count = random.randint(220, 520)
    avg = random.randint(150, 260)
    key_press_lengths[key] = {
        "count": count,
        "total_ms": count * avg,
        "max_ms": random.randint(avg + 60, avg + 220),
        "min_ms": random.randint(max(30, avg - 120), avg),
    }

interval_stats = {
    "count": 125000,
    "total_ms": 125000 * 430,
    "max_ms": 2800,
    "min_ms": 32,
}

word_shapes = {}
for word in WORDS:
    samples = []
    for _ in range(random.randint(4, 7)):
        durations = [random.randint(180, 430) for _ in word]
        intervals = [random.randint(90, 330) for _ in word]
        samples.append({"durations": durations, "intervals": intervals})
    word_shapes[word] = samples

avg_interval = interval_stats["total_ms"] / max(1, interval_stats["count"])
total_press_ms = sum(stats["total_ms"] for stats in key_press_lengths.values())
total_press_count = sum(stats["count"] for stats in key_press_lengths.values())
avg_press_length = total_press_ms / max(1, total_press_count)
typing_profile = {
    "avg_interval": round(avg_interval, 1),
    "avg_press_length": round(avg_press_length, 1),
    "wpm": round(60000 / avg_interval, 1),
    "avg_word_shape_samples": sum(len(v) for v in word_shapes.values()),
    "long_pause_rate": round(random.uniform(0.005, 0.018), 3),
}

summary = {
    "total_events": sum(key_counts.values()),
    "letters": sum(key_counts[k] for k in LETTERS),
    "actions": sum(key_counts[k] for k in ACTIONS),
    "words": sum(word_counts.values()),
    "rage_clicks": sum(daily_rage.values()),
    "long_pauses": random.randint(620, 940),
    "first_event": "2023-01-01T06:30:00+00:00",
    "last_event": "2023-12-31T23:58:00+00:00",
    "key_counts": key_counts,
    "daily_activity": daily_activity,
    "daily_rage": daily_rage,
    "daily_word_counts": daily_word_counts,
    "word_counts": word_counts,
    "word_pairs": word_pairs,
    "key_pairs": key_pairs,
    "key_press_lengths": key_press_lengths,
    "interval_stats": interval_stats,
    "word_durations": word_durations,
    "device_meta": device_meta,
    "word_shapes": word_shapes,
    "typing_profile": typing_profile,
}

output = Path("data/sample_summary.json")
output.parent.mkdir(exist_ok=True)
output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Wrote {output}")
