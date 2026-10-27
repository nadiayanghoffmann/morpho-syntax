#!/usr/bin/env python3
"""
experiment.py
=============
PsychoPy MEG presentation script for the Morpho-Syntax noun stimuli experiment.

Presents trials from data/stimuli_nouns.csv across 12 conditions:
  8 Critical conditions (Comp/List × Phrase/Compound × Space/Nospace)
  2 SSELocalizer conditions (Phrase-Loc, List-Loc)
  2 Lexicality conditions (Word, Pseudoword)

Trigger Channel Mapping:
  • ch160: Phrase trigger line
  • ch161: Spaced trigger line
  • ch162: Composition trigger line
  • ch163: Critical condition baseline line
  • ch164: SSELocalizer line
  • ch165: Lexicality Word line
  • ch166: Lexicality Pseudoword line

Trial Sequence:
  1. Fixation cross (500 ms)
  2. Stimulus 1 + trigger flip (300 ms)
  3. ISI blank screen (300 ms)
  4. Stimulus 2 + response collection (up to 2000 ms)
     Response keys: '1' = Mismatch / Different, '2' = Match / Same
  5. ITI blank screen (jittered 500–800 ms)

Results saved to: logs/<participant_name>/trial_results.csv
"""

import os
import sys
import time
import random
import pandas as pd
import numpy as np

# Hardware trigger sender
from port_open_send import sendTrigger, get_condition_channels, TRIGGER_MAP_12, CONDITION_INFO_12

# PsychoPy imports
try:
    from psychopy import visual, core, event, gui
    PSYCHOPY_AVAILABLE = True
except ImportError:
    PSYCHOPY_AVAILABLE = False
    print("[WARNING] PsychoPy is not installed. To run this experiment GUI, install psychopy.")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(HERE, "data", "stimuli_nouns.csv")
LOGS_DIR  = os.path.join(HERE, "logs")


def load_and_prepare_stimuli(csv_path):
    """Load stimuli_nouns.csv and filter for the 12 experiment conditions."""
    df = pd.read_csv(csv_path)

    # Condition filtering for 12 conditions
    # 8 Critical conditions: TestControl in ['Comp', 'List']
    crit_mask = df['TestControl'].isin(['Comp', 'List'])

    # 2 SSELocalizer conditions: Phrase-Loc and List-Loc
    sse_mask = (df['TestControl'] == 'SSELocalizer') & (df['StrucLevel'].isin(['Phrase-Loc', 'List-Loc']))

    # 2 Lexicality conditions: Word and Pseudoword
    lex_mask = (df['TestControl'] == 'Lexicality') & (df['StrucLevel'].isin(['Word', 'Pseudoword']))

    filtered = df[crit_mask | sse_mask | lex_mask].copy()

    # Assign condition labels and trigger channels
    channels_col = []
    condition_col = []
    mask_col = []

    for _, row in filtered.iterrows():
        tc = str(row['TestControl']).strip()
        sl = str(row['StrucLevel']).strip()
        sp = str(row['Spacing']).strip()
        chans = get_condition_channels(tc, sl, sp)
        cond_name = f"{tc}_{sl}_{sp}"
        channels_col.append(chans)
        condition_col.append(cond_name)
        # compute integer trigger mask
        from port_open_send import channels_to_mask
        mask_col.append(channels_to_mask(chans))

    filtered['Trigger_Channels'] = channels_col
    filtered['Condition']        = condition_col
    filtered['Trigger_Mask']     = mask_col

    return filtered


