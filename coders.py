"""Lossy image compression wrappers.

Supported coders: JPEG, JPEG2000, HEIF, AVIF, BPG, AGU, AGUm, ADCT, ADCTm.

For standard coders (JPEG, JPEG2000, HEIF, AVIF) encoding is done in-memory
via Pillow / pillow_heif. For proprietary coders (AGU, AGUm, ADCT, ADCTm, BPG)
subprocess calls are made to binaries expected in the ``coders/`` directory.
"""
from __future__ import annotations

import io
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Union

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Parameter ranges — copied exactly from legacy/oop.py lines 33–62
# ---------------------------------------------------------------------------

DEFAULT_RANGES: dict[str, dict[str, float]] = {
    "AGU":      {"start": 2,   "stop": 200, "step": 1},
    "AGUm":     {"start": 2,   "stop": 200, "step": 1},
    "ADCT":     {"start": 2,   "stop": 200, "step": 1},
    "ADCTm":    {"start": 2,   "stop": 200, "step": 1},
    "BPG":      {"start": 2,   "stop": 51,  "step": 1},
    "JPEG2000": {"start": 1.2, "stop": 33,  "step": 0.1},
    "JPEG":     {"start": 1,   "stop": 100, "step": 1},
    "HEIF":     {"start": 1,   "stop": 100, "step": 1},
    "AVIF":     {"start": 1,   "stop": 100, "step": 1},
}

_CODERS_DIR = Path(__file__).parent / "coders"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_exe(name: str) -> Path:
    """Return path to a coder executable; search PATH then coders/ directory."""
    on_path = shutil.which(name)
    if on_path:
        return Path(on_path)
    candidate = _CODERS_DIR / name
    if candidate.exists():
        return candidate
    raise FileNotFoundError(
        f"Executable '{name}' not found on PATH or in '{_CODERS_DIR}'. "
        f"Download the binary and place it in the coders/ directory. "
        f"See coders/README.md for download hints."
    )


def _array_to_raw(image: np.ndarray, path: Path) -> None:
    """Write uint8 2-D array as flat binary (row-major, no header)."""
    path.write_bytes(image.flatten(order="C").tobytes())


def _raw_to_array(path: Path, shape: tuple[int, int]) -> np.ndarray:
    """Read flat binary back into a uint8 2-D array of given shape."""
    data = np.frombuffer(path.read_bytes(), dtype=np.uint8)
    return data.reshape(shape, order="C")


def _run(cmd: str) -> None:
    """Run a shell command string; raise on non-zero exit."""
    subprocess.check_call(cmd, shell=True)


def _cr_from_shapes(source_bytes: int, compressed_bytes: int) -> float:
    """Compression ratio = uncompressed / compressed."""
    return source_bytes / max(compressed_bytes, 1)


# ---------------------------------------------------------------------------
# Per-coder implementations (grayscale 2-D arrays)
# ---------------------------------------------------------------------------

def _compress_jpeg(image: np.ndarray, quality: int) -> tuple[np.ndarray, float]:
    buf = io.BytesIO()
    pil = Image.fromarray(image)
    pil.save(buf, format="JPEG", quality=int(quality))
    encoded = buf.getvalue()
    decoded = np.array(Image.open(io.BytesIO(encoded)).convert("L"))
    raw_bytes = image.size  # H*W bytes for grayscale
    cr = _cr_from_shapes(raw_bytes, len(encoded))
    return decoded, cr


def _compress_jpeg2000(image: np.ndarray, compression_ratio: float) -> tuple[np.ndarray, float]:
    buf = io.BytesIO()
    pil = Image.fromarray(image)
    pil.save(buf, format="JPEG2000", quality_mode="rates", quality_layers=[compression_ratio])
    encoded = buf.getvalue()
    decoded = np.array(Image.open(io.BytesIO(encoded)).convert("L"))
    raw_bytes = image.size
    cr = _cr_from_shapes(raw_bytes, len(encoded))
    return decoded, cr


def _compress_heif_avif(image: np.ndarray, quality: int, fmt: str) -> tuple[np.ndarray, float]:
    import pillow_heif
    pillow_heif.register_heif_opener()
    buf = io.BytesIO()
    pil = Image.fromarray(image)
    pil.save(buf, format=fmt, quality=int(quality))
    encoded = buf.getvalue()
    decoded_pil = Image.open(io.BytesIO(encoded)).convert("L")
    decoded = np.array(decoded_pil)
    raw_bytes = image.size
    cr = _cr_from_shapes(raw_bytes, len(encoded))
    return decoded, cr


def _compress_bpg(image: np.ndarray, qp: int) -> tuple[np.ndarray, float]:
    bpgenc = _find_exe("bpgenc.exe")
    bpgdec = _find_exe("bpgdec.exe")
    tmpdir = Path(tempfile.mkdtemp())
    try:
        src_png = tmpdir / "src.png"
        cod = tmpdir / "out.bpg"
        dec_png = tmpdir / "dec.png"
        cv2.imwrite(str(src_png), image, [cv2.IMWRITE_PNG_COMPRESSION, 0])
        _run(f'"{bpgenc}" -m 9 -b 8 -q {int(qp)} "{src_png}" -o "{cod}"')
        _run(f'"{bpgdec}" -o "{dec_png}" "{cod}"')
        decoded = cv2.imread(str(dec_png), 0)
        raw_bytes = image.size
        cr = _cr_from_shapes(raw_bytes, cod.stat().st_size)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return decoded, cr


