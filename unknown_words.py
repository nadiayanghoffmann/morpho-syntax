import os, time, random, hashlib
import numpy as np
import pandas as pd

from psychopy import core, visual, event, data, gui
from psychopy.hardware import keyboard
from psychopy.preferences import prefs
from port_open_send import *
from sklearn.utils import shuffle

# ============================================================================#
# === Experiment Variables ===================================================#
# ============================================================================#

debug           = True
toggle_diode    = True
use_frame_rate  = False
send_triggers   = True
fullscr         = False
simulate_responses = False
verbose         = True

ROOT = '/Users/aab8523/Desktop/UnknownWords'   # <-- UPDATE THIS to the experiment directory

if debug:              print("DEBUG IS ON")
if not toggle_diode:   print("DIODE IS OFF")
if not send_triggers:  print("TRIGGERS IS SET TO OFF")
if simulate_responses: print("SIMULATING RESPONSES...")

# ============================================================================#
# === Experiment Setup =======================================================#
# ============================================================================#

dir_logs         = os.path.join(ROOT, 'logs')
participant_name = None
exp              = None   # will be set after practice

info  = {
    'Participant ID': '',
    'Start from block': '1',    # enter 2-5 to resume after an error
    'Fullscreen': False,
    'Auto respond?': False,
    'Frame rate?': False,
}
order = ['Participant ID', 'Start from block', 'Fullscreen', 'Auto respond?', 'Frame rate?']
dlg   = gui.DlgFromDict(dictionary=info, title='Unknown Words MEG', order=order)
if not dlg.OK:
    core.quit()

expt               = 'UnknownWords'
verbose            = True
toggle_diode       = True
send_triggers      = True
use_frame_rate     = info['Frame rate?']
participant_name   = info['Participant ID']
fullscr            = info['Fullscreen']
simulate_responses = info['Auto respond?']

try:
    start_block = max(1, int(info['Start from block']))
except (ValueError, TypeError):
    start_block = 1

print(f"Starting from block {start_block}")
print()

# Deterministic shuffle — same participant ID always yields the same trial order,
# so restarting from any block reproduces the same sequence.
_seed = int(hashlib.md5(participant_name.encode()).hexdigest()[:8], 16) % (2**31)
np.random.seed(_seed)
random.seed(_seed)

# ============================================================================#
# === Display Text and Key Setup =============================================#
# ============================================================================#

setup_text = "Please be patient as we set up the experiment..."

practice_instructions = (
    "Welcome to the practice session!\n\n"
    "You will see two short strings of words flash rapidly one after the other.\n\n"
    "Press '2' with your LEFT INDEX FINGER if they are the SAME.\n\n"
    "Press '1' with your LEFT MIDDLE FINGER if they are DIFFERENT.\n\n"
    "This practice session will be brief.\n"
    "When you are ready, press either button to continue."
)

instructions_text = (
    "This is the main experiment.\n\n"
    "You will see two short strings of words flash rapidly one after the other.\n\n"
    "Press '2' with your LEFT INDEX FINGER if they are the SAME.\n\n"
    "Press '1' with your LEFT MIDDLE FINGER if they are DIFFERENT.\n\n"
    "Respond as quickly and accurately as possible.\n\n"
    "When you are ready, press either button to continue."
)

pause = "Experiment paused. Wait for experimenter to continue."

setup_proceed_key         = ['s', 'escape']
instruction_proceed_keys  = ['left', 'right', '1', '2', 'escape']
end_proceed_key           = ['s', 'escape']

# --- Trigger map ---
# Stimulus1 onset → encodes STRUC (grammatical structure category)
struc_trigger_map = {
    'Grammatical': 'ch160',
    'Reversed':    'ch161',
    'Anomalous':   'ch162',
}
# Stimulus2 onset → encodes Match type
match_trigger_map = {
    0: 'ch163',   # SAME
    1: 'ch164',   # noun different
    2: 'ch165',   # adjective different
    3: 'ch166',   # structure word different
}

# ============================================================================#
# === Experiment Objects =====================================================#
# ============================================================================#