def run_experiment(debug=False, send_triggers=True, toggle_diode=True, fullscr=False):
    if not PSYCHOPY_AVAILABLE:
        print("[ERROR] Cannot launch experiment without PsychoPy.")
        sys.exit(1)

    # Dialog box
    exp_info = {
        'Participant': 'test_sub',
        'Session': '1',
        'Fullscreen': fullscr,
        'Send Triggers': send_triggers,
        'Diode': toggle_diode,
        'Debug (10 trials)': debug
    }

    dlg = gui.DlgFromDict(dictionary=exp_info, title='Morpho-Syntax MEG Experiment')
    if not dlg.OK:
        core.quit()

    participant = exp_info['Participant'].strip()
    session     = exp_info['Session'].strip()
    fullscr     = exp_info['Fullscreen']
    triggers_on = exp_info['Send Triggers']
    diode_on    = exp_info['Diode']
    debug_mode  = exp_info['Debug (10 trials)']

    # Output directory
    sub_dir = os.path.join(LOGS_DIR, participant)
    os.makedirs(sub_dir, exist_ok=True)
    out_csv = os.path.join(sub_dir, f"{participant}_session_{session}_trials.csv")

    # Load stimuli
    stim_df = load_and_prepare_stimuli(DATA_FILE)
    if debug_mode:
        stim_df = stim_df.sample(n=min(12, len(stim_df))).reset_index(drop=True)
    else:
        # Shuffle stimuli randomly
        stim_df = stim_df.sample(frac=1.0).reset_index(drop=True)

    print(f"\n[Experiment] Loaded {len(stim_df)} trials across 12 conditions.")
    print(f"[Experiment] Participant: {participant} | Triggers: {triggers_on} | Diode: {diode_on}")

    # Window setup
    win = visual.Window(size=[1280, 800], fullscr=fullscr, color=[-1, -1, -1], units='pix')
    win.mouseVisible = False

    # Visual stimuli
    fixation = visual.TextStim(win, text='+', color=[1, 1, 1], height=50)
    stim_text = visual.TextStim(win, text='', color=[1, 1, 1], height=40, font='Courier')
    instruction_text = visual.TextStim(
        win,
        text="Welcome to the experiment!\n\n"
             "You will see two words/phrases in sequence.\n"
             "Judge whether Stimulus 1 and Stimulus 2 MATCH or DIFFER:\n\n"
             "Press '2' for MATCH (Same)\n"
             "Press '1' for MISMATCH (Different)\n\n"
             "Please respond as quickly and accurately as possible.\n\n"
             "Press SPACEBAR to start.",
        color=[1, 1, 1], height=24, wrapWidth=900
    )

    # Photodiode patch (top-left corner for optical sensor)
    diode_square = visual.Rect(
        win, width=80, height=80, pos=[-win.size[0]/2 + 40, win.size[1]/2 - 40],
        fillColor=[1, 1, 1], lineColor=[1, 1, 1], units='pix'
    )

    # Show instructions
    instruction_text.draw()
    win.flip()
    event.waitKeys(keyList=['space'])

    # Brief countdown
    for count in ["3", "2", "1"]:
        fixation.text = count
        fixation.draw()
        win.flip()
        core.wait(0.5)

    trial_clock = core.Clock()
    results = []

    # Main Trial Loop
    for idx, row in stim_df.iterrows():
        s1 = str(row['Stim1']).strip()
        s2 = str(row['Stim2']).strip()
        expected = "2" if row['Match'] == 'Match' else "1"
        chans = row['Trigger_Channels']

        # 1. Fixation (500 ms)
        fixation.text = '+'
        fixation.draw()
        win.flip()
        core.wait(0.500)

        # 2. Stimulus 1 (300 ms) + Trigger Flip
        stim_text.text = s1
        stim_text.draw()
        if diode_on:
            diode_square.draw()

        if triggers_on:
            win.callOnFlip(sendTrigger, channel=chans, duration=0.015)

        t_onset = win.flip()
        core.wait(0.300)

        # 3. ISI blank screen (300 ms)
        win.flip()
        core.wait(0.300)

        # 4. Stimulus 2 + Response collection (up to 2.0 s)
        stim_text.text = s2
        stim_text.draw()
        if diode_on:
            diode_square.draw()

        win.flip()
        trial_clock.reset()

        keys = event.waitKeys(maxWait=2.0, keyList=['1', '2', 'escape'], timeStamped=trial_clock)

        if keys:
            pressed_key, rt = keys[0]
            if pressed_key == 'escape':
                print("\n[Experiment] Aborted by user.")
                break
        else:
            pressed_key, rt = None, None

        is_correct = (pressed_key == expected) if pressed_key else False

        # 5. ITI blank screen (jittered 0.5 – 0.8 s)
        win.flip()
        iti = random.uniform(0.5, 0.8)
        core.wait(iti)

        results.append({
            'trial_num': idx + 1,
            'Item': row['Item'],
            'TestControl': row['TestControl'],
            'StrucLevel': row['StrucLevel'],
            'Spacing': row['Spacing'],
            'Condition': row['Condition'],
            'Trigger_Channels': " ".join(chans),
            'Trigger_Mask': row['Trigger_Mask'],
            'Stim1': s1,
            'Stim2': s2,
            'Match': row['Match'],
            'expected_key': expected,
            'pressed_key': pressed_key,
            'is_correct': is_correct,
            'rt_s': rt,
        })

        if (idx + 1) % 50 == 0:
            # Save intermediate backup
            pd.DataFrame(results).to_csv(out_csv, index=False)
            # Break screen
            break_text = visual.TextStim(
                win, text=f"Take a short break!\nCompleted {idx+1}/{len(stim_df)} trials.\n\nPress SPACE to continue.",
                color=[1, 1, 1], height=24
            )
            break_text.draw()
            win.flip()
            event.waitKeys(keyList=['space'])

    # Final save
    res_df = pd.DataFrame(results)
    res_df.to_csv(out_csv, index=False)
    print(f"\n[Experiment] Results saved to: {out_csv}")

    # End screen
    end_text = visual.TextStim(win, text="Thank you! The experiment is now complete.", color=[1, 1, 1], height=28)
    end_text.draw()
    win.flip()
    core.wait(2.0)
    win.close()


if __name__ == '__main__':
    # Parse CLI arguments if provided
    debug = '--debug' in sys.argv
    run_experiment(debug=debug, fullscr=False)
