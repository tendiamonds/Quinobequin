"""
Read a batch of reports sent from a Reports page (reports.py): paste the email into a
text file, and this lists them, blazes first, by trail and sign-to-sign stretch, each
against what the map has there.

  python read_reports.py EMAIL.txt ...
"""

import collections
import json
import sys

MARK = "--- data (for the map's tools) ---"


def read(path):
    text = open(path, encoding="utf-8").read()
    if MARK not in text:
        raise SystemExit("%s: no data block (the line '%s')" % (path, MARK))
    # The data is one line of JSON. A mail app may wrap it (keeping the space at each break),
    # so join the lines back up; anything after it (a signature) is ignored
    data = "".join(text.split(MARK, 1)[1].strip().splitlines())
    return json.JSONDecoder().raw_decode(data)[0]


def where(r):
    at = r.get("at")
    return "%.6f, %.6f (+/- %s m)" % (at["lat"], at["lon"], at["acc"]) if at else "no location"


def main(paths):
    reports = [r for p in paths for r in read(p)]
    seen = set()
    reports = [r for r in reports if not (r["id"] in seen or seen.add(r["id"]))]
    print("%d reports" % len(reports))

    blazes = [r for r in reports if r["kind"] == "blaze"]
    by_stretch = collections.defaultdict(list)
    for r in blazes:
        x = r.get("ctx") or {}
        key = (x.get("trail") or "(off trail, near %s)" % x.get("near", "?"), x.get("stretch") or "")
        by_stretch[key].append(r)
    if blazes:
        print("\nBlazes (%d), by stretch:" % len(blazes))
        for (trail, stretch), rs in sorted(by_stretch.items()):
            expect = sorted(set(k for r in rs for k in ((r.get("ctx") or {}).get("expect") or [])))
            # Another color: what was typed for it
            saw = collections.Counter((r.get("text") or "other") if r["blaze"] == "other" else r["blaze"] for r in rs)
            agree = set(saw) - {"none"} <= set(expect) and (bool(expect) or set(saw) <= {"none"})
            print("  %-26s %-10s map: %-16s seen: %s%s" % (trail, stretch, ", ".join(expect) or "none",
                  ", ".join("%s x%d" % kv for kv in saw.most_common()), "" if agree else "   <-- differs"))
            for r in rs:
                if r.get("text") and r["blaze"] != "other":
                    print("      note (%s): %s" % (r["blaze"], r["text"]))

    for kind, title in (("check", "Checks"), ("sign", "Standing at a sign"), ("note", "Notes")):
        rs = [r for r in reports if r["kind"] == kind]
        if rs:
            print("\n%s (%d):" % (title, len(rs)))
            for r in rs:
                about = (r.get("about") or {}).get("ref", "")
                print("  %s  %s%s  at %s%s" % (r["when"][:16].replace("T", " "), about + ": " if about else "",
                      r.get("answer") or "", where(r), ("\n      " + r["text"]) if r.get("text") else ""))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")   # stretches are "C29–C26"
    main(sys.argv[1:])
