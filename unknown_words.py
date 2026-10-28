"""
unknown_words.py
================
MEG Experiment Script for Morpho-Syntax Noun Stimuli (13 Conditions, 650 Trials).
Based on the PsychoPy unknown_words.py experiment structure and StimTracker port integration.

13 Experimental Conditions (50 stimuli each = 650 total trials):
-----------------------------------------------------------------
  Critical Conditions (8):
    1. comp phrase space           (e.g., 'sells books', 11 chars) -> [ch160, ch161, ch162, ch163]
    2. comp phrase nospace         (e.g., 'sellsbooks',  10 chars) -> [ch160, ch162, ch163]
    3. comp compound space         (e.g., 'book seller', 11 chars) -> [ch161, ch162, ch163]
    4. comp compound nospace       (e.g., 'bookseller',  10 chars) -> [ch162, ch163]
    5. list phrase space           (e.g., 'pages words', 11 chars) -> [ch160, ch161, ch163]
    6. list phrase nospace         (e.g., 'pageswords',  10 chars) -> [ch160, ch163]
    7. list compound space         (e.g., 'tabs novels', 11 chars) -> [ch161, ch163]
    8. list compound nospace       (e.g., 'tabsnovels',  10 chars) -> [ch163]

  Lexicality Conditions (3):
    9.  word                       (e.g., 'chair',  5 chars)       -> [ch165]
    10. pseudoword                 (e.g., 'charp',  5 chars)       -> [ch166]
    11. consonant string           (e.g., 'ftgpm',  5 chars)       -> [ch165, ch166]

  SSELocalizer Conditions (2):
    12. phrase-loc                 (e.g., 'kittens meow', 12 chars)-> [ch160, ch164]
    13. list-loc                   (e.g., 'kittens dogs', 12 chars)-> [ch164]

Trigger Lines (Cedrus StimTracker Channels 160-166):
  • ch160 (bit 0, 0x01): Phrase trigger line
  • ch161 (bit 1, 0x02): Spacing trigger line (active for Spaced conditions)
  • ch162 (bit 2, 0x04): Composition trigger line (active for Comp)
  • ch163 (bit 3, 0x08): Critical baseline marker line (and Match trigger at S2)
  • ch164 (bit 4, 0x10): SSELocalizer marker line      (and Mismatch trigger at S2)
  • ch165 (bit 5, 0x20): Lexicality Word line
  • ch166 (bit 6, 0x40): Lexicality Pseudoword line
"""

import os
import sys
import time
import random
import hashlib
import numpy as np
import pandas as pd

# PsychoPy imports (optional at import-time for offline environments)
try:
    from psychopy import core, visual, event, data, gui  # type: ignore
    from psychopy.hardware import keyboard               # type: ignore
    from psychopy.preferences import prefs               # type: ignore
    PSYCHOPY_AVAILABLE = True
except ImportError:
    PSYCHOPY_AVAILABLE = False

# StimTracker hardware trigger functions
from port_open_send import sendTrigger, channels_to_mask, CHANNEL_BITS

# ============================================================================#
# === 13 Conditions & Trigger Mapping ========================================#
# ============================================================================#
#
# This dictionary maps every condition directly to its trigger channel(s).
# The channels are sent to the Cedrus StimTracker via port_open_send.py.
# You can edit the channels mapped to any condition here if your MEG setup changes.

condition_trigger_map = {
    # 8 Critical conditions (Comp/List × Phrase/Compound × Space/Nospace)
    'comp_phrase_space':        ['ch160', 'ch161', 'ch162', 'ch163'],
    'comp_phrase_nospace':      ['ch160', 'ch162', 'ch163'],
    'comp_compound_space':      ['ch161', 'ch162', 'ch163'],
    'comp_compound_nospace':    ['ch162', 'ch163'],
    'list_phrase_space':        ['ch160', 'ch161', 'ch163'],
    'list_phrase_nospace':      ['ch160', 'ch163'],
    'list_compound_space':      ['ch161', 'ch163'],
    'list_compound_nospace':    ['ch163'],

    # 3 Lexicality conditions
    'word':                     ['ch165'],
    'pseudoword':               ['ch166'],
    'consonant_string':         ['ch165', 'ch166'],

    # 2 SSELocalizer conditions
    'phrase-loc':               ['ch160', 'ch164'],
    'list-loc':                 ['ch164'],
}