def _compress_agu_style(
    image: np.ndarray,
    param: int,
    exe_name: str,
    cleanup_lastps: bool = False,
) -> tuple[np.ndarray, float]:
    """Generic AGU / AGUm / ADCT / ADCTm subprocess wrapper.

    Ported from ``get_compressed_image_II`` in legacy/image_utils.py.
    Uses a per-call temp directory so concurrent runs do not collide.
    """
    exe = _find_exe(exe_name)
    tmpdir = Path(tempfile.mkdtemp())
    try:
        raw_path = tmpdir / "temp.raw"
        cod_path = tmpdir / "temp.cod"
        out_path = tmpdir / "temp.out"
        shape = image.shape[:2]  # (H, W)
        _array_to_raw(image, raw_path)
        # encode
        _run(f'"{exe}" e "{raw_path}" "{cod_path}" {int(param)}')
        if not cod_path.exists():
            raise RuntimeError(
                f"{exe_name} encoder did not produce '{cod_path.name}'. "
                f"These codecs require a 512×512 input image "
                f"(got {image.shape[1]}×{image.shape[0]})."
            )
        # decode
        _run(f'"{exe}" d "{cod_path}" "{out_path}"')
        if not out_path.exists():
            raise RuntimeError(
                f"{exe_name} decoder did not produce '{out_path.name}'."
            )
        decoded = _raw_to_array(out_path, shape)
        raw_bytes = raw_path.stat().st_size
        cr = _cr_from_shapes(raw_bytes, cod_path.stat().st_size)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return decoded, cr


# ---------------------------------------------------------------------------
# Colour routing
# ---------------------------------------------------------------------------

def _compress_channelwise(
    image: np.ndarray,
    fn,
) -> tuple[np.ndarray, float]:
    """Apply a grayscale compression function per channel and stack results."""
    channels = [fn(image[:, :, c]) for c in range(image.shape[2])]
    decoded = np.stack([ch[0] for ch in channels], axis=2)
    cr = float(np.mean([ch[1] for ch in channels]))
    return decoded, cr


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compress(
    image: np.ndarray,
    coder: str,
    param: Union[int, float],
) -> tuple[np.ndarray, float]:
    """Compress and decompress an image once; return the decoded array and CR.

    Parameters
    ----------
    image : np.ndarray
        Input image, uint8, 2-D (H×W grayscale) or 3-D (H×W×C BGR colour).
    coder : str
        Coder name — one of ``JPEG``, ``JPEG2000``, ``HEIF``, ``AVIF``,
        ``BPG``, ``AGU``, ``AGUm``, ``ADCT``, ``ADCTm``.
    param : int or float
        Compression parameter (quality / quantisation step / compression ratio
        depending on the coder).  See :data:`DEFAULT_RANGES` for valid ranges.

    Returns
    -------
    tuple[np.ndarray, float]
        ``(decoded_image, compression_ratio)`` where *decoded_image* has the
        same shape and dtype as *image* and *compression_ratio* > 1 means
        compression was achieved.

    Raises
    ------
    ValueError
        If *coder* is not recognised.
    FileNotFoundError
        If a required binary is missing from PATH / ``coders/`` directory.

    Examples
    --------
    >>> import numpy as np
    >>> img = np.random.randint(0, 256, (64, 64), dtype=np.uint8)
    >>> decoded, cr = compress(img, "JPEG", 75)
    >>> decoded.shape == img.shape and cr > 1
    True
    """
    colour = image.ndim == 3
    coder = coder.upper() if coder not in ("AGUm", "ADCTm") else coder

    # Pillow handles colour natively; proprietary coders run per channel.
    if coder == "JPEG":
        if colour:
            return _compress_channelwise(image, lambda ch: _compress_jpeg(ch, int(param)))
        return _compress_jpeg(image, int(param))

    if coder == "JPEG2000":
        if colour:
            return _compress_channelwise(image, lambda ch: _compress_jpeg2000(ch, float(param)))
        return _compress_jpeg2000(image, float(param))

    if coder in ("HEIF", "AVIF"):
        fmt = coder
        if colour:
            return _compress_channelwise(
                image, lambda ch: _compress_heif_avif(ch, int(param), fmt)
            )
        return _compress_heif_avif(image, int(param), fmt)

    if coder == "BPG":
        if colour:
            return _compress_channelwise(image, lambda ch: _compress_bpg(ch, int(param)))
        return _compress_bpg(image, int(param))

    _agu_map: dict[str, tuple[str, bool]] = {
        "AGU":   ("AGU.exe",   False),
        "AGUm":  ("AGUm.exe",  False),
        "ADCT":  ("ADCT.exe",  True),
        "ADCTm": ("ADCTm.exe", True),
    }
    if coder in _agu_map:
        exe_name, _ = _agu_map[coder]
        if colour:
            return _compress_channelwise(
                image, lambda ch: _compress_agu_style(ch, int(param), exe_name)
            )
        return _compress_agu_style(image, int(param), exe_name)

    raise ValueError(
        f"Unknown coder '{coder}'. Supported: {sorted(DEFAULT_RANGES)}"
    )
