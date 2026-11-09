# Third-party notices

## Handy

The processing chain (voice activity smoothing, chunking, text cleanup, model catalog) is adapted from [Handy](https://github.com/cjpais/Handy) v0.10.0.

```
MIT License

Copyright (c) 2025 CJ Pais

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Dependencies

[transcribe.cpp](https://github.com/handy-computer/transcribe.cpp) (MIT, The transcribe.cpp authors) is installed from PyPI. Its packages carry their own license files, including those of ggml, miniz and Silero VAD. Other Python dependencies are listed in `requirements.txt`.

## Models

Models are not part of this repository. They are downloaded from Hugging Face on first start, pinned by revision and checked by SHA-256.

| Model | Repository | License |
| --- | --- | --- |
| Parakeet Ultra | `handy-computer/parakeet-ultra-gguf` | CC-BY-4.0 |
| Silero VAD v6.2 | `handy-computer/silero-vad-v6.2-gguf` | MIT |
| VoxLingua107 ECAPA | `handy-computer/lang-id-voxlingua107-ecapa-gguf` | Apache-2.0 |