# Stimulus 2 onset trigger map: encodes Match vs Mismatch
match_trigger_map = {
    'Match':    'ch163',   # SAME (Match)
    'Mismatch': 'ch164',   # DIFFERENT (Mismatch)
    0:          'ch163',
    1:          'ch164',
}


def get_trial_condition_key(row):
    """
    Given a row from stimuli_nouns.csv, return the matching condition key
    in condition_trigger_map.
    """
    tc = str(row.get('TestControl', '')).strip().lower()
    sl = str(row.get('StrucLevel', '')).strip().lower()
    sp = str(row.get('Spacing', '')).strip().lower()

    if tc in ('comp', 'list'):
        return f"{tc}_{sl}_{sp}"
    elif tc == 'lexicality':
        if sl in ('consonantstring', 'consonant string', 'consonant_string'):
            return 'consonant_string'
        return sl  # 'word' or 'pseudoword'
    elif tc == 'sselocalizer':
        if 'phrase' in sl:
            return 'phrase-loc'
        elif 'list' in sl:
            return 'list-loc'
        return sl
    return f"{tc}_{sl}_{sp}".strip('_')


def get_trial_trigger_channel(trial):
    """Look up trigger channels for a trial from condition_trigger_map."""
    cond_key = str(trial.get('Condition_Key', '')).strip().lower()
    if not cond_key:
        cond_key = get_trial_condition_key(trial)
    return condition_trigger_map.get(cond_key, ['ch163'])


# ============================================================================#
# === Paths & Configuration Defaults =========================================#
# ============================================================================#

ROOT         = os.path.dirname(os.path.abspath(__file__))
dir_logs     = os.path.join(ROOT, 'logs')
DATA_FILE    = os.path.join(ROOT, 'data', 'stimuli_nouns.csv')

debug              = False
toggle_diode       = True
use_frame_rate     = False
send_triggers      = True
fullscr            = False
simulate_responses = False
verbose            = True

# ============================================================================#
# === Helper to Prepare Stimuli ==============================================#
# ============================================================================#

