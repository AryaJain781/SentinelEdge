"""NSL-KDD flow parser: 41 named features, binary label, attack category.

The NSL-KDD files have no header row. Each line is one connection with 41
feature values, then the attack name, then a difficulty score (0 to 21).
This module names the columns, maps every attack name to a binary label
(0 = normal, 1 = attack) and to one of four attack categories, and keeps the
three text columns (protocol, service, flag) as text for later encoding.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

FEATURE_COLUMNS: tuple[str, ...] = (
    "duration",
    "protocol_type",
    "service",
    "flag",
    "src_bytes",
    "dst_bytes",
    "land",
    "wrong_fragment",
    "urgent",
    "hot",
    "num_failed_logins",
    "logged_in",
    "num_compromised",
    "root_shell",
    "su_attempted",
    "num_root",
    "num_file_creations",
    "num_shells",
    "num_access_files",
    "num_outbound_cmds",
    "is_host_login",
    "is_guest_login",
    "count",
    "srv_count",
    "serror_rate",
    "srv_serror_rate",
    "rerror_rate",
    "srv_rerror_rate",
    "same_srv_rate",
    "diff_srv_rate",
    "srv_diff_host_rate",
    "dst_host_count",
    "dst_host_srv_count",
    "dst_host_same_srv_rate",
    "dst_host_diff_srv_rate",
    "dst_host_same_src_port_rate",
    "dst_host_srv_diff_host_rate",
    "dst_host_serror_rate",
    "dst_host_srv_serror_rate",
    "dst_host_rerror_rate",
    "dst_host_srv_rerror_rate",
)

TEXT_COLUMNS: tuple[str, ...] = ("protocol_type", "service", "flag")
LABEL_COLUMN = "label"
CATEGORY_COLUMN = "attack_category"
DIFFICULTY_COLUMN = "difficulty"

CATEGORIES: tuple[str, ...] = ("Normal", "DoS", "Probe", "R2L", "U2R")

# Standard NSL-KDD grouping of attack names into four families.
# "worm" is placed in DoS here; some papers place it elsewhere (see docs).
ATTACK_CATEGORY: dict[str, str] = {
    # Denial of service
    "back": "DoS",
    "land": "DoS",
    "neptune": "DoS",
    "pod": "DoS",
    "smurf": "DoS",
    "teardrop": "DoS",
    "apache2": "DoS",
    "udpstorm": "DoS",
    "processtable": "DoS",
    "mailbomb": "DoS",
    "worm": "DoS",
    # Probing (scanning)
    "ipsweep": "Probe",
    "nmap": "Probe",
    "portsweep": "Probe",
    "satan": "Probe",
    "mscan": "Probe",
    "saint": "Probe",
    # Remote to local
    "ftp_write": "R2L",
    "guess_passwd": "R2L",
    "imap": "R2L",
    "multihop": "R2L",
    "phf": "R2L",
    "spy": "R2L",
    "warezclient": "R2L",
    "warezmaster": "R2L",
    "sendmail": "R2L",
    "named": "R2L",
    "snmpgetattack": "R2L",
    "snmpguess": "R2L",
    "xlock": "R2L",
    "xsnoop": "R2L",
    "httptunnel": "R2L",
    # User to root
    "buffer_overflow": "U2R",
    "loadmodule": "U2R",
    "perl": "U2R",
    "rootkit": "U2R",
    "ps": "U2R",
    "sqlattack": "U2R",
    "xterm": "U2R",
    # Normal traffic
    "normal": "Normal",
}


class UnknownAttackError(ValueError):
    """Raised when a file contains an attack name not in ``ATTACK_CATEGORY``."""


def _detect_delimiter(path: Path) -> str:
    """NSL-KDD copies use either tabs (Zenodo) or commas (GitHub). Check line 1."""
    with path.open("r", encoding="utf-8") as handle:
        first_line = handle.readline()
    return "\t" if "\t" in first_line else ","


def parse_nsl_kdd(path: Path | str) -> pd.DataFrame:
    """Read one NSL-KDD file into a DataFrame with named columns.

    Returns the 41 feature columns, ``label`` (0 normal, 1 attack),
    ``attack_category`` (Normal, DoS, Probe, R2L or U2R) and ``difficulty``.
    Raises ``UnknownAttackError`` if an attack name is not recognised.
    """
    source = Path(path)
    delimiter = _detect_delimiter(source)
    raw = pd.read_csv(
        source, header=None, sep=delimiter, dtype=str, keep_default_na=False
    )
    if raw.shape[1] != 43:
        raise ValueError(
            f"Expected 43 columns (41 features, name, difficulty), got {raw.shape[1]}"
        )

    frame = raw.copy()
    frame.columns = [*FEATURE_COLUMNS, "attack_name", DIFFICULTY_COLUMN]
    attack_names = frame.pop("attack_name").astype(str).str.strip().str.lower()

    unknown = sorted(set(attack_names) - set(ATTACK_CATEGORY))
    if unknown:
        raise UnknownAttackError(f"Unrecognised attack names: {unknown[:10]}")

    categories = attack_names.map(ATTACK_CATEGORY)
    frame[LABEL_COLUMN] = (categories != "Normal").astype(int)
    frame[CATEGORY_COLUMN] = categories
    frame[DIFFICULTY_COLUMN] = frame[DIFFICULTY_COLUMN].astype(int)
    for column in FEATURE_COLUMNS:
        if column not in TEXT_COLUMNS:
            frame[column] = pd.to_numeric(frame[column])
    return frame
