"""ExecuTorch AOT export: Llama 3.2 1B Instruct -> 4-bit groupwise .pte + tokenizer.

Status: **this is a reference implementation of the documented plan in
docs/executorch_summary.md and ADR-0009 -- it has never been run, anywhere,
by this project.** The sandbox this was authored in has no `torch`, no
`executorch`, no `optimum`, no `torchao`, and no network access to install
any of them or to download gated model weights. WP6 (the ExecuTorch-export
sense of that label, not the documentation-phase sense -- see
docs/technical_report.md Section 2 for why those are two different things in
this repo) has not started. Running this script is WP6's actual work, not
something this authoring session could complete standing in for the team.

Before this script can run at all, a team member must, by hand, outside any
script (these are consent/identity steps that cannot be automated here):

1. Create or use a Hugging Face account and accept Meta's Llama 3.2
   Community License on the model page
   (https://huggingface.co/meta-llama/Llama-3.2-1B-Instruct). Access is
   gated and reviewed by Meta/HF; it is not instant for every account.
2. Generate a Hugging Face access token with read access to gated repos, and
   set it as an environment variable before running this script:
   ``export HF_TOKEN=hf_...`` (PowerShell: ``$env:HF_TOKEN = "hf_..."``).
3. Install the toolchain on a machine with enough RAM and disk (the BF16
   checkpoint alone is ~2.46 GB, per docs/executorch_summary.md Section 3):
   ``pip install torch executorch optimum[executorch] torchao``
   -- exact package names/versions change with ExecuTorch releases; check
   the official docs linked in docs/executorch_summary.md Section 6 at the
   time this is actually run, rather than trusting this comment to still be
   current.

This script follows the 4-step flow from the Phase 8 brief, which matches
the 7-stage flow already documented in docs/executorch_summary.md Section 2:

    PyTorch model -> 4-bit groupwise PTQ -> torch.export capture ->
    Edge dialect (EXIR) -> XNNPACK partition/delegate -> serialized .pte

It uses the documented **community tooling path** (`optimum-cli export
executorch`) as the primary route, because docs/executorch_summary.md
Section 2 already identifies that as the practical path, rather than
hand-rolling the lower-level `torch.export`/EXIR calls -- reimplementing
what `optimum-cli` already does correctly would be a second source of bugs
with no offsetting benefit. A lower-level fallback using the ExecuTorch
Python API directly is included for the case where the CLI tool does not
support this exact quantization recipe at the time this is run; it is
marked clearly as unverified reference code.

Usage (on a properly set-up machine, not in this sandbox)::

    python -m deploy.export_llama_pte --output-dir models/llama
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

MODEL_ID = "meta-llama/Llama-3.2-1B-Instruct"
# 8da4w: 8-bit dynamic activations, 4-bit groupwise weights. This is the
# recipe named in docs/executorch_summary.md Section 2/3 as the community
# reference. The group size below is a starting point, not a measured
# choice -- docs/executorch_summary.md Section 3 says smaller groups keep
# more accuracy but store more scale values, and no group size has been
# selected or measured by this project yet. Record whichever value is
# actually used as a new ADR, per that document's own instruction.
QUANTIZATION_RECIPE = "8da4w"
GROUP_SIZE = 128
TARGET_PTE_NAME = "llama3_2_1b_4bit.pte"
TOKENIZER_NAME = "tokenizer.bin"

# Budgets from docs/executorch_summary.md Section 4 / ADR-0009, repeated
# here only so this script can warn if the output clearly violates them --
# it does not replace the on-device memory measurement WP8 must still do.
PLANNED_MODEL_SIZE_MB = 750
CAUTIOUS_MODEL_SIZE_MB = 1024  # public SpinQuant 4-bit export, ~1.0 GiB
PEAK_MEMORY_TARGET_MB = 1100


def check_prerequisites() -> None:
    missing = []
    for module in ("torch", "executorch", "torchao"):
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    if missing:
        raise SystemExit(
            f"Missing required packages: {missing}. Install them first "
            "(see this file's module docstring for the exact commands and "
            "the HF gated-access steps that must happen before that)."
        )
    if shutil.which("optimum-cli") is None:
        raise SystemExit(
            "'optimum-cli' not found on PATH. Install with "
            "`pip install optimum[executorch]` (see module docstring)."
        )
    import os

    if not os.environ.get("HF_TOKEN"):
        raise SystemExit(
            "HF_TOKEN is not set. Llama 3.2 1B Instruct is a gated model -- "
            "accept the licence on huggingface.co and set HF_TOKEN before "
            "running this script (see module docstring, step 1-2)."
        )


def export_with_optimum_cli(output_dir: Path) -> Path:
    """Primary path: the documented community tool.

    This is the command form described in docs/executorch_summary.md
    Section 2 ("optimum-cli export executorch with the xnnpack recipe and
    TorchAO quantization options such as 8da4w"). Flag names must be
    re-checked against the installed optimum/executorch version before
    relying on this -- CLI flags for quantization recipes have changed
    across ExecuTorch releases and this project has never run this command.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "optimum-cli",
        "export",
        "executorch",
        "--model",
        MODEL_ID,
        "--recipe",
        "xnnpack",
        "--qlinear",
        QUANTIZATION_RECIPE,
        "--group_size",
        str(GROUP_SIZE),
        "--output_dir",
        str(output_dir),
    ]
    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout, file=sys.stdout)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(
            "optimum-cli export failed. This is expected to need iteration "
            "the first time it is actually run -- check the flag names "
            "above against `optimum-cli export executorch --help` for the "
            "installed version before assuming this script's flags are "
            "correct."
        )
    produced = list(output_dir.glob("*.pte"))
    if not produced:
        raise RuntimeError(
            f"optimum-cli reported success but no .pte file was found in "
            f"{output_dir}. Inspect its output above."
        )
    return produced[0]


