import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from phase1_writers_room.graph.state import initial_state
from phase1_writers_room.graph.workflow import build_graph


def _prompt_for_story() -> str:
    """Ask the user for a story idea when no --prompt/--script was given."""
    print("\nEnter your story idea, then press Enter.\n")
    while True:
        try:
            line = input("Story idea: ").strip()
        except EOFError:
            print("\nAborted.", file=sys.stderr)
            sys.exit(1)
        if line:
            return line
        print("Please type a non-empty idea, or press Ctrl+C to exit.\n")


def run(
    prompt: str | None = None,
    script_path: str | None = None,
    *,
    print_header: bool = True,
):
    # ── Build state ───────────────────────────────────────────────────────────
    if script_path:
        with open(script_path, "r") as f:
            raw_script = f.read()
        state = initial_state(script=raw_script)
    else:
        state = initial_state(prompt=prompt)

    # ── Build and invoke graph ────────────────────────────────────────────────
    if print_header:
        print("=" * 50)
        print("PROJECT MONTAGE — Phase 1: The Writer's Room")
        print("=" * 50)

    graph = build_graph()
    final_state = graph.invoke(state)

    # ── Print final state summary ─────────────────────────────────────────────
    print("\n── Final State ──")
    print(f"  status       : {final_state['status']}")
    print(f"  input_mode   : {final_state['input_mode']}")
    print(f"  hitl_approved: {final_state['hitl_approved']}")
    print(f"  scenes       : {len(final_state['script']['scenes']) if final_state['script'] else 0}")
    print(f"  characters   : {len(final_state['characters'])}")
    print(f"  images       : {len(final_state['images'])}")
    if final_state.get("error"):
        print(f"  error        : {final_state['error']}")

    return final_state


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="PROJECT MONTAGE Phase 1 — Writer's Room",
        epilog=(
            "Run with no arguments to be prompted for your story idea. "
            "Or use --prompt / --script as before."
        ),
    )
    parser.add_argument(
        "-p",
        "--prompt",
        type=str,
        default=None,
        metavar="TEXT",
        help="Story idea for auto mode (skip interactive prompt)",
    )
    parser.add_argument(
        "-s",
        "--script",
        type=str,
        default=None,
        metavar="PATH",
        help="Path to a manual screenplay text file",
    )
    args = parser.parse_args()

    if args.prompt is not None and args.script is not None:
        parser.error("Use either --prompt or --script, not both.")

    if args.script is not None:
        run(script_path=args.script)
    elif args.prompt is not None:
        run(prompt=args.prompt)
    else:
        print("=" * 50)
        print("PROJECT MONTAGE — Phase 1: The Writer's Room")
        print("=" * 50)
        run(prompt=_prompt_for_story(), print_header=False)
