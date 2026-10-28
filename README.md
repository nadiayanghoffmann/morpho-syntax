# Morpho-Syntax MEG Experiment

This repository holds everything needed to **run** and **analyze the behavior** of an MEG (magnetoencephalography) experiment about how the brain combines two words into one meaning. It compares phrases like *"sells books"*, compound words like *"book seller"* / *"bookseller"*, and two-noun lists that don't combine, like *"pages words"*.

The README has two parts. The **overview** gives the big picture in a few minutes. The **details** walk through each file in the order the code runs, with links to the exact lines, so you can read along in the Python.

---

## Contents

**Overview**
1. [What this experiment is about](#1-what-this-experiment-is-about)
2. [What a participant experiences](#2-what-a-participant-experiences)
3. [How the pieces fit together](#3-how-the-pieces-fit-together)
4. [What's in this repository](#4-whats-in-this-repository)
5. [Quick start](#5-quick-start)

**Details**

6. [The experimental design: 13 conditions](#6-the-experimental-design-13-conditions)
7. [The stimulus file: `data/stimuli_nouns.csv`](#7-the-stimulus-file-datastimuli_nounscsv)
8. [Running a session: `morpho_syntax.py`](#8-running-a-session-morpho_syntaxpy)
9. [Triggers and hardware: `port_open_send.py`](#9-triggers-and-hardware-port_open_sendpy)
10. [Analyzing behavior: `behavioral_analysis.py`](#10-analyzing-behavior-behavioral_analysispy)
11. [Dry runs without the lab: `tools/`](#11-dry-runs-without-the-lab-tools)
12. [Development setup](#12-development-setup)
13. [Known issues and open questions](#13-known-issues-and-open-questions)
14. [Glossary](#14-glossary)

---

# Overview

## 1. What this experiment is about

When you read *"sells books"*, your brain doesn't just recognize two words. It **composes** them into one meaning: an action applied to an object. Language researchers want to know *where* and *when* that composition happens in the brain, and whether it works the same way for:

- **phrases** built by grammar: *"sells books"*, a verb plus its object
- **compound words** built inside a word: *"book seller"*, *"bookseller"*

They also want to know whether **the space between the words** matters. Is *"bookseller"* handled differently from *"book seller"*?

To isolate composition, every "composing" stimulus has a **control** with similar length and shape whose words *don't* combine into one meaning. *"pages words"* is two nouns side by side, a "list". Brain activity that is stronger for *"sells books"* than for *"pages words"* points to composition.

The brain activity is recorded with **MEG**, a scanner that measures the tiny magnetic fields produced by neurons, with millisecond timing. **This repository does not analyze MEG data.** It does three things:

1. **runs the experiment**: shows the words and records the button presses
2. **sends timing markers ("triggers")** to the MEG system, so the brain recording can later be cut up by condition
3. **analyzes the behavior**: accuracy and reaction time of the button presses

## 2. What a participant experiences

The participant lies in the MEG scanner and looks at a screen. They hold a button box in their left hand. On every trial:

```
  +            (blank)      sells books      (blank)      sells books      (blank … press!)      (blank)
fixation                    Stimulus 1                    Stimulus 2       answer window          pause
 200 ms        200 ms        300 ms          500 ms        300 ms          up to 2 s             800 ms
```

They answer one question: **were the two strings the same?**
- **2** (left index finger) = SAME
- **1** (left middle finger) = DIFFERENT

On "different" trials one word changes: *"sellsbooks"* → *"sellsnotes"*. The task is deliberately easy. Its job is to keep people reading attentively. The real interest is the brain's response to **Stimulus 1**.

A session has 5 practice trials with "Correct!/Incorrect" feedback. Then come **650 trials in 5 blocks of 130**, with a break after each block. Each trial takes roughly 2.5–3.5 s, so the main part lasts about 30–40 minutes plus breaks.

## 3. How the pieces fit together

```
                         data/stimuli_nouns.csv   (650 word pairs, 13 conditions)
                                    │
                                    ▼
                           morpho_syntax.py   ◄── PsychoPy (draws the screen, reads keys)
                         ┌──────────┴───────────┐
                         ▼                      ▼
              port_open_send.py           logs/<id>/<id>_morph_syntax_trials.csv
           (trigger code per trial)        (one row per trial: what was shown,
                         │                  what was pressed, how fast)
                         ▼                      │
              Cedrus StimTracker box            ▼
                         │              behavioral_analysis.py
                         ▼                      │
              MEG recording                     ├──► analysis/  (CSV tables)
       (analyzed elsewhere, not here)           └──► figures/   (PNG charts)
```

**For testing on a laptop**, `tools/dry_run.py` swaps in a fake PsychoPy (`tools/fake_psychopy/`) and runs this whole chain with fake participants (see [section 11](#11-dry-runs-without-the-lab-tools)).

## 4. What's in this repository

| Path | What it is |
|---|---|
| [`morpho_syntax.py`](morpho_syntax.py) | **The experiment.** Run it with PsychoPy to test a participant. |
| [`port_open_send.py`](port_open_send.py) | Talks to the trigger hardware. Defines which trigger code each condition gets. |
| [`behavioral_analysis.py`](behavioral_analysis.py) | Reads all participant logs and produces statistics tables and figures. |
| [`data/stimuli_nouns.csv`](data/stimuli_nouns.csv) | The 650 stimulus pairs and their properties. |
| [`tools/dry_run.py`](tools/dry_run.py) | Runs experiment + analysis end-to-end with fake participants, no lab needed. |
| [`tools/fake_psychopy/`](tools/fake_psychopy/psychopy/__init__.py) | A stand-in for PsychoPy used by the dry run. |
| `logs/` | *Created at runtime.* One folder per participant with their trial log. Ignored by git, because it holds participant data. |
| `analysis/`, `figures/` | *Created by the analysis.* Statistics tables and charts. |
| `dry_run/` | *Created by the dry run.* A scratch copy holding fake results. Ignored by git. |
| [`requirements.txt`](requirements.txt) | Python packages for analysis and development. PsychoPy is installed separately (see [section 12](#12-development-setup)). |
| [`pyrefly.toml`](pyrefly.toml), [`.vscode/`](.vscode/settings.json), [`.dir-locals.el`](.dir-locals.el) | Editor and type-checker settings. |

## 5. Quick start

**One-time setup** (laptop, for analysis and dry runs):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Try everything without the lab** (about 3 seconds):

```bash
.venv/bin/python tools/dry_run.py          # 2 fake participants
.venv/bin/python tools/dry_run.py -n 5     # 5 fake participants
# results: dry_run/figures/ and dry_run/analysis/
```

**Run a real session** (on the stimulus computer, with PsychoPy installed):

```bash
python morpho_syntax.py        # or open it in the PsychoPy app and press Run
```

Fill in the dialog. **Use a new Participant ID for each person** (e.g. `sub-01`).

**Analyze** after one or more sessions:

```bash
.venv/bin/python behavioral_analysis.py
# results: analysis/ and figures/
```

> ⚠️ If `logs/` is empty, `behavioral_analysis.py` **invents 20 fake participants** and analyzes them without warning beyond one printed line. Never report results unless you've confirmed they came from real logs (see [10.2](#102-where-the-data-comes-from-and-the-simulation-trap)).

---

# Details

## 6. The experimental design: 13 conditions

### 6.1 The 8 critical conditions: a 2 × 2 × 2 design

Three factors, each with two levels, give 8 combinations:

| Factor | Column in the CSV | Levels | Meaning |
|---|---|---|---|
| **Composition** | `TestControl` | `Comp` / `List` | Do the words combine into one meaning (`Comp`), or are they a list of unrelated nouns (`List`, the control)? |
| **Structure** | `StrucLevel` | `Phrase` / `Compound` | Built like a phrase (verb + noun: *sells books*) or like a compound (noun + noun: *book seller*)? |
| **Spacing** | `Spacing` | `Space` / `Nospace` | Written with a space (*book seller*) or without (*bookseller*)? |

The 8 versions of **item 1** show how each "word set" (`Item` 1–50) appears in every cell:

| # | Composition | Structure | Spacing | Stimulus 1 | Note |
|---|---|---|---|---|---|
| 1 | Comp | Phrase | Space | *sells books* | a real phrase |
| 2 | Comp | Phrase | Nospace | *sellsbooks* | same phrase, space removed |
| 3 | Comp | Compound | Space | *book seller* | a real compound |
| 4 | Comp | Compound | Nospace | *bookseller* | the compound as normally written |
| 5 | List | Phrase | Space | *pages words* | two nouns; length-matched to *sells books* |
| 6 | List | Phrase | Nospace | *pageswords* | |
| 7 | List | Compound | Space | *tabs novels* | two nouns; length-matched to *book seller* |
| 8 | List | Compound | Nospace | *tabsnovels* | |

The `List` rows are the controls. They have the same letter count and look as their `Comp` partners, but the words don't build a meaning together.

### 6.2 The 5 localizer conditions

**Localizers** are short, well-established mini-tasks mixed into the session. They help find the right brain regions in each individual. Their results then guide where to look for the critical effects.

| # | `TestControl` | `StrucLevel` | Example | Purpose (as far as the code shows) |
|---|---|---|---|---|
| 9 | `SSELocalizer` | `Phrase-Loc` | *kittens meow* | A classic two-word phrase vs. list contrast, used to find the brain's word-combining regions. |
| 10 | `SSELocalizer` | `List-Loc` | *kittens dogs* | The list control for #9. |
| 11 | `Lexicality` | `Word` | *cartoon* | Real word. |
| 12 | `Lexicality` | `Pseudoword` | *granic* | Pronounceable non-word. |
| 13 | `Lexicality` | `ConsonantString` | *mdbym* | Unpronounceable letter string. Word / pseudoword / consonant string together find the brain's reading and word-recognition areas. |

For localizers, the `Spacing` column just says `Localizer`. What "SSE" stands for isn't documented in the code; ask Nadia.

### 6.3 Balance

Every condition has **50 trials**, 13 × 50 = **650**. Within each condition, "same" and "different" trials are roughly balanced: 24/26 or 26/24 in the critical conditions, exactly 25/25 in the localizers. For a given word set, if the spaced version is a "same" trial, the unspaced version is usually the "different" one, and vice versa. That way participants can't predict the answer from the condition.

### 6.4 Trigger codes per condition

Each condition is marked in the MEG recording by a combination of **7 trigger lines**, `ch160`–`ch166`. For the critical conditions, the lines map directly onto the factors:

- `ch160` on = **Phrase** (also used for the phrase localizer)
- `ch161` on = **Space**
- `ch162` on = **Comp**
- `ch163` on = **"this is a critical trial"** (always on for conditions 1–8)
- `ch164` = SSE localizer, `ch165` = Word, `ch166` = Pseudoword. Consonant strings use `ch165` + `ch166` together.

Each line is one bit of a number, so a combination is a single number (the **mask**): `ch160`=1, `ch161`=2, `ch162`=4, `ch163`=8, `ch164`=16, `ch165`=32, `ch166`=64.

| # | Condition | Lines on | Mask |
|---|---|---|---|
| 1 | Comp Phrase Space | 160 161 162 163 | 1+2+4+8 = **15** |
| 2 | Comp Phrase Nospace | 160 162 163 | 1+4+8 = **13** |
| 3 | Comp Compound Space | 161 162 163 | 2+4+8 = **14** |
| 4 | Comp Compound Nospace | 162 163 | 4+8 = **12** |
| 5 | List Phrase Space | 160 161 163 | 1+2+8 = **11** |
| 6 | List Phrase Nospace | 160 163 | 1+8 = **9** |
| 7 | List Compound Space | 161 163 | 2+8 = **10** |
| 8 | List Compound Nospace | 163 | **8** |
| 9 | SSE Phrase-Loc | 160 164 | 1+16 = **17** |
| 10 | SSE List-Loc | 164 | **16** |
| 11 | Word | 165 | **32** |
| 12 | Pseudoword | 166 | **64** |
| 13 | Consonant string | 165 166 | 32+64 = **96** |

These are sent at the onset of **Stimulus 1**. At the onset of **Stimulus 2**, a second trigger says whether it's a "same" (`ch163`, mask 8) or "different" (`ch164`, mask 16) trial. Those two codes are the same numbers as conditions 8 and 10 (see [Known issues](#13-known-issues-and-open-questions)).

## 7. The stimulus file: `data/stimuli_nouns.csv`

One row per trial, **650 rows**, 23 columns.

| Column | Example | Meaning |
|---|---|---|
| `Item` | `1` | Word-set number. Critical items are 1–50, SSE localizer 51–100, lexicality 101–150. |
| `TestControl` | `Comp` | `Comp`, `List`, `SSELocalizer` or `Lexicality` (see [section 6](#6-the-experimental-design-13-conditions)). |
| `StrucLevel` | `Phrase` | `Phrase`, `Compound`, `Phrase-Loc`, `List-Loc`, `Word`, `Pseudoword` or `ConsonantString`. |
| `Spacing` | `Space` | `Space`, `Nospace` or `Localizer`. |
| `Stim1` | `sells books` | What's shown first. |
| `S1Length` | `11` | Character count of `Stim1`, spaces included. |
| `Match` | `Match` | `Match` means Stim2 is identical (correct answer **2**). `Mismatch` means one word differs (correct answer **1**). |
| `MismatchCol` | `2` | For mismatches: which word changed (1 = first, 2 = second). Empty for matches. |
| `Stim2` | `sells books` | What's shown second. |
| `S2Length` | `11` | Character count of `Stim2`. |
| `GloveW1W2` | `0.318` | Semantic similarity of the two words (GloVe word vectors; 0 = unrelated, higher = more related). |
| `UnigramFreqW1`, `UnigramFreqW2` | `648139` | How common each word is in a large text corpus. |
| `NgramFreq` | `12229` | How often the two words occur together as a pair. |
| `ClozePrW2` | `10.47` | How predictable word 2 is given word 1. The scale isn't documented here. |
| `S1PTAN`, `S1PTAF`, `S1OTAN`, `S1OTAF`, `S2PTAN`, … | `2.35` | **Not documented here.** They're only filled in for single-word lexicality items, so they're probably phonological (P) and orthographic (O) neighborhood measures (N = count, F = frequency) for Stim1/Stim2. Ask Nadia. |

Notes:
- **The measures exist so conditions can be matched.** A difference between `Comp` and `List` should come from composition, not from one set being made of rarer or more related words.
- **Many measures are 0 in some rows.** The frequency, similarity and predictability measures are filled in for the spaced versions and are 0 for the unspaced versions and the lexicality items.
- **The analysis doesn't use the measures.** Only the experiment's condition columns and `Stim1`/`Stim2`/`Match` matter to the code. The rest is carried into the trial log for later use.

## 8. Running a session: `morpho_syntax.py`

### 8.1 How to launch

PsychoPy **cannot** be installed into this repo's Python 3.14 environment (see [12](#12-development-setup)). Use one of:
- the **PsychoPy standalone app** on the stimulus PC: open `morpho_syntax.py` and press Run
- a separate **Python 3.10** environment with `pip install psychopy`, then `python morpho_syntax.py`

The script must stay next to `port_open_send.py` and `data/`. It finds them relative to its own location ([line 132](morpho_syntax.py#L132)).

### 8.2 The setup dialog

| Field | Default | What it does |
|---|---|---|
| Participant ID | `sub-01` | Names the log folder and file. **Also seeds the random trial order**: the same ID always gives the same order. |
| Start from block | `1` | Set to 2–5 to **resume** after a crash. Practice is skipped. ⚠️ See [8.8](#88-resuming-after-a-crash). |
| Number of blocks | `5` | How many blocks to split the 650 trials into. 5 gives 130 per block. |
| Fullscreen | off | Turn **on** for real sessions. |
| Send triggers? | on | Sends triggers to the StimTracker. With no device connected, nothing happens (safe). |
| Auto respond? | off | Answers randomly by itself, for testing only. |
| Frame rate? | off | Stored but **not used** by this version of the script. Timing always uses `core.wait`. |

### 8.3 Walking through the code

The file reads top to bottom like this:

1. **Docstring** ([lines 1–36](morpho_syntax.py#L1-L36)): the 13 conditions and trigger lines, as in [section 6](#6-the-experimental-design-13-conditions).
2. **Imports** ([lines 38–56](morpho_syntax.py#L38-L56)): PsychoPy is imported inside `try/except`, so the file can at least be opened without it. `sendTrigger` and `channels_to_mask` come from [`port_open_send.py`](port_open_send.py).
3. **`condition_trigger_map`** ([line 66](morpho_syntax.py#L66)): condition name → trigger lines. This is **the map actually used** when sending Stimulus-1 triggers. It duplicates `TRIGGER_MAP_12` in `port_open_send.py`; the dry run checks that the two agree.
4. **`match_trigger_map`** ([line 88](morpho_syntax.py#L88)): `Match` → `ch163`, `Mismatch` → `ch164`, for the Stimulus-2 trigger.
5. **`get_trial_condition_key(row)`** ([line 96](morpho_syntax.py#L96)): turns a CSV row's `TestControl`/`StrucLevel`/`Spacing` into a lowercase key like `comp_phrase_space` or `consonant_string`.
6. **`get_trial_trigger_channel(trial)`** ([line 120](morpho_syntax.py#L120)): looks up a trial's trigger lines. Unknown conditions fall back to `['ch163']`.
7. **Paths and defaults** ([lines 128–142](morpho_syntax.py#L128-L142)): `ROOT` is the script's folder; `logs/` and `data/stimuli_nouns.csv` sit under it. The default flags are overwritten by the dialog.
8. **`load_and_prepare_13_conditions(csv_path)`** ([line 148](morpho_syntax.py#L148)): reads the CSV and adds three columns to every row: `Condition_Key`, `Trigger_Channels` (e.g. `"ch160 ch161 ch162 ch163"`) and `Trigger_Mask` (e.g. `15`).
9. **`run_meg_experiment()`** ([line 183](morpho_syntax.py#L183)) does everything else, in order:
   - **Dialog** ([192–227](morpho_syntax.py#L192-L227)): shows the setup dialog and reads its answers.
   - **Seed** ([229–233](morpho_syntax.py#L229-L233)): turns the participant ID into a number with MD5 and seeds the random generators with it. That makes the trial order repeatable per participant and different between participants.
   - **Texts and keys** ([235–257](morpho_syntax.py#L235-L257)): instruction screens and which keys advance them.
   - **Screen objects** ([259–268](morpho_syntax.py#L259-L268)): a dark-grey window, white text in the Menlo font, a fixation cross and the **photodiode square** ([line 265](morpho_syntax.py#L265)). The square is a white patch in the top-left corner, shown together with each stimulus. A light sensor taped to the screen sees it and records the *true* moment the stimulus appeared, which can lag the software trigger by a frame or two.
   - **Timing constants** ([270–282](morpho_syntax.py#L270-L282)): the durations in [section 2](#2-what-a-participant-experiences).
   - **Helper functions** ([284–380](morpho_syntax.py#L284-L380)): `present_text`, `present_fixation`, `present_prime` (Stimulus 1), `present_target` (Stimulus 2 + response), `after_trial_pause`, `present_feedback`, `save_and_quit`. These are described in [8.4](#84-one-trial-in-code).
   - **Practice** ([382–389](morpho_syntax.py#L382-L389), run at [415–437](morpho_syntax.py#L415-L437)): 5 hardcoded trials with feedback and **no triggers**. Only shown when starting from block 1.
   - **Load and shuffle** ([391–397](morpho_syntax.py#L391-L397)): all 650 rows, shuffled with the participant's seed.
   - **Blocks** ([399–405](morpho_syntax.py#L399-L405)): the shuffled list is cut into `n_blocks` consecutive chunks of `ceil(650 / n_blocks)` trials.
   - **Log file** ([407–410](morpho_syntax.py#L407-L410)): `logs/<id>/<id>_morph_syntax_trials.csv`.
   - **Main loop** ([441–512](morpho_syntax.py#L441-L512)): for each block and each trial it runs fixation → Stimulus 1 → Stimulus 2 + response → pause. It then scores the answer ([461](morpho_syntax.py#L461)), prints a one-line summary to the console and appends a record ([479](morpho_syntax.py#L479)). **After each block** the whole log so far is written to disk ([500–502](morpho_syntax.py#L500-L502)) and a break screen shows the running accuracy.
   - **Goodbye** ([514–522](morpho_syntax.py#L514-L522)): final accuracy, then the window closes.

### 8.4 One trial in code

```
present_fixation()          '+' 200 ms, blank 200 ms
present_prime(trial)        ── flip ──► Stim1 + photodiode on screen
                                         └─ callOnFlip: trialClock.reset, sendTrigger(condition lines, 10 ms)
                            wait 300 ms, blank, wait 500 ms
present_target(trial)       ── flip ──► Stim2 + photodiode on screen
                                         └─ callOnFlip: sendTrigger(ch163 if Match else ch164, 10 ms)
                            wait 300 ms, then blank screen
                            rt0 = now;  wait for key '1'/'2' (max 2.0 s)
                            rt  = key time − rt0      (None if no key)
after_trial_pause()         blank 800 ms
```

- **Trigger timing:** `win.callOnFlip(...)` ([324](morpho_syntax.py#L324), [346](morpho_syntax.py#L346)) means "run this exactly when the screen updates". That ties the trigger to the frame where the text appears.
- **When the reaction-time clock starts:** reaction time is measured from when Stimulus 2 **disappears** ([356](morpho_syntax.py#L356)), not from when it appeared. Add 300 ms to get time from Stimulus-2 onset.
- **Missed answers:** if no key is pressed within 2 s, the response and RT are logged as empty, and the trial counts as incorrect.
- **Escape** at any key prompt quits immediately.

### 8.5 Keys

| Moment | Keys accepted |
|---|---|
| "Please be patient…" setup screen | `s`, `space` (experimenter) |
| Instruction / break screens | `1`, `2`, `left`, `right`, `space` |
| Response window | `1` = different, `2` = same. `space` is also accepted but always counts as wrong. |
| Anywhere | `escape` = quit |

### 8.6 The log file

`logs/<id>/<id>_morph_syntax_trials.csv`, one row per trial:

| Column | Meaning |
|---|---|
| `Participant` | The ID from the dialog. |
| `Trial_num` | 1…650 across the session. |
| `Block` | 1…5. |
| `Item`, `TestControl`, `StrucLevel`, `Spacing` | Copied from the stimulus CSV. |
| `Condition_Key` | e.g. `comp_phrase_space`. |
| `Trigger_Channels`, `Trigger_Mask` | What was sent at Stimulus 1, e.g. `ch160 ch161 ch162 ch163` / `15`. |
| `Stim1`, `Stim2`, `Match` | What was shown, and whether it was a same/different trial. |
| `Expected_Response` | `2` for Match, `1` for Mismatch. |
| `Participant_Resp` | What they pressed (`1`, `2`, `space`, or empty). |
| `Correct` | 1 or 0. |
| `RT_s` | Reaction time in seconds, from Stimulus-2 offset (empty if no answer). |

`logs/` is in `.gitignore`. Participant data shouldn't go into the repository. Back it up some other way.

### 8.7 Console output

Each trial prints one line like:

```
Trial 17/650 [B1] Cond: list_phrase_nospace    | Resp: 1 (exp 1) | Correct: 1 | RT: 512 ms | Acc: 94.1%
```

This lets the experimenter watch accuracy live during the session.

### 8.8 Resuming after a crash

Restart with the **same Participant ID** and set **Start from block** to the block that was interrupted. The same ID gives the same shuffled order, so the remaining blocks continue where they left off, and practice is skipped.

> ⚠️ **Rename the existing log file before resuming.** The script writes to the same file name and starts with an empty list, so the earlier blocks would be **overwritten**. Also, a block is only saved when it *finishes*: quitting mid-block (Escape or crash) loses that block's trials. See [Known issues](#13-known-issues-and-open-questions).

## 9. Triggers and hardware: `port_open_send.py`

### 9.1 What a trigger is

The MEG system records brain signals continuously. To know *which* moment in that stream was "Stimulus 1 of a Comp-Phrase-Space trial", the experiment computer sends a short electrical pulse on some of the MEG's **trigger channels** (160–166) at exactly that moment. Afterwards, the analysis cuts the recording into "epochs" around each pulse and groups them by code.

The pulses go through a **Cedrus StimTracker**, a small box connected to the stimulus computer by USB serial. It turns commands from the computer into pulses on its output lines, which are wired into the MEG.

### 9.2 Walking through the code

- **Docstring** ([lines 1–35](port_open_send.py#L1-L35)): the full condition → channel table.
- **`CHANNEL_BITS`** ([line 46](port_open_send.py#L46)): channel name → bit value (`ch160` = `0x01` … `ch166` = `0x40`).
- **`TRIGGER_MAP_12`** ([line 58](port_open_send.py#L58)): `(TestControl, StrucLevel, Spacing)` → list of channels, for all **13** conditions. The name is historical; `TRIGGER_MAP_13` is an alias ([77](port_open_send.py#L77)).
- **`CONDITION_INFO_12`** ([line 80](port_open_send.py#L80)): numbered conditions 1–13 with display labels. `CONDITION_INFO_13` is an alias.
- **`channels_to_mask(channels)`** ([line 98](port_open_send.py#L98)): adds up the bits. `['ch160', 'ch163']` → `1 | 8` = `9`.
- **`get_condition_channels(tc, sl, sp)`** ([line 111](port_open_send.py#L111)): looks a condition up in `TRIGGER_MAP_12`, with fallbacks for slightly different spellings.
- **Serial setup** ([lines 139–168](port_open_send.py#L139-L168)): runs **as soon as the module is imported**. It looks for the device at `/dev/cu.usbserial-A900a2R9`; set the environment variable `MEG_SERIAL_PORT` to use a different port. Settings are 115200 baud. If the device isn't there, it prints `Trigger simulation/mock mode active` and every later `sendTrigger` call quietly does nothing. That's why the experiment runs safely on a laptop.
- **`sendTrigger(channel, duration)`** ([line 171](port_open_send.py#L171)): builds the 3-byte StimTracker command `b'mh' + bytes([mask])`. It writes it **twice** (an NYU MEG lab convention), waits `duration` seconds (10 ms from the experiment) and then writes `b'mh\x00'` twice, which turns all lines off again. That on/off makes the pulse.

### 9.3 Why there are two trigger maps

`morpho_syntax.py` has its own `condition_trigger_map` (lowercase keys). `port_open_send.py` has `TRIGGER_MAP_12` (tuple keys). They describe the same thing. **If you change one, change the other.** `tools/dry_run.py` checks that every logged trial's channels match `port_open_send.py`.

## 10. Analyzing behavior: `behavioral_analysis.py`

### 10.1 What it measures

- **Accuracy:** the share of trials answered correctly.
- **Reaction time (RT):** how fast, using correct and incorrect trials, keeping only RTs between 0.10 s and 2.00 s ([lines 81–82](behavioral_analysis.py#L81-L82)).
- **Signal-detection categories:** each response falls into one of four boxes.

  | | answered SAME (2) | answered DIFFERENT (1) |
  |---|---|---|
  | **was same** | Hit | Miss |
  | **was different** | False Alarm | Correct Reject |

**Why behavior matters in an MEG study:** it shows that participants paid attention, and it reveals whether some conditions were simply *harder*, which could also change brain activity.

### 10.2 Where the data comes from, and the simulation trap

`load_all_behavioral_data()` ([line 197](behavioral_analysis.py#L197)):

1. Looks for `logs/**/*trials.csv`, then `data/*trials.csv` ([203–205](behavioral_analysis.py#L203-L205)).
2. **If it finds logs**, it reads them all. Key columns are kept as text, so `"2"` doesn't become the number `2`. It renames the experiment's columns to the analysis's names using `LOG_COLUMN_RENAMES` ([line 133](behavioral_analysis.py#L133)): `Participant`→`participant_id`, `Participant_Resp`→`pressed_key`, `RT_s`→`rt_s`, and so on. Then it works out a `Condition` name like `Comp_Phrase_Space` for every trial with `map_row_to_condition()` ([line 150](behavioral_analysis.py#L150)).
3. **If it finds no logs, it makes up data** ([lines 220 onward](behavioral_analysis.py#L220)): 20 fake participants. Their accuracy and RT per condition are **typed into the code** (`cond_effects`, [line 227](behavioral_analysis.py#L227)). Every "effect" in such output is just those typed-in numbers. Its only legitimate use is checking that the code runs, and `tools/dry_run.py` now covers that better.

### 10.3 The steps in `main()`

`main()` is at [line 630](behavioral_analysis.py#L630):

| Step | Code | Output |
|---|---|---|
| Load + classify | `load_all_behavioral_data`, `classify_responses` ([280](behavioral_analysis.py#L280)), `filter_rt` ([301](behavioral_analysis.py#L301)) | Adds `Response_Type` (Hit/Miss/…), `Accurate` (1/0) and three trigger-line flags (`has_ch160_phrase`, `has_ch161_space`, `has_ch162_comp`). |
| Trial table | [651](behavioral_analysis.py#L651) | `analysis/trial_level_data.csv`: every trial, every column. |
| 2×2×2 ANOVA | `plot_2x2x2_factorial` ([350](behavioral_analysis.py#L350)), models at [360](behavioral_analysis.py#L360) and [366](behavioral_analysis.py#L366) | `analysis/anova_accuracy_2x2x2.csv`, `analysis/anova_rt_2x2x2.csv`, `figures/fig01_2x2x2_factorial_accuracy_rt.png` |
| Condition summary | `acc_summary` ([307](behavioral_analysis.py#L307)), `rt_summary` ([314](behavioral_analysis.py#L314)) | `analysis/summary_12_conditions.csv`: mean accuracy, mean RT and standard errors for all 13 conditions (the file name is historical). |
| Response counts | [670–671](behavioral_analysis.py#L670-L671) | `analysis/sdt_response_summary.csv`: Hit/Miss/CR/FA counts per condition. |
| Trigger-line effects | `plot_trigger_channels_breakdown` ([424](behavioral_analysis.py#L424)) | `figures/fig02_trigger_channels_breakdown.png`: accuracy and RT for Phrase vs Compound, Space vs Nospace, Comp vs List (critical trials only). |
| All conditions + pairwise tests | `plot_all_12_conditions_matrix` ([480](behavioral_analysis.py#L480)), `pairwise_fdr` ([328](behavioral_analysis.py#L328)) | `figures/fig03_all_12_conditions_with_sig_matrix.png`: bars for all 13 conditions plus a grid showing which pairs differ significantly. |
| Response-type rates | `plot_response_summary_table` ([595](behavioral_analysis.py#L595)) | `figures/fig04_sdt_summary_table.png`: Hit/Miss/CR/FA rates per condition. |

### 10.4 The statistics in plain terms

- **3-way ANOVA (`fig01`, `anova_*.csv`)** asks, for the 8 critical conditions: does accuracy or RT depend on Composition? On Structure? On Spacing? And do the factors **interact**, e.g. does the space matter more for compounds than for phrases? Each row of the table is one such question. `PR(>F)` is its p-value, and smaller means less likely to be chance.
- **Pairwise Welch t-tests with FDR correction (`fig03`)** compare every pair of the 13 conditions (78 pairs). Running that many tests produces some "significant" results by chance alone. The **FDR (Benjamini–Hochberg)** correction ([343](behavioral_analysis.py#L343)) adjusts the p-values to keep that under control. Stars: `*` p<.05, `**` p<.01, `***` p<.001, `ns` = not significant.
- **Error bars** are standard errors: roughly, how much the mean would wobble if you repeated the experiment.

### 10.5 Statistical caveats

These matter before reporting anything:

- **Trials are treated as independent.** All trials from all participants are pooled, as if 13,000 trials came from 13,000 people. Trials from the same person are correlated, so this makes p-values far too small. The standard approaches are a **repeated-measures ANOVA on per-participant averages**, or a **mixed-effects model** with participant and item as random effects.
- **Accuracy is 0/1 but analyzed with ordinary linear regression.** A logistic (mixed) model fits binary outcomes better.
- **"SDT" here means counts and rates only.** No sensitivity (d′) or bias (c) is computed.
- **RT includes error trials.** Many analyses use correct trials only.

## 11. Dry runs without the lab: `tools/`

### 11.1 What the dry run does

`tools/dry_run.py` ([source](tools/dry_run.py)) proves the whole chain works on any laptop in a few seconds:

1. **Copies** `morpho_syntax.py`, `port_open_send.py`, `behavioral_analysis.py` and `data/` into `dry_run/` ([`prepare_out_dir`](tools/dry_run.py#L42)). The real `logs/`, `analysis/` and `figures/` are never touched. `dry_run/` is wiped at the start of each run, but only if it carries the marker file the script leaves there.
2. **Runs the experiment** once per fake participant (`dryrun-01`, `dryrun-02`, …) in a separate Python process, with the fake PsychoPy on the import path ([`run_participant`](tools/dry_run.py#L54)). The experiment's own **Auto respond** mode supplies random answers.
3. **Checks triggers** ([`check_triggers`](tools/dry_run.py#L67)): every logged trial's `Trigger_Channels` must equal what `port_open_send.py` defines for its condition.
4. **Runs the analysis** on the fake logs ([`run_analysis`](tools/dry_run.py#L83)).

Output:

```
[1/3] Running the experiment with fake PsychoPy …
  dryrun-01: ok — window closed, 1300 triggers sent        ← 650 trials × (Stim1 + Stim2)
[2/3] Checking trigger channels …
  1300 trials in 2 logs, 13 conditions
  trigger channels match port_open_send.py for every trial
[3/3] Running behavioral analysis …
  analysis ok
```

Each participant's full console output is saved as `dry_run/dryrun-NN_console.txt`, and the analysis's as `dry_run/analysis_console.txt`.

**Expect meaningless results:** random answers give about 50% accuracy, about 25% for each response type, and no real effects.

### 11.2 How the fake PsychoPy works

[`tools/fake_psychopy/psychopy/`](tools/fake_psychopy/psychopy/__init__.py) is a folder named `psychopy` with the handful of names the experiment uses. Putting `tools/fake_psychopy` on `PYTHONPATH` makes `import psychopy` find it instead of the real one.

| Module | Real PsychoPy | Fake |
|---|---|---|
| [`gui.py`](tools/fake_psychopy/psychopy/gui.py) | Shows the setup dialog | Fills it in from `DRYRUN_SUBJECT` / `DRYRUN_START_BLOCK` environment variables and turns on Auto respond |
| [`visual.py`](tools/fake_psychopy/psychopy/visual.py) | Draws to the screen | Draws nothing, but **runs `callOnFlip` callbacks on `flip()`**, so `sendTrigger` really executes (in mock mode). It counts triggers. |
| [`core.py`](tools/fake_psychopy/psychopy/core.py) | Real waiting | **Simulated clock:** `wait(0.3)` returns instantly but advances `time.time()` by 0.3 s, so a 30-minute session takes about 1 s and RTs still look realistic |
| [`event.py`](tools/fake_psychopy/psychopy/event.py) | Reads the keyboard | Instantly "presses" the first allowed key |
| `data.py`, `preferences.py`, `hardware/` | — | Empty placeholders so the imports work |

To run a single fake session by hand:

```bash
DRYRUN_SUBJECT=test-01 PYTHONPATH=tools/fake_psychopy .venv/bin/python morpho_syntax.py
# note: this writes into the real logs/ folder; delete logs/test-01 afterwards
```

### 11.3 What a dry run can't tell you

It can't check display timing, fonts and layout, photodiode alignment, whether the StimTracker actually receives triggers, or whether the MEG records them. Those need a pilot session in the lab.

## 12. Development setup

- **Python:** the project's `.venv` uses Python 3.14 with the packages in `requirements.txt`: numpy, pandas, matplotlib, scipy, statsmodels, pyserial, types-pyserial.
- **PsychoPy is not in `requirements.txt`.** The newest PsychoPy on PyPI needs `numpy<1.24`, which doesn't support Python 3.14. Run real sessions with the PsychoPy app or a Python 3.10 environment, and use the dry run on the laptop. The PsychoPy imports in `morpho_syntax.py` carry `# type: ignore` so the type checker doesn't flag them.
- **Type checking:** [pyrefly](https://pyrefly.org) is configured in [`pyrefly.toml`](pyrefly.toml). Run `pyrefly check`. It should report 0 errors; the remaining warnings are style notes.
- **Editors:** [`.vscode/settings.json`](.vscode/settings.json) points VS Code at `.venv`, and [`.dir-locals.el`](.dir-locals.el) does the same for Emacs.
- **Version control:** a git repository also managed with [jj (Jujutsu)](https://jj-vcs.github.io/jj/). The remote is `nadia-remote` (`github.com/nadiayanghoffmann/morpho-syntax`), and the main bookmark/branch is `main`.

## 13. Known issues and open questions

Ordered roughly by how much they could hurt:

1. **Resuming overwrites the log.** After a crash, restarting at block *k* writes blocks *k…5* to the same file, so blocks 1…*k*−1 are lost. **Workaround:** rename the log file before resuming. **Fix:** load the existing log on resume, or write each block to its own file.
2. **Quitting mid-block loses that block.** The log is only saved at the end of each block, and Escape (`save_and_quit`) doesn't save. Up to 130 trials can be lost.
3. **The analysis invents data when there are no logs** ([10.2](#102-where-the-data-comes-from-and-the-simulation-trap)). Easy to mistake for real results.
4. **Stimulus-2 trigger codes clash with Stimulus-1 codes.** "Same" (`ch163` = 8) equals condition 8 (List Compound Nospace), and "different" (`ch164` = 16) equals condition 10 (SSE List-Loc). The MEG analysis can only tell them apart by their order within a trial. All 7 lines are already used for condition codes, so solving this needs a decision from the lab, e.g. other channels, or no Stimulus-2 trigger.
5. **Statistics treat trials as independent** ([10.5](#105-statistical-caveats)). Use per-participant or mixed-effects analyses before drawing conclusions.
6. **Practice uses real stimuli.** *"sells books"*, *"book seller"*, *"kittens meow"* and *"chair"* are also experimental items. Participants will have seen them before the main run.
7. **RT is measured from Stimulus-2 offset**, and the 2-s response window starts then too. Make sure that's intended, and say so in any write-up.
8. **Two copies of the trigger map** (`condition_trigger_map` and `TRIGGER_MAP_12`) must be kept in sync by hand.
9. **The "Frame rate?" option and the `debug` flag do nothing** in this version.
10. **Undocumented details:** what "SSE" stands for, the units of `ClozePrW2`, and the meaning of the `S1PTAN`… columns.
11. **Names say "12" but hold 13** (`TRIGGER_MAP_12`, `summary_12_conditions.csv`, `plot_all_12_conditions_matrix`). That's left over from before the consonant-string condition was added.

## 14. Glossary

| Term | Meaning |
|---|---|
| **MEG** | Magnetoencephalography: records the brain's magnetic fields with millisecond precision. |
| **Composition** | Combining word meanings into a larger meaning (*sells* + *books* → selling of books). |
| **Phrase / compound** | Two-word unit built by grammar (*sells books*) / a word built from words (*bookseller*). |
| **List condition** | Control where words sit side by side without combining (*pages words*). |
| **Localizer** | Short standard task used to find a brain region in each participant. |
| **Pseudoword** | Pronounceable made-up word (*granic*). |
| **Consonant string** | Unpronounceable letter string (*mdbym*). |
| **Item** | A word set that appears across conditions, matched for length. |
| **Trigger** | Short electrical pulse marking an event in the MEG recording. |
| **StimTracker** | Cedrus box that turns computer commands into trigger pulses. |
| **Mask** | A trigger combination written as a single number (sum of the bits). |
| **Photodiode** | Light sensor on the screen that records exactly when a stimulus appeared. |
| **PsychoPy** | Python software for running timed experiments (drawing, keys, timing). |
| **Flip** | Swapping in the newly drawn screen. Stimuli appear on a flip. |
| **ISI / ITI** | Inter-stimulus interval (blank between Stim1 and Stim2) / inter-trial interval (pause between trials). |
| **RT** | Reaction time. |
| **Hit / Miss / False Alarm / Correct Reject** | The four answer outcomes (see [10.1](#101-what-it-measures)). |
| **SDT** | Signal detection theory: the framework behind those four categories. |
| **ANOVA** | Analysis of variance: tests whether means differ across factors and their combinations. |
| **Interaction** | When one factor's effect depends on another's level. |
| **p-value** | How surprising the data would be if there were no real effect. Small = surprising. |
| **FDR / Benjamini–Hochberg** | Correction for running many tests at once. |
| **Welch t-test** | Compares two means without assuming equal variances. |
| **Standard error (SE)** | How precisely a mean is estimated. Shown as error bars. |
| **Mixed-effects model** | Regression that accounts for repeated measurements per participant and item. |
| **Dry run** | Running the full pipeline with fake participants to check the code. |