win          = visual.Window(monitor='default', units='pix', checkTiming=True, fullscr=fullscr, color='#444444')
stim_text    = visual.TextStim(win, text='', height=17, font='Menlo', wrapWidth=700, alignText='center', color='white')
answer_text  = visual.TextStim(win, text='', height=17, font='Menlo', wrapWidth=700, alignText='center', color='white')
fixation     = visual.TextStim(win, text='+', height=30, font='Menlo', wrapWidth=700, alignText='center', color='white')

# Regular instructions (center of screen — used without hand image)
instructions = visual.TextStim(win, text='', height=17, font='Menlo', wrapWidth=700,
                                pos=(0, 0), alignText='center', color='white')

# Instructions shifted up to make room for the hand image below
instructions_high = visual.TextStim(win, text='', height=17, font='Menlo', wrapWidth=700,
                                     pos=(0, 90), alignText='center', color='white')

photodiode   = visual.Rect(win, width=57, height=57, pos=[-483, 355], fillColor=[255, 255, 255], fillColorSpace='rgb255')

# Hand image — displayed below response-key instruction screens
_hand_path = os.path.join(ROOT, 'hand.png')
if os.path.exists(_hand_path):
    hand_img = visual.ImageStim(win, image=_hand_path, pos=(0, -210), size=(200, 200))
else:
    hand_img = None
    print(f"Warning: hand.png not found at {_hand_path}")

proceed         = keyboard.Keyboard()
trialClock      = core.Clock()
clock           = core.Clock()
defaultKeyboard = keyboard.Keyboard()
win.mouseVisible = False

# ============================================================================#
# === Experiment Timing ======================================================#
# ============================================================================#

frame_time_ms = win.monitorFramePeriod * 1000

fixation_ON_s  = 0.200   # fixation cross on
fixation_OFF_s = 0.200   # blank after fixation
prime_ON_s     = 0.300   # Stimulus1 and Stimulus2 on time
prime_OFF_s    = 0.500   # blank between Stimulus1 and Stimulus2
inter_trial_s  = 0.800   # blank after response

fixation_ON_ms  = fixation_ON_s  * 1000
fixation_OFF_ms = fixation_OFF_s * 1000
prime_ON_ms     = prime_ON_s     * 1000
prime_OFF_ms    = prime_OFF_s    * 1000
inter_trial_ms  = inter_trial_s  * 1000


# ============================================================================#
# === Emergency Save & Quit ==================================================#
# ============================================================================#

def save_and_quit():
    """Save log (if open) and exit cleanly. Triggered by pressing Escape."""
    print("\n[ESCAPE] Saving log and quitting...")
    if exp is not None and participant_name != 'test':
        try:
            exp.saveAsWideText(exp.dataFileName + '.csv')
            print(f"  Log saved to: {exp.dataFileName}.csv")
        except Exception as e:
            print(f"  Warning: could not force-save log: {e}")
    win.close()
    core.quit()


# ============================================================================#
# === Display Functions ======================================================#
# ============================================================================#


def present_text(text='', proceed_keys=['s'], simulate_responses=False):
    """Show plain instruction screen (no hand image)."""
    instructions.setText(text)
    instructions.draw()
    win.flip()
    if simulate_responses:
        return '1'
    keys = event.waitKeys(keyList=list(proceed_keys) + ['escape'])
    if keys[0] == 'escape':
        save_and_quit()
    return keys[0]


def present_text_with_hand(text='', proceed_keys=['s'], simulate_responses=False):
    """Show instruction screen with hand.png centered below the text."""
    instructions_high.setText(text)
    instructions_high.draw()
    if hand_img is not None:
        hand_img.draw()
    win.flip()
    if simulate_responses:
        return '1'
    keys = event.waitKeys(keyList=list(proceed_keys) + ['escape'])
    if keys[0] == 'escape':
        save_and_quit()
    return keys[0]


