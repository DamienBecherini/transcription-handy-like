"""Voice detection as in Handy v0.10.0: Silero VAD v6.2, then smoothing, and only speech is kept.

Taken from Handy (src-tauri/src/audio_toolkit/vad/smoothed.rs, managers/audio.rs, audio/sink.rs):
- 512-sample frames (32 ms), speech if the probability is > 0.3;
- 450 ms pre-roll (15 frames), onset after 2 voiced frames, 450 ms hangover (15 frames);
- every frame not kept is removed, including in the middle of the recording;
- less than 1 s of speech: padded with zeros up to 1.25 s.
Handy reads the probabilities while recording; here the recording is whole, so they are computed
in one go (same recurrent state, frame after frame), then the same state machine is applied.
"""
from collections import deque

import numpy as np

THRESHOLD = 0.3
PREROLL = 15
ONSET = 2
HANGOVER = 15
RATE = 16000
MIN_BEFORE_PADDING = RATE          # 1 s
PADDED_LENGTH = 20000              # 1.25 s


def kept_frames(probs, threshold=THRESHOLD, preroll=PREROLL, onset=ONSET, hangover=HANGOVER):
    """Indices of the kept frames, in order (Handy's SmoothedVad state machine)."""
    kept = []
    buffer = deque()            # [index, emitted] of the last frames, pre-roll included
    in_speech = False
    onset_count = 0
    hangover_count = 0
    for i, p in enumerate(probs):
        buffer.append([i, False])
        while len(buffer) > preroll + 1:
            buffer.popleft()
        voiced = p > threshold
        if not in_speech and voiced:
            onset_count += 1
            if onset_count >= onset:
                in_speech = True
                hangover_count = hangover
                onset_count = 0
                for f in buffer:
                    if not f[1]:
                        kept.append(f[0])
                        f[1] = True
        elif in_speech and voiced:
            hangover_count = hangover
            buffer[-1][1] = True
            kept.append(i)
        elif in_speech:
            if hangover_count > 0:
                hangover_count -= 1
                buffer[-1][1] = True
                kept.append(i)
            else:
                in_speech = False
        else:
            onset_count = 0
    return kept


def keep_speech(pcm: np.ndarray, probs, frame_size: int) -> np.ndarray:
    """Concatenates the kept frames (the last incomplete frame has no probability: ignored, as in Handy)."""
    indices = kept_frames(probs)
    if not indices:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate([pcm[i * frame_size:(i + 1) * frame_size] for i in indices]).astype(np.float32)


def pad(pcm: np.ndarray) -> np.ndarray:
    """Speech shorter than 1 s: zeros up to 1.25 s (the model gets very short clips wrong)."""
    if 0 < len(pcm) < MIN_BEFORE_PADDING:
        return np.concatenate([pcm, np.zeros(PADDED_LENGTH - len(pcm), dtype=np.float32)])
    return pcm
