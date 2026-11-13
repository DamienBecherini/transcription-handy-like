"""Decodes the received audio (browser WebM/Opus, WAV, MP3, M4A…) to 16 kHz mono float32 PCM with ffmpeg."""
import os
import subprocess
import tempfile

import numpy as np

RATE = 16000


class InvalidAudio(ValueError):
    pass


def decode(data: bytes, timeout_s: float | None = None) -> np.ndarray:
    """The file goes through the disk rather than a pipe: ffmpeg must be able to seek back
    (MP4/MOV with the "moov" index at the end, otherwise it outputs nothing without complaining)."""
    if timeout_s is None:
        timeout_s = 60 + len(data) / 1_000_000   # one more second per MB (an hour of audio ≈ 60 MB)
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        f.write(data)
        path = f.name
    try:
        r = subprocess.run(
            ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", path,
             "-vn", "-f", "f32le", "-acodec", "pcm_f32le", "-ac", "1", "-ar", str(RATE), "pipe:1"],
            capture_output=True, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired as e:
        raise InvalidAudio("decoding took too long") from e
    finally:
        os.unlink(path)
    if r.returncode != 0:
        raise InvalidAudio(r.stderr.decode(errors="replace").strip()[-300:] or "ffmpeg failed")
    pcm = np.frombuffer(r.stdout, dtype=np.float32).copy()
    if len(pcm) == 0:
        raise InvalidAudio("no readable audio track")
    return pcm