def present_fixation_core_wait(verbose=True):
    start_time = time.time()

    fixation.draw()
    win.flip()
    core.wait(fixation_ON_s)

    win.flip()
    core.wait(fixation_OFF_s)

    end_time = time.time()
    return (end_time - start_time) * 1000


def present_fixation_frame_rate(verbose=True):
    start_time = time.time()

    for _ in range(int(fixation_ON_ms / frame_time_ms + 1)):
        fixation.draw()
        win.flip()

    for _ in range(int(fixation_OFF_ms / frame_time_ms + 1)):
        win.flip()

    end_time = time.time()
    return (end_time - start_time) * 1000


def present_fixation(use_frame_rate, verbose=True):
    if use_frame_rate:
        return present_fixation_frame_rate(verbose)
    else:
        return present_fixation_core_wait(verbose)


def present_prime_core_wait(trial, send_trigger=True, verbose=True):
    """Show Stimulus1 for prime_ON_s, then blank for prime_OFF_s."""
    stim_text.setText(str(trial['Stimulus1']))
    win.callOnFlip(trialClock.reset)

    if send_trigger and not is_practice:
        ch = struc_trigger_map.get(str(trial.get('STRUC', '')))
        if ch:
            win.callOnFlip(sendTrigger, channel=ch, duration=0.02)

    stim_on_start = time.time()
    stim_text.draw()
    if toggle_diode:
        photodiode.draw()
    win.flip()
    core.wait(prime_ON_s)

    win.flip()
    core.wait(prime_OFF_s)

    stim_off_end = time.time()
    return (stim_off_end - stim_on_start) * 1000


def present_prime_frame_rate(trial, send_trigger=True, verbose=True):
    """Frame-rate version of prime presentation."""
    stim_text.setText(str(trial['Stimulus1']))
    win.callOnFlip(trialClock.reset)

    if send_trigger and not is_practice:
        ch = struc_trigger_map.get(str(trial.get('STRUC', '')))
        if ch:
            win.callOnFlip(sendTrigger, channel=ch, duration=0.02)

    stim_on_start = time.time()
    for _ in range(int(prime_ON_ms / frame_time_ms + 1)):
        stim_text.draw()
        if toggle_diode:
            photodiode.draw()
        win.flip()

    for _ in range(int(prime_OFF_ms / frame_time_ms + 1)):
        win.flip()

    stim_off_end = time.time()
    return (stim_off_end - stim_on_start) * 1000


def present_prime(trial, use_frame_rate, send_trigger=True, verbose=True):
    if use_frame_rate:
        return present_prime_frame_rate(trial, send_trigger, verbose)
    else:
        return present_prime_core_wait(trial, send_trigger, verbose)


def present_target(trial, use_frame_rate=False, verbose=True):
    """Show Stimulus2 for prime_ON_s, then blank until participant responds.
    Pressing Escape at any point saves the log and exits."""
    answer_text.setText(str(trial['Stimulus2']))

    # Trigger at Stimulus2 onset encoding match type
    if not is_practice and send_triggers:
        try:
            match_val = int(trial.get('Match', -1))
            ch = match_trigger_map.get(match_val)
            if ch:
                win.callOnFlip(sendTrigger, channel=ch, duration=0.02)
        except (TypeError, ValueError):
            pass

    if use_frame_rate:
        for _ in range(int(prime_ON_ms / frame_time_ms + 1)):
            answer_text.draw()
            if toggle_diode:
                photodiode.draw()
            win.flip()
    else:
        answer_text.draw()
        if toggle_diode:
            photodiode.draw()
        win.flip()
        core.wait(prime_ON_s)

    # Blank screen — wait for response
    win.flip()
    rt0 = time.time()

    if simulate_responses:
        answer   = str(random.randint(1, 2))
        core.wait(random.uniform(0.5, 0.9))
        end_time = time.time()
    else:
        keys     = event.waitKeys(keyList=['1', '2', 'escape', 'p'])
        end_time = time.time()
        if keys[0] == 'escape':
            save_and_quit()
        answer = keys[0]

    rt = end_time - rt0
    return answer, str(trial['Stimulus2']), rt


