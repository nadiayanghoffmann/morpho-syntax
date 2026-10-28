#!/usr/bin/env python3
"""
tools/dry_run.py
================
Dry-run the whole pipeline on a laptop, without PsychoPy or MEG hardware:

  1. Runs morpho_syntax.py for a few fake participants, using tools/fake_psychopy
     and the script's own 'Auto respond?' mode (random answers, so ~50% accuracy).
  2. Checks that every logged trial carries the trigger channels port_open_send.py
     defines for its condition.
  3. Runs behavioral_analysis.py on those logs.

Everything happens in a copy under dry_run/, so the real logs/, analysis/ and
figures/ are never touched. dry_run/ is wiped at the start of each run.

This checks the logic only — not display timing, fonts, the photodiode, or
whether the StimTracker receives triggers. Those need the lab computer.

Usage:
  .venv/bin/python tools/dry_run.py          # 2 participants
  .venv/bin/python tools/dry_run.py -n 5     # 5 participants
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys

import pandas as pd

HERE      = os.path.dirname(os.path.abspath(__file__))
ROOT      = os.path.dirname(HERE)
FAKE_PSY  = os.path.join(HERE, 'fake_psychopy')
OUT_DIR   = os.path.join(ROOT, 'dry_run')
MARKER    = '.dry_run_output'   # only a folder carrying this marker is ever deleted

PIPELINE_FILES = ['morpho_syntax.py', 'port_open_send.py', 'behavioral_analysis.py']


def prepare_out_dir():
    if os.path.exists(OUT_DIR):
        if not os.path.exists(os.path.join(OUT_DIR, MARKER)):
            sys.exit(f"[dry run] {OUT_DIR} exists but wasn't made by this script; not deleting it.")
        shutil.rmtree(OUT_DIR)
    os.makedirs(OUT_DIR)
    open(os.path.join(OUT_DIR, MARKER), 'w').close()
    for name in PIPELINE_FILES:
        shutil.copy2(os.path.join(ROOT, name), OUT_DIR)
    shutil.copytree(os.path.join(ROOT, 'data'), os.path.join(OUT_DIR, 'data'))


def run_participant(subject):
    env = dict(os.environ, PYTHONPATH=FAKE_PSY, DRYRUN_SUBJECT=subject)
    result = subprocess.run([sys.executable, 'morpho_syntax.py'], cwd=OUT_DIR, env=env,
                            capture_output=True, text=True)
    with open(os.path.join(OUT_DIR, f'{subject}_console.txt'), 'w') as f:
        f.write(result.stdout + result.stderr)
    if result.returncode != 0:
        print(result.stdout[-2000:] + result.stderr[-2000:])
        sys.exit(f"[dry run] morpho_syntax.py failed for {subject} (exit {result.returncode})")
    summary = [line for line in result.stdout.splitlines() if line.startswith('[fake psychopy]')]
    print(f"  {subject}: ok — {summary[-1].removeprefix('[fake psychopy] ') if summary else ''}")


def check_triggers():
    sys.path.insert(0, OUT_DIR)
    from port_open_send import get_condition_channels

    logs = glob.glob(os.path.join(OUT_DIR, 'logs', '**', '*trials.csv'), recursive=True)
    df = pd.concat([pd.read_csv(f) for f in logs], ignore_index=True)
    expected = [" ".join(get_condition_channels(r['TestControl'], r['StrucLevel'], r['Spacing']))
                for _, r in df.iterrows()]
    bad = df[df['Trigger_Channels'] != pd.Series(expected, index=df.index)]
    print(f"  {len(df)} trials in {len(logs)} logs, {df['Condition_Key'].nunique()} conditions")
    if not bad.empty:
        print(bad[['Condition_Key', 'Trigger_Channels']].drop_duplicates().to_string())
        sys.exit(f"[dry run] {len(bad)} trials have unexpected trigger channels")
    print("  trigger channels match port_open_send.py for every trial")


def run_analysis():
    result = subprocess.run([sys.executable, 'behavioral_analysis.py'], cwd=OUT_DIR,
                            capture_output=True, text=True)
    with open(os.path.join(OUT_DIR, 'analysis_console.txt'), 'w') as f:
        f.write(result.stdout + result.stderr)
    if result.returncode != 0:
        print(result.stdout[-2000:] + result.stderr[-2000:])
        sys.exit(f"[dry run] behavioral_analysis.py failed (exit {result.returncode})")
    print("  analysis ok")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-n', '--participants', type=int, default=2, help='number of fake participants (default 2)')
    args = parser.parse_args()

    print(f"[dry run] working in {OUT_DIR}")
    prepare_out_dir()

    print("[1/3] Running the experiment with fake PsychoPy …")
    for i in range(1, args.participants + 1):
        run_participant(f"dryrun-{i:02d}")

    print("[2/3] Checking trigger channels …")
    check_triggers()

    print("[3/3] Running behavioral analysis …")
    run_analysis()

    print(f"\n[dry run] done. Look in:\n  {os.path.join(OUT_DIR, 'figures')}\n  {os.path.join(OUT_DIR, 'analysis')}")


if __name__ == '__main__':
    main()
