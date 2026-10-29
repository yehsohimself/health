# PT

PT is a personal trainer and nutrition coach that runs on your Mac. It asks a few questions, tests where you are, writes your week,
adjusts each day to how you slept and how you feel, and tells you why it changed something. Built for Apple silicon. Open source
under the MIT license.

> **Not medical advice.** PT is a training and nutrition helper, not a doctor or physiotherapist. It asks the standard pre-exercise
> health questions (PAR-Q+) before you start and stops the day when you report warning signs. If you have a medical condition,
> pain that does not go away, or you are unsure, talk to a doctor first.

## What it does

- **Getting to know you:** one question per screen (goals, experience, schedule, equipment, aches, eating habits), then a short
  first-week path with two easy tests that set your starting level.
- **Training:** calisthenics progressions (push-up → … → one-arm), mobility, animal flow, cycling routes, solo jiu-jitsu drills.
  Progression rules are written in code and shown in the app; every change says why and can be undone.
- **Each day:** a 30-second morning check (sleep, energy, aches) turns the plan green, yellow or red; a guided player counts sets,
  rest and reps out loud; after the session it asks how hard it was and whether anything hurt.
- **Nutrition:** calorie and protein targets that correct themselves from your weigh-ins, an eating window, meal logging from a
  photo or a sentence (values from the German BLS 4.0 food table, not invented by a model), a weekly menu and shopping list.
- **Progress:** streak, badges, strength tests, weight trend, readiness, a weekly coach message.

Interface in Turkish.

## Install

Requirements: a Mac with Apple silicon, macOS 14 or newer, [Homebrew](https://brew.sh) and Git.

```bash
git clone https://github.com/yehsohimself/pt.git
cd pt
./kurulum.sh
.venv/bin/python pt_sunucu.py
```

Then open http://127.0.0.1:8771. Later, double-click `PT.command`. The install script adds `ffmpeg` and `uv` with Homebrew, creates
`.venv` and downloads the exercise pictures and coach voice (about 45 MB) from the release.

### Claude

Plans, meal estimates from photos, the weekly menu and coach messages are written by Claude through your own subscription: install
[Claude Code](https://claude.com/claude-code) and sign in once (`claude auth login`). Without it, PT still runs the morning check,
the player, progression rules, streaks and logging, but it cannot write a new plan.

## Where your data goes

Your profile, logs, weights and meal photos are stored in the `pt/` folder on your Mac and never leave it, except the text (and photo)
needed for a writing task, which goes to Claude when you use one. Other outside requests, none of them with an account: cycling routes
(OpenStreetMap search for your start area, BRouter, Open-Meteo weather, map tiles), barcode lookups (Open Food Facts), a monthly
PubMed search for new training research, exercise videos (YouTube, privacy-enhanced mode) and Google Fonts. The server listens on
127.0.0.1 only.

## Credits

Food values: Max Rubner-Institut, BLS 4.0 (CC BY 4.0), see `modeller/bls/LISANS.md`. Routes: BRouter and OpenStreetMap contributors.
Weather: Open-Meteo.

## Development

`pt_sunucu.py` starts a small Flask server; the API is in `pt_site.py`, the rules in `pt.py`, the page is `static/pt.html`.
Tests: `.venv/bin/python -m pytest tests -q`. Code identifiers and comments are in Turkish. PT is cut from a larger workspace where it
runs next to sibling products on the same engine.

---

**Türkçe:** PT, Mac'inizde çalışan kişisel antrenör ve beslenme koçu. Seçenekli sorularla sizi tanır, başlangıç testiyle seviyenizi
ölçer, haftanızı yazar, her sabah uyku ve enerjinize göre günü ayarlar; ilerleme kuralları kodda ve görünür. Tıbbi tavsiye değildir.
Kurulum: yukarıdaki dört komut, sonra tarayıcıda http://127.0.0.1:8771. Plan ve yemek tahmini için Claude Code girişi gerekir.