def after_trial_pause_core_wait():
    win.flip()
    core.wait(inter_trial_s)


def after_trial_pause_frame_rate():
    for _ in range(int(inter_trial_ms / frame_time_ms + 1)):
        win.flip()


def after_trial_pause(use_frame_rate):
    if use_frame_rate:
        after_trial_pause_frame_rate()
    else:
        after_trial_pause_core_wait()


def present_feedback_core_wait(text, duration=0.6, verbose=True):
    instructions.setText(text)
    instructions.draw()
    win.flip()
    core.wait(duration)


def present_feedback_frame_rate(text, duration=0.6, verbose=True):
    instructions.setText(text)
    for _ in range(int(duration * 1000 / frame_time_ms + 1)):
        instructions.draw()
        win.flip()


def present_feedback(text, duration, use_frame_rate, verbose=True):
    if use_frame_rate:
        present_feedback_frame_rate(text, duration, verbose)
    else:
        present_feedback_core_wait(text, duration, verbose)


# ============================================================================#
# === Set up Blocks ==========================================================#
# ============================================================================#

# Hardcoded practice trials (from main.js)
# correct: '2' = SAME, '1' = DIFFERENT
practice_items = [
    {'Stimulus1': 'girls read books',     'Stimulus2': 'girls study books',     'correct': '1'},
    {'Stimulus1': 'leaf tree pond',        'Stimulus2': 'leaf tree pond',         'correct': '2'},
    {'Stimulus1': 'dogs chew bones',       'Stimulus2': 'dogs chew bones',        'correct': '2'},
    {'Stimulus1': 'drive car roads',       'Stimulus2': 'drive car streets',      'correct': '1'},
    {'Stimulus1': 'soft are plarms the',   'Stimulus2': 'soft are plarms all',    'correct': '1'},
]

stimuli_fn   = 'stimulus-list.csv'
stimuli_path = os.path.join(ROOT, stimuli_fn)
stimuli      = pd.read_csv(stimuli_path)
stimuli      = shuffle(stimuli)   # deterministic via np.random.seed above

n_blocks           = 5
n_trials_per_block = 80   # 400 trials / 5 blocks
blocks = [
    shuffle(stimuli.iloc[i * n_trials_per_block : (i + 1) * n_trials_per_block])
    for i in range(n_blocks)
]

# ============================================================================#
# === Begin Experiment =======================================================#
# ============================================================================#

present_text(setup_text, setup_proceed_key)

# --- Practice (skip if resuming mid-experiment) ---
if start_block == 1:
    present_text_with_hand(practice_instructions, instruction_proceed_keys)
    practice_correct = 0
    is_practice      = True

    for p_num, trial in enumerate(practice_items, start=1):

        fixation_time            = present_fixation(use_frame_rate)
        prime_time               = present_prime(trial, use_frame_rate, send_trigger=False)
        answer, display_text, rt = present_target(trial, use_frame_rate)
        after_trial_pause(use_frame_rate)

        correct = (answer == trial['correct'])
        if correct:
            practice_correct += 1
        acc = (practice_correct / p_num) * 100

        present_feedback("Correct!" if correct else "Incorrect", 0.6, use_frame_rate)

        print(f"\nPractice Trial ({p_num}/{len(practice_items)})")
        print(f"  Fixation time:  {fixation_time:.2f} ms")
        print(f"  Prime:          {trial['Stimulus1']}")
        print(f"  Target:         {display_text}")
        print(f"  Prime ON time:  {prime_time:.2f} ms")
        print(f"  Response:       {answer}  (correct: {trial['correct']})")
        print(f"  Correct?        {int(correct)}")
        print(f"  Accuracy:       {acc:.1f}%")
        print(f"  RT:             {rt * 1000:.0f} ms")

    acc = (practice_correct / len(practice_items)) * 100
    present_text(
        f"End of practice.\n\nYour accuracy is: {acc:.1f}%.\n\n"
        f"Press either button when you are ready to continue.",
        ['1', '2', 's', 'escape']
    )
else:
    is_practice = False
    print(f"Skipping practice — resuming from block {start_block}.")