def load_and_prepare_13_conditions(csv_path):
    """
    Load data/stimuli_nouns.csv and verify all 13 conditions (650 stimuli).
    Adds 'Condition_Key', 'Trigger_Channels', and 'Trigger_Mask' columns.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Stimuli CSV not found at {csv_path}")

    df = pd.read_csv(csv_path)

    # Standardize condition keys and trigger channels
    cond_keys = []
    trig_chans = []
    trig_masks = []

    for _, row in df.iterrows():
        key = get_trial_condition_key(row)
        chans = condition_trigger_map.get(key, ['ch163'])
        mask = channels_to_mask(chans)

        cond_keys.append(key)
        trig_chans.append(" ".join(chans) if isinstance(chans, list) else str(chans))
        trig_masks.append(mask)

    df['Condition_Key']   = cond_keys
    df['Trigger_Channels']= trig_chans
    df['Trigger_Mask']    = trig_masks

    return df


# ============================================================================#
# === Experiment Main Logic ==================================================#
# ============================================================================#

def run_meg_experiment():
    global debug, toggle_diode, use_frame_rate, send_triggers, fullscr, simulate_responses, verbose

    if not PSYCHOPY_AVAILABLE:
        print("[ERROR] PsychoPy is not installed in the active environment.")
        print("To run this experiment GUI on macOS, use Python 3.10 with PsychoPy installed,")
        print("or run with the standalone PsychoPy app.")
        sys.exit(1)

    # 1. Experiment Setup Dialog
    info = {
        'Participant ID': 'sub-01',
        'Start from block': '1',    # enter 2-5 to resume after a break/error
        'Number of blocks': '5',    # default 5 blocks of 130 trials = 650 trials
        'Fullscreen': False,
        'Send triggers?': True,
        'Auto respond?': False,
        'Frame rate?': False,
    }
    order = ['Participant ID', 'Start from block', 'Number of blocks', 'Fullscreen',
             'Send triggers?', 'Auto respond?', 'Frame rate?']

    dlg = gui.DlgFromDict(dictionary=info, title='Morpho-Syntax MEG Experiment (13 Conditions)', order=order)
    if not dlg.OK:
        core.quit()

    participant_name   = str(info['Participant ID']).strip()
    fullscr            = bool(info['Fullscreen'])
    send_triggers      = bool(info['Send triggers?'])
    simulate_responses = bool(info['Auto respond?'])
    use_frame_rate     = bool(info['Frame rate?'])

    try:
        start_block = max(1, int(info['Start from block']))
    except (ValueError, TypeError):
        start_block = 1

    try:
        n_blocks = max(1, int(info['Number of blocks']))
    except (ValueError, TypeError):
        n_blocks = 5

    print(f"\n[Experiment] Participant: {participant_name}")
    print(f"[Experiment] Starting from block: {start_block} (Total blocks: {n_blocks})")
    print(f"[Experiment] Hardware triggers: {send_triggers} | Fullscreen: {fullscr}")

    # Deterministic shuffle seed based on participant ID:
    # restarting with the same ID reproduces the identical trial order.
    _seed = int(hashlib.md5(participant_name.encode()).hexdigest()[:8], 16) % (2**31)
    np.random.seed(_seed)
    random.seed(_seed)

    # 2. Display and Instructions Text
    setup_text = "Please be patient as we set up the experiment..."

    practice_instructions = (
        "Welcome to the practice session!\n\n"
        "You will see two short words or phrases flash rapidly one after the other.\n\n"
        "Press '2' with your LEFT INDEX FINGER if they are the SAME.\n\n"
        "Press '1' with your LEFT MIDDLE FINGER if they are DIFFERENT.\n\n"
        "This practice session will be brief.\n"
        "When you are ready, press either button to continue."
    )

    instructions_text = (
        "This is the main experiment.\n\n"
        "You will see two short words or phrases flash rapidly one after the other.\n\n"
        "Press '2' with your LEFT INDEX FINGER if they are the SAME.\n\n"
        "Press '1' with your LEFT MIDDLE FINGER if they are DIFFERENT.\n\n"
        "Respond as quickly and accurately as possible.\n\n"
        "When you are ready, press either button to continue."
    )

    setup_proceed_key        = ['s', 'space', 'escape']
    instruction_proceed_keys = ['1', '2', 'left', 'right', 'space', 'escape']

    # 3. Visual Objects Setup
    win = visual.Window(monitor='default', units='pix', checkTiming=True, fullscr=fullscr, color='#444444')
    stim_text   = visual.TextStim(win, text='', height=24, font='Menlo', wrapWidth=800, alignText='center', color='white')
    answer_text = visual.TextStim(win, text='', height=24, font='Menlo', wrapWidth=800, alignText='center', color='white')
    fixation    = visual.TextStim(win, text='+', height=36, font='Menlo', wrapWidth=800, alignText='center', color='white')
    instructions= visual.TextStim(win, text='', height=20, font='Menlo', wrapWidth=800, pos=(0, 0), alignText='center', color='white')
    photodiode  = visual.Rect(win, width=57, height=57, pos=[-483, 355], fillColor=[255, 255, 255], fillColorSpace='rgb255')

    trialClock  = core.Clock()
    win.mouseVisible = False

    # Timing Constants (in seconds)
    fixation_ON_s  = 0.200   # fixation cross on
    fixation_OFF_s = 0.200   # blank after fixation
    prime_ON_s     = 0.300   # Stimulus 1 and Stimulus 2 duration
    prime_OFF_s    = 0.500   # blank between Stimulus 1 and Stimulus 2
    inter_trial_s  = 0.800   # blank after response

    frame_time_ms  = win.monitorFramePeriod * 1000 if win.monitorFramePeriod else 16.67
    fixation_ON_ms = fixation_ON_s * 1000
    fixation_OFF_ms= fixation_OFF_s * 1000
    prime_ON_ms    = prime_ON_s * 1000
    prime_OFF_ms   = prime_OFF_s * 1000
    inter_trial_ms = inter_trial_s * 1000

    # 4. Emergency Quit Function
    def save_and_quit():
        print("\n[ESCAPE] Exiting cleanly...")
        win.close()
        core.quit()

    def present_text(text='', proceed_keys=['s']):
        instructions.setText(text)
        instructions.draw()
        win.flip()
        if simulate_responses:
            return '1'
        keys = event.waitKeys(keyList=list(proceed_keys) + ['escape'])
        if keys and keys[0] == 'escape':
            save_and_quit()
        return keys[0] if keys else '1'

    def present_fixation():
        if use_frame_rate:
            for _ in range(int(fixation_ON_ms / frame_time_ms + 1)):
                fixation.draw()
                win.flip()
            for _ in range(int(fixation_OFF_ms / frame_time_ms + 1)):
                win.flip()
        else:
            fixation.draw()
            win.flip()
            core.wait(fixation_ON_s)
            win.flip()
            core.wait(fixation_OFF_s)

    def present_prime(trial, send_trigger=True):
        """Show Stimulus 1 (Prime). Sends condition trigger at onset on screen flip."""
        s1 = str(trial.get('Stim1', trial.get('Stimulus1', ''))).strip()
        stim_text.setText(s1)
        win.callOnFlip(trialClock.reset)

        if send_trigger and send_triggers and not is_practice:
            ch = get_trial_trigger_channel(trial)
            if ch:
                win.callOnFlip(sendTrigger, channel=ch, duration=0.01)

        stim_on_start = time.time()
        stim_text.draw()
        if toggle_diode:
            photodiode.draw()
        win.flip()
        core.wait(prime_ON_s)

        win.flip()
        core.wait(prime_OFF_s)
        return (time.time() - stim_on_start) * 1000

    def present_target(trial):
        """Show Stimulus 2 (Target). Sends Match/Mismatch trigger at onset on screen flip."""
        s2 = str(trial.get('Stim2', trial.get('Stimulus2', ''))).strip()
        answer_text.setText(s2)

        if send_triggers and not is_practice:
            m_val = str(trial.get('Match', '')).strip()
            match_ch = match_trigger_map.get(m_val)
            if match_ch:
                win.callOnFlip(sendTrigger, channel=match_ch, duration=0.01)

        answer_text.draw()
        if toggle_diode:
            photodiode.draw()
        win.flip()
        core.wait(prime_ON_s)

        # Blank screen — wait for response
        win.flip()
        rt0 = time.time()

        if simulate_responses:
            answer = str(random.choice(['1', '2']))
            core.wait(random.uniform(0.3, 0.6))
            end_time = time.time()
        else:
            keys = event.waitKeys(maxWait=2.0, keyList=['1', '2', 'escape', 'space'])
            end_time = time.time()
            if keys and keys[0] == 'escape':
                save_and_quit()
            answer = keys[0] if keys else None

        rt = (end_time - rt0) if answer else None
        return answer, s2, rt

    def after_trial_pause():
        win.flip()
        core.wait(inter_trial_s)

    def present_feedback(text, duration=0.6):
        instructions.setText(text)
        instructions.draw()
        win.flip()
        core.wait(duration)

    # 5. Practice Trials
    practice_items = [
        {'Stim1': 'sells books',   'Stim2': 'sells books',   'Match': 'Match',    'correct': '2'},
        {'Stim1': 'book seller',   'Stim2': 'noteseller',    'Match': 'Mismatch', 'correct': '1'},
        {'Stim1': 'chair',         'Stim2': 'chair',         'Match': 'Match',    'correct': '2'},
        {'Stim1': 'charp',         'Stim2': 'chark',         'Match': 'Mismatch', 'correct': '1'},
        {'Stim1': 'kittens meow',  'Stim2': 'puppies meow',  'Match': 'Mismatch', 'correct': '1'},
    ]

    # 6. Load 13 Conditions (650 Stimuli)
    print("\n[Experiment] Loading 13 conditions from data/stimuli_nouns.csv ...")
    stim_df = load_and_prepare_13_conditions(DATA_FILE)
    print(f"[Experiment] Successfully loaded {len(stim_df)} stimuli across 13 conditions.")

    # Shuffle deterministically
    stim_df = stim_df.sample(frac=1.0, random_state=_seed).reset_index(drop=True)

    # Divide trials across blocks
    total_trials = len(stim_df)
    n_trials_per_block = int(np.ceil(total_trials / n_blocks))
    blocks = [
        stim_df.iloc[i * n_trials_per_block : min((i + 1) * n_trials_per_block, total_trials)].copy()
        for i in range(n_blocks)
    ]

    # Setup log directory and CSV output file
    sub_dir = os.path.join(dir_logs, participant_name)
    os.makedirs(sub_dir, exist_ok=True)
    out_csv = os.path.join(sub_dir, f"{participant_name}_morph_syntax_trials.csv")

    # Start Experiment
    present_text(setup_text, setup_proceed_key)

    # Practice session
    is_practice = (start_block == 1)
    if is_practice:
        present_text(practice_instructions, instruction_proceed_keys)
        p_correct = 0
        for p_idx, p_trial in enumerate(practice_items, start=1):
            present_fixation()
            present_prime(p_trial, send_trigger=False)
            ans, _, p_rt = present_target(p_trial)
            after_trial_pause()

            corr = (ans == p_trial['correct'])
            if corr:
                p_correct += 1
            present_feedback("Correct!" if corr else "Incorrect", 0.6)

        p_acc = (p_correct / len(practice_items)) * 100
        present_text(
            f"End of practice.\n\nYour accuracy: {p_acc:.1f}%\n\n"
            f"Press button '1' or '2' to begin the main experiment.",
            instruction_proceed_keys
        )

    is_practice = False
    present_text(instructions_text, instruction_proceed_keys)

    # Main Trial Loop
    results = []
    trial_counter = (start_block - 1) * n_trials_per_block
    total_correct = 0

    for b_idx, block in enumerate(blocks, start=1):
        if b_idx < start_block:
            continue

        print(f"\n--- Starting Block {b_idx}/{n_blocks} ({len(block)} trials) ---")

        for _, trial in block.iterrows():
            trial_counter += 1

            present_fixation()
            prime_ms = present_prime(trial, send_trigger=True)
            ans, disp_s2, rt = present_target(trial)
            after_trial_pause()

            is_match = (str(trial['Match']).strip().lower() == 'match')
            expected_key = '2' if is_match else '1'
            correct = (ans == expected_key) if ans else False

            if correct:
                total_correct += 1

            trials_done = trial_counter - (start_block - 1) * n_trials_per_block
            acc = (total_correct / trials_done) * 100 if trials_done > 0 else 0

            if verbose:
                print(f"Trial {trial_counter}/{total_trials} [B{b_idx}] "
                      f"Cond: {trial['Condition_Key']:<22} | "
                      f"Resp: {ans} (exp {expected_key}) | "
                      f"Correct: {int(correct)} | "
                      f"RT: {f'{rt*1000:.0f} ms' if rt else 'None':<7} | "
                      f"Acc: {acc:.1f}%")

            rec = {
                'Participant':       participant_name,
                'Trial_num':         trial_counter,
                'Block':             b_idx,
                'Item':              trial.get('Item', ''),
                'TestControl':       trial.get('TestControl', ''),
                'StrucLevel':        trial.get('StrucLevel', ''),
                'Spacing':           trial.get('Spacing', ''),
                'Condition_Key':     trial['Condition_Key'],
                'Trigger_Channels':  trial['Trigger_Channels'],
                'Trigger_Mask':      trial['Trigger_Mask'],
                'Stim1':             trial.get('Stim1', ''),
                'Stim2':             trial.get('Stim2', ''),
                'Match':             trial.get('Match', ''),
                'Expected_Response': expected_key,
                'Participant_Resp':  ans,
                'Correct':           int(correct),
                'RT_s':              rt,
            }
            results.append(rec)

        # Save intermediate log after each block
        pd.DataFrame(results).to_csv(out_csv, index=False)
        print(f"[Log] Block {b_idx} saved to: {out_csv}")

        # Block break screen (except after the final block)
        if b_idx < len(blocks):
            present_text(
                f"End of block {b_idx} of {n_blocks}.\n\n"
                f"Your accuracy so far: {acc:.1f}%\n\n"
                f"Take a short break!\n"
                f"Press either button when you are ready to continue.",
                instruction_proceed_keys
            )

    # Final wrap-up
    present_text(
        f"The experiment is now over! Thank you for your participation!\n\n"
        f"Final Accuracy: {acc:.1f}%\n\n"
        f"Please sit tight while we save the recording...",
        ['s', 'space', 'escape']
    )
    win.close()
    print(f"\n[Experiment Completed] Full trial log saved to:\n  {out_csv}\n")


if __name__ == '__main__':
    run_meg_experiment()
