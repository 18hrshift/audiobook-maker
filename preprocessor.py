"""
TTS preprocessing — runs on cleaned text just before it goes to the TTS engine.
Distinct from text_processor.py (which cleans raw extracted text).
This stage makes text sound natural when spoken aloud.
"""

import re
from num2words import num2words


# ── Abbreviation expansion ─────────────────────────────────────────────────────
# Order matters — longer patterns first to avoid partial matches

ABBREVIATIONS = {
    # Titles
    r"\bDr\.": "Doctor",
    r"\bMr\.": "Mister",
    r"\bMrs\.": "Misses",
    r"\bMs\.": "Miss",
    r"\bProf\.": "Professor",
    r"\bSt\.": "Saint",
    r"\bGov\.": "Governor",
    r"\bGen\.": "General",
    r"\bSgt\.": "Sergeant",
    r"\bCpt\.": "Captain",
    r"\bCpl\.": "Corporal",
    r"\bPvt\.": "Private",
    r"\bRev\.": "Reverend",
    r"\bHon\.": "Honorable",
    # Common words
    r"\betc\.": "etcetera",
    r"\bvs\.": "versus",
    r"\be\.g\.": "for example",
    r"\bi\.e\.": "that is",
    r"\bviz\.": "namely",
    r"\bapprox\.": "approximately",
    r"\bdept\.": "department",
    r"\bno\.": "number",
    # US states (common in addresses/context)
    r"\bPA\b": "Pennsylvania",
    r"\bCA\b": "California",
    r"\bNY\b": "New York",
    r"\bTX\b": "Texas",
    r"\bFL\b": "Florida",
    r"\bIL\b": "Illinois",
}

# Compile once
_ABBREV_PATTERNS = [(re.compile(pat), repl) for pat, repl in ABBREVIATIONS.items()]


# ── Number conversion rules ────────────────────────────────────────────────────
# Don't convert: years (1900-2099), page numbers, ISBN, version numbers (v1.2)

_YEAR_RE = re.compile(r"\b(1[89]\d{2}|20[012]\d)\b")
_VERSION_RE = re.compile(r"\bv\d+[\.\d]*\b", re.IGNORECASE)
_DECIMAL_RE = re.compile(r"\b(\d+)\.(\d+)\b")
_ORDINAL_RE = re.compile(r"\b(\d+)(st|nd|rd|th)\b", re.IGNORECASE)
_PLAIN_INT_RE = re.compile(r"\b(\d{1,9})\b")


def preprocess_for_tts(text: str) -> str:
    """Full preprocessing pipeline for a text chunk going to TTS."""
    text = _expand_abbreviations(text)
    text = _convert_numbers(text)
    text = _inject_pauses(text)
    text = _final_cleanup(text)
    return text


def _expand_abbreviations(text: str) -> str:
    for pattern, replacement in _ABBREV_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _convert_numbers(text: str) -> str:
    # Protect years — replace with placeholder
    years = {}
    def protect_year(m):
        key = f"__YEAR{len(years)}__"
        years[key] = m.group(0)
        return key
    text = _YEAR_RE.sub(protect_year, text)

    # Protect version numbers
    versions = {}
    def protect_version(m):
        key = f"__VER{len(versions)}__"
        versions[key] = m.group(0)
        return key
    text = _VERSION_RE.sub(protect_version, text)

    # Decimals: "3.14" → "3 point 14"
    def convert_decimal(m):
        return f"{m.group(1)} point {m.group(2)}"
    text = _DECIMAL_RE.sub(convert_decimal, text)

    # Ordinals: "1st" → "first", "22nd" → "twenty-second"
    def convert_ordinal(m):
        try:
            return num2words(int(m.group(1)), to="ordinal")
        except Exception:
            return m.group(0)
    text = _ORDINAL_RE.sub(convert_ordinal, text)

    # Plain integers: "42" → "forty-two"
    # Skip large numbers (likely IDs/codes) and single digits already in words
    def convert_int(m):
        val = int(m.group(1))
        if val > 999999:  # Don't read out 7+ digit numbers
            return m.group(0)
        try:
            return num2words(val)
        except Exception:
            return m.group(0)
    text = _PLAIN_INT_RE.sub(convert_int, text)

    # Restore protected items
    for key, val in years.items():
        text = text.replace(key, val)
    for key, val in versions.items():
        text = text.replace(key, val)

    return text


def _inject_pauses(text: str) -> str:
    """
    Insert natural pause markers at paragraph breaks.
    Voxtral/TTS models respond to ellipses and em-dashes as pause cues.
    A double newline (paragraph break) gets a brief pause marker.
    """
    # Paragraph break → period + newline (ensures TTS pauses between paragraphs)
    text = re.sub(r"\n\n+", "\n\n", text)  # normalize first
    # If a paragraph doesn't end with punctuation, add a period so TTS pauses
    text = re.sub(r"([^\.\!\?\n])\n\n", r"\1.\n\n", text)
    return text


def _final_cleanup(text: str) -> str:
    # Remove any leftover markdown symbols that sneak through
    text = re.sub(r"[#*_`~]", "", text)
    # Collapse multiple spaces
    text = re.sub(r"  +", " ", text)
    return text.strip()