# --- Data logger ---
if participant_name != 'test':
    os.makedirs(os.path.join(dir_logs, participant_name), exist_ok=True)
    exp = data.ExperimentHandler(
        dataFileName=os.path.join(dir_logs, participant_name,
                                  f'{participant_name}_{expt}_logfile'),
        autoLog=False, savePickle=False
    )

# ============================================================================#
# === Main Experiment Loop ===================================================#
# ============================================================================#

is_practice      = False
trialNum         = (start_block - 1) * n_trials_per_block   # offset if resuming
total_correct    = 0
experiment_start = time.time()
total_trials     = sum(len(block) for block in blocks)

present_text(setup_text, setup_proceed_key)
present_text_with_hand(instructions_text, instruction_proceed_keys)

for b, block in enumerate(blocks, start=1):

    # Skip blocks already completed
    if b < start_block:
        continue

    for _, trial in block.iterrows():

        fixation_time            = present_fixation(use_frame_rate, verbose=False)
        prime_time               = present_prime(trial, use_frame_rate, verbose=False)
        answer, display_text, rt = present_target(trial, use_frame_rate, verbose=False)
        after_trial_pause(use_frame_rate)

        is_match = (int(trial['Match']) == 0)
        correct  = (is_match and answer == '2') or (not is_match and answer == '1')
        if correct:
            total_correct += 1
        trialNum += 1
        accuracy = (total_correct / (trialNum - (start_block - 1) * n_trials_per_block)) * 100

        print(f"\nTrial ({trialNum}/{total_trials})")
        print(f"  Block:         {b}")
        print(f"  Fixation time: {fixation_time:.2f} ms")
        print(f"  SET:           {trial['SET']}  "
              f"Cond: {trial['Cond_ID']}  "
              f"STRUC: {trial['STRUC']}  "
              f"Match: {trial['Match']}")
        print(f"  Prime:         {trial['Stimulus1']}")
        print(f"  Prime ON time: {prime_time:.2f} ms")
        print(f"  Target:        {display_text}")
        print(f"  Response:      {answer}")
        print(f"  Correct?       {int(correct)}")
        print(f"  Accuracy:      {accuracy:.1f}%")
        print(f"  RT:            {rt * 1000:.0f} ms")

        if participant_name != 'test':
            exp.addData('Participant',    participant_name)
            exp.addData('Trial_num',      trialNum)
            exp.addData('Block',          str(b))
            exp.addData('Response',       answer)
            exp.addData('Correct',        int(correct))
            exp.addData('RT',             rt)
            for col in trial.index:
                exp.addData(col, trial[col])
            exp.nextEntry()

    trials_so_far = trialNum - (start_block - 1) * n_trials_per_block
    acc = (total_correct / trials_so_far) * 100 if trials_so_far > 0 else 0
    if b != len(blocks):
        present_text(
            f"End of block {b}.\n\n"
            f"Your accuracy is: {acc:.1f}%.\n\n"
            f"Remember: press '2' when the strings are the SAME, "
            f"and '1' when they are DIFFERENT.\n\n"
            f"Press either button when you are ready to continue.",
            ['1', '2', 's', 'escape']
        )
    else:
        print('END OF SESSION')

# ============================================================================#
# === End Experiment =========================================================#
# ============================================================================#

trials_so_far = trialNum - (start_block - 1) * n_trials_per_block
acc = (total_correct / trials_so_far) * 100 if trials_so_far > 0 else 0
present_text(
    f"The experiment is now over! Thank you for your participation!\n\n"
    f"Your accuracy is: {acc:.1f}%.\n\n"
    f"Please sit tight while we save the recording...",
    ['s', 'escape']
)
win.close()

experiment_end      = time.time()
experiment_time_s   = experiment_end - experiment_start
experiment_time_min = experiment_time_s / 60.0

if verbose:
    print("Total Experiment Time in seconds:", str(experiment_time_s))
    print("Total Experiment Time in minutes:", str(experiment_time_min))
    print("Accuracy: %s" % acc)
