"""Write an evidence-scoped GitHub Actions summary from an existing JSON report."""
import argparse
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--title", required=True)
    args = parser.parse_args()
    result = json.loads(args.report.read_text())
    rows = [f"## {args.title}", "", "| Check | Recorded value |", "| --- | --- |"]
    for name in ("status", "frozen_files", "maintained_guides", "objects_checked",
                 "full_orbital_conditions", "current_policy_conditions", "current_policy_tasks",
                 "ledger_search_W", "new_molecular_experiments", "new_molecular_evaluations"):
        if name in result:
            rows.append(f"| {name.replace('_', ' ')} | {result[name]} |")
    rows += ["", "This job checks repository or saved-data consistency. It does not establish a new performance result.", ""]
    text = "\n".join(rows)
    destination = os.environ.get("GITHUB_STEP_SUMMARY")
    if destination:
        with Path(destination).open("a") as stream:
            stream.write(text)
    else:
        print(text)


if __name__ == "__main__":
    main()
