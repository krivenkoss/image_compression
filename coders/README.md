# Codec Binaries

This directory is intentionally **not shipped with executables**. Drop the
following binaries here yourself (they are gitignored — `git status` will
not see them).

| Executable     | Coder | Where to get it                                 |
|----------------|-------|-------------------------------------------------|
| `bpgenc.exe`   | BPG   | https://bellard.org/bpg/ (Windows build)         |
| `bpgdec.exe`   | BPG   | https://bellard.org/bpg/ (Windows build)         |
| `AGU.exe`      | AGU   | Contact the authors of the AGU codec             |
| `AGUm.exe`     | AGUm  | Contact the authors of the AGU codec             |
| `ADCT.exe`     | ADCT  | Contact the authors of the ADCT codec            |
| `ADCTm.exe`    | ADCTm | Contact the authors of the ADCT codec            |

If a `bpgenc.exe` Windows build ships extra DLLs
(`libgcc_s_seh-1.dll`, `libwinpthread-1.dll`, `libjpeg-62.dll`,
`libpng16-16.dll`, `libtiff-5.dll`, `openjp2.dll`, `SDL.dll`,
`SDL_image.dll`, `zlib1.dll`, `msvcp140.dll`, `vcruntime140.dll`,
`concrt140.dll`, `libstdc++-6.dll`), drop them here alongside the
executables.

JPEG, JPEG2000, HEIF, and AVIF are handled in-memory via Pillow /
pillow_heif and do **not** require any binary in this folder.

## Why are these gitignored?

The proprietary AGU / AGUm / ADCT / ADCTm executables are third-party
software whose redistribution rights we do not own; the BPG Windows
binaries fall under libbpg's own license. Excluding them from the
repository keeps publication clean and license-compliant. The Python
code raises `FileNotFoundError` with an informative message when a
binary is missing, so the rest of the framework still works on
JPEG / JPEG2000 / HEIF / AVIF without any local setup.