def export_with_executorch_api_fallback(output_dir: Path) -> Path:
    """Lower-level fallback, following the 7-stage flow by hand.

    Unverified reference code -- use only if export_with_optimum_cli fails
    for a reason that looks like a CLI limitation rather than a real export
    error. Mirrors docs/executorch_summary.md Section 2's stage list
    directly so a reader can match each line to that table.
    """
    import torch
    from executorch.exir import to_edge
    from torch.export import export as torch_export
    from transformers import AutoModelForCausalLM, AutoTokenizer

    print("Stage 1/7: loading Llama 3.2 1B Instruct weights ...")
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, torch_dtype=torch.float32)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model.eval()

    print(
        f"Stage 2/7: applying 4-bit groupwise PTQ "
        f"(recipe={QUANTIZATION_RECIPE}, group_size={GROUP_SIZE}) ..."
    )
    from torchao.quantization import quantize_

    # NOTE: the exact torchao API for groupwise 4-bit weight + 8-bit dynamic
    # activation quantization has changed between torchao releases. Check
    # the current torchao docs for the function name/signature at the time
    # this is actually run -- this call is illustrative of the intent
    # (quantize linear layers; leave norm layers higher precision, per
    # docs/executorch_summary.md Section 3), not a verified working call.
    quantize_(model, QUANTIZATION_RECIPE, group_size=GROUP_SIZE)

    print("Stage 3/7: torch.export capture (TorchDynamo tracing) ...")
    example_input = tokenizer("Hello", return_tensors="pt")["input_ids"]
    exported_program = torch_export(model, (example_input,))

    print("Stage 4/7: lowering to Edge dialect (EXIR) ...")
    edge_program = to_edge(exported_program)

    print("Stage 5/7: partitioning to the XNNPACK delegate ...")
    from executorch.backends.xnnpack.partition.xnnpack_partitioner import (
        XnnpackPartitioner,
    )

    edge_program = edge_program.to_backend(XnnpackPartitioner())

    print("Stage 6/7: serializing to .pte ...")
    output_dir.mkdir(parents=True, exist_ok=True)
    pte_path = output_dir / TARGET_PTE_NAME
    executorch_program = edge_program.to_executorch()
    with open(pte_path, "wb") as fh:
        fh.write(executorch_program.buffer)

    print("Stage 7/7: packaging tokenizer ...")
    _package_tokenizer(tokenizer, output_dir)

    return pte_path


def _package_tokenizer(tokenizer, output_dir: Path) -> Path:
    """Save the tokenizer in whatever form the chosen ExecuTorch runtime
    build expects. The exact expected filename/format (a raw sentencepiece
    model, a custom tokenizer.bin produced by an ExecuTorch conversion
    tool, or a HF tokenizer.json) depends on the runtime harness built in
    deploy/android_guide.md and has not been pinned down by this project
    yet -- this writes the HF tokenizer files and ALSO a copy named
    tokenizer.bin as a placeholder, and must be reconciled with whatever
    the actual Android/JNI harness loads before being trusted.
    """
    tok_dir = output_dir / "tokenizer_hf"
    tokenizer.save_pretrained(tok_dir)
    placeholder = output_dir / TOKENIZER_NAME
    # Placeholder copy -- replace with the real conversion step the chosen
    # ExecuTorch runtime build expects once that is decided (new ADR).
    candidate_files = list(tok_dir.glob("*.model")) or list(tok_dir.glob("*.json"))
    if candidate_files:
        shutil.copy(candidate_files[0], placeholder)
    return placeholder


def _check_budget(pte_path: Path) -> None:
    size_mb = pte_path.stat().st_size / 1_000_000
    print(f"\n.pte file size: {size_mb:.1f} MB")
    if size_mb <= PLANNED_MODEL_SIZE_MB:
        print(f"  Within the optimistic {PLANNED_MODEL_SIZE_MB} MB plan.")
    elif size_mb <= CAUTIOUS_MODEL_SIZE_MB:
        print(
            f"  Above the optimistic {PLANNED_MODEL_SIZE_MB} MB plan but within "
            f"the cautious {CAUTIOUS_MODEL_SIZE_MB} MB case already budgeted "
            "in docs/executorch_summary.md Section 4."
        )
    else:
        print(
            f"  EXCEEDS the cautious {CAUTIOUS_MODEL_SIZE_MB} MB case. The "
            f"peak-memory budget of ~{PEAK_MEMORY_TARGET_MB} MB total "
            "(docs/executorch_summary.md Section 4) is very unlikely to be "
            "met -- this is a real blocker to record as a new ADR before "
            "proceeding to on-device testing, not a number to proceed past "
            "quietly.",
            file=sys.stderr,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("models/llama"))
    parser.add_argument(
        "--use-api-fallback",
        action="store_true",
        help="Use the lower-level ExecuTorch API path instead of optimum-cli.",
    )
    args = parser.parse_args(argv)

    check_prerequisites()

    if args.use_api_fallback:
        pte_path = export_with_executorch_api_fallback(args.output_dir)
    else:
        try:
            pte_path = export_with_optimum_cli(args.output_dir)
        except RuntimeError as exc:
            print(f"\noptimum-cli path failed: {exc}", file=sys.stderr)
            print("Falling back to the lower-level ExecuTorch API path ...")
            pte_path = export_with_executorch_api_fallback(args.output_dir)

    _check_budget(pte_path)
    print(
        f"\nExported: {pte_path}\n"
        "This has not been loaded or run by an ExecuTorch runtime, on a "
        "device or otherwise, as part of producing this script. Validate "
        "it loads correctly before relying on it -- see "
        "deploy/android_guide.md."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
