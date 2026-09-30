#!/usr/bin/env python3
"""Compare your hand labels in heldout/audit_sample.md with the by-construction truth. Stdlib only.

Fill each line in place, for example:
    Your answer: status CONFLICTING  value(s) 30, 90
    Your answer: status CONTEXTUAL  value(s) 500 new, 100 legacy
    Your answer: status INSUFFICIENT  value(s) none
Statuses: SUPPORTED SUPERSEDED CONTEXTUAL CONFLICTING INSUFFICIENT UNSUPPORTED.
Run only after ALL questions are labeled: until then it prints a count and reveals nothing.

Usage: python audit_check.py [path/to/audit_sample.md]
"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
ANSWER = re.compile(r"Your answer:\s*status\s*(.*?)\s*value\(s\)\s*(.*)$", re.M)
WITH_VALUES = ("supported", "superseded", "contextual", "conflicting")


def parse(path):
    sections = re.split(r"^## (h\d+):", pathlib.Path(path).read_text(encoding="utf-8"), flags=re.M)[1:]
    out = {}
    for qid, body in zip(sections[0::2], sections[1::2]):
        m = ANSWER.search(body)
        status = re.sub(r"[^A-Za-z_]", "", m.group(1)).strip("_").lower() if m else ""
        if status.startswith("unsupported"):
            status = "unsupported_case"
        out[qid] = (status, {int(v) for v in re.findall(r"\d+", m.group(2))} if m else set())
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else HERE / "heldout" / "audit_sample.md"
    labels = parse(path)
    blank = [q for q, (s, _) in labels.items() if not s]
    if blank:
        sys.exit(f"{len(blank)} of {len(labels)} questions are still unlabeled. Label them all first.")
    truth = {q["id"]: q for q in json.load(open(HERE / "heldout" / "expected_answers.json", encoding="utf-8"))["questions"]}

    bad, status_ok, values_ok, values_n = [], 0, 0, 0
    for qid, (status, values) in sorted(labels.items()):
        exp = truth[qid]["expected"]
        s_ok = status == exp["status"]
        status_ok += s_ok
        v_ok = True
        if exp["status"] in WITH_VALUES:
            values_n += 1
            v_ok = values == {a["value"] for a in exp["answers"]}
            values_ok += v_ok
        if not (s_ok and v_ok):
            bad.append((qid, status, sorted(values), truth[qid]["template"], exp["status"],
                        sorted({a["value"] for a in exp["answers"]})))
    print(f"labeled {len(labels)} questions")
    print(f"status agrees:  {status_ok}/{len(labels)}")
    print(f"values agree:   {values_ok}/{values_n} (only where the truth has values)")
    for qid, s, v, tpl, es, ev in bad:
        print(f"DISAGREE {qid} [{tpl}]: you said {s} {v}; construction says {es} {ev}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
