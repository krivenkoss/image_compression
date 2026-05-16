"""INI configuration loader for image compression studies.

Provides a thin wrapper around :mod:`configparser` that auto-casts types,
expands comma-separated lists, and validates the configuration against known
coder / metric / noise names.
"""
from __future__ import annotations

import configparser
import logging
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Known valid names — used for validation only.
_KNOWN_CODERS = {
    "AGU", "AGUm", "ADCT", "ADCTm", "BPG", "JPEG2000", "JPEG", "HEIF", "AVIF"
}
_KNOWN_NOISE = {
    "gaussian", "uniform", "speckle", "poisson",
    "mixed_poisson_gaussian", "correlated_gaussian", "ar1",
}

def _available_metrics() -> set[str]:
    """Return the set of metrics actually available in the current environment."""
    from metrics import METRIC_FUNCS  # lazy import avoids circular deps
    return set(METRIC_FUNCS.keys())


def _try_cast(value: str):
    """Cast a string to bool / int / float / list[...] / str / None.

    An empty string (or a string containing only whitespace) is returned as
    ``None`` so that optional INI keys left blank translate to Python ``None``
    rather than an empty string or zero.
    """
    stripped = value.strip()
    if stripped == "":
        return None
    if stripped.lower() in ("true", "yes", "on"):
        return True
    if stripped.lower() in ("false", "no", "off"):
        return False
    # Comma-separated list?
    if "," in stripped:
        parts = [p.strip() for p in stripped.split(",") if p.strip()]
        return [_try_cast(p) for p in parts]
    # Numeric?
    try:
        return int(stripped)
    except ValueError:
        pass
    try:
        return float(stripped)
    except ValueError:
        pass
    return stripped


def _apply_overrides(
    parser: configparser.ConfigParser,
    overrides: dict[str, str],
) -> None:
    """Apply dotted-key overrides, e.g. ``{"noise.std_values": "5,10,14"}``."""
    for key, val in overrides.items():
        parts = key.split(".", 1)
        if len(parts) != 2:
            raise ValueError(
                f"Override key '{key}' must be in 'section.option' form."
            )
        section, option = parts
        if not parser.has_section(section):
            parser.add_section(section)
        parser.set(section, option, val)


def _validate(cfg: dict) -> None:
    """Raise ValueError for unknown coder / metric / noise names."""
    coders = cfg.get("coders", {}).get("list", [])
    if isinstance(coders, str):
        coders = [coders]
    for c in coders:
        if c not in _KNOWN_CODERS:
            raise ValueError(
                f"Unknown coder '{c}' in [coders] list. Known: {sorted(_KNOWN_CODERS)}"
            )

    available = _available_metrics()
    metrics = cfg.get("metrics", {}).get("list", [])
    if isinstance(metrics, str):
        metrics = [metrics]
    for m in metrics:
        if m not in available:
            raise ValueError(
                f"Metric '{m}' is not available. "
                f"Available (depends on installed packages): {sorted(available)}"
            )

    kinds = cfg.get("noise", {}).get("kinds", [])
    if isinstance(kinds, str):
        kinds = [kinds]
    for k in kinds:
        if k not in _KNOWN_NOISE:
            raise ValueError(
                f"Unknown noise kind '{k}' in [noise] kinds. Known: {sorted(_KNOWN_NOISE)}"
            )


def load_ini(
    path: Path,
    overrides: dict[str, str] | None = None,
) -> dict:
    """Load an INI file and return a nested dict.

    Parameters
    ----------
    path : Path
        Path to the ``.ini`` configuration file.
    overrides : dict[str, str] or None
        Dotted-key overrides applied after file parsing, e.g.
        ``{"noise.std_values": "5,10,14"}``.

    Returns
    -------
    dict
        Nested dict; top-level keys are lowercase INI section names.
        ``[coder.X]`` sections land under ``cfg["coder_ranges"]["X"]``.
        Comma-separated values become lists. Booleans / ints / floats are
        auto-cast.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        On missing required sections, unknown coder/metric/noise names, or
        malformed ``[coder.X]`` range entries.

    Examples
    --------
    >>> from pathlib import Path
    >>> cfg = load_ini(Path("configs/study_01_noisy_vs_compressed.ini"))
    >>> "paths" in cfg
    True
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    parser = configparser.ConfigParser(
        interpolation=configparser.ExtendedInterpolation(),
        inline_comment_prefixes=(";", "#"),
    )
    parser.read(path, encoding="utf-8")

    if overrides:
        _apply_overrides(parser, overrides)

    cfg: dict = {}
    coder_ranges: dict = {}

    for section in parser.sections():
        if section.lower().startswith("coder."):
            coder_name = section[len("coder."):]
            ranges: dict = {}
            for option in parser.options(section):
                ranges[option] = _try_cast(parser.get(section, option))
            # Validate range structure
            for key in ("start", "stop", "step"):
                if key not in ranges:
                    raise ValueError(
                        f"[{section}] is missing the '{key}' key."
                    )
            coder_ranges[coder_name] = ranges
        else:
            sec_dict: dict = {}
            for option in parser.options(section):
                sec_dict[option] = _try_cast(parser.get(section, option))
            cfg[section.lower()] = sec_dict

    cfg["coder_ranges"] = coder_ranges

    # Ensure list values that might be single items are wrapped in lists
    for section_key, field in (
        ("coders", "list"),
        ("metrics", "list"),
        ("noise", "kinds"),
        ("images", "filenames"),
    ):
        if section_key in cfg and field in cfg[section_key]:
            val = cfg[section_key][field]
            if not isinstance(val, list):
                cfg[section_key][field] = [val]

    # Ensure std_values is a list of numbers
    if "noise" in cfg and "std_values" in cfg["noise"]:
        val = cfg["noise"]["std_values"]
        if not isinstance(val, list):
            cfg["noise"]["std_values"] = [val]

    _validate(cfg)
    return cfg


def informative_filename(
    study: str,
    image: str,
    coders: list[str],
    noise_kind: str,
    std,
    ext: str,
    out_dir: Path,
) -> Path:
    """Build a non-colliding output path with a timestamp suffix.

    The pattern is::

        {out_dir}/{study}__{image}__{coders}__noise-{noise_kind}-std{std}__{timestamp}.{ext}

    Parameters
    ----------
    study : str
        Study identifier, e.g. ``"study_01_noisy_vs_compressed"``.
    image : str
        Image filename or joined list, e.g. ``"fr02.bmp"``.
    coders : list[str]
        List of coder names; joined with ``+``.
    noise_kind : str
        Noise type tag.
    std : int or float or str
        Noise std (or combined tag).
    ext : str
        File extension without the dot (e.g. ``"csv"``), or empty string.
    out_dir : Path
        Directory to place the file in (created if necessary).

    Returns
    -------
    Path
        Full path including timestamp; no file is created by this function.

    Examples
    --------
    >>> from pathlib import Path
    >>> p = informative_filename("s01", "img.bmp", ["JPEG"], "gaussian", 10, "csv", Path("output"))
    >>> p.suffix == ".csv"
    True
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    coders_tag = "+".join(coders)
    # Sanitise image name (remove extension dots for clarity)
    image_tag = re.sub(r"[^\w.+-]", "_", image)
    stem = f"{study}__{image_tag}__{coders_tag}__noise-{noise_kind}-std{std}__{ts}"
    if ext:
        return out_dir / f"{stem}.{ext.lstrip('.')}"
    return out_dir / stem
