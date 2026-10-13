"""
The conservation restrictions (CRs) on land the Upper Charles Forest trails cross.

A CR doesn't change who owns the land: the owner keeps it, and the holders have the
right and duty to enforce the restriction. Signs on CR land carry the holders' logos.

Sources: the recorded CRs, the state's protected open space records (MassGIS), and The
Trustees' 2013 CR map. Which signs stand on CR land is in sign_logos.csv, worked out from
those and checked in the field; fix that file if a post turns out to be on the other
side of a CR line.
"""

import csv
import os

PROJ = os.path.dirname(os.path.abspath(__file__))

CRS = {
    "Adams Street Town Forest Additions CR": {
        "holders": ["The Trustees"],
        "land": "85.6 acres added to the Adams Street Town Forest in 2013 (the former NSTAR "
                "parcels, Holliston Map 4 Block 2); the original Town Forest isn't under a CR",
        "recorded": "Middlesex South Registry of Deeds, Book 62685, Page 340",
    },
    "Fairbanks CR": {
        "holders": ["The Trustees", "DCR"],
        "land": "the 210-acre David Reed Fairbanks conservation area (Holliston Map 1 Block 2 Lot 35)",
        "recorded": "Middlesex South Registry of Deeds, Book 40805, Page 64",
    },
}


def holders_text(cr):
    return " and ".join(CRS[cr]["holders"])


def sign_crs():
    """{sign label: CR name} for the signs on CR land (sign_logos.csv)"""
    out = {}
    with open(os.path.join(PROJ, "sign_logos.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            land = (row.get("CR land") or "").strip()
            if land:
                if land not in CRS:
                    raise ValueError("sign_logos.csv: %s is on %r, which isn't in crs.CRS" % (row["sign"], land))
                out[row["sign"]] = land
    return out


LOOK_FOR = ("small boundary signs on trees (The Trustees may post signs up to a foot square on "
            "the CR's edge), painted blazes or survey pins along the line, or a stone wall or old "
            "fence line that follows it. Stand at the post when you save, so the answer records "
            "where it is.")


def sign_checks():
    """Signs close to a CR line, to check in the field (sign_logos.csv check_on_ground), for
    checks.build_checks_page"""
    out = []
    with open(os.path.join(PROJ, "sign_logos.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("check_on_ground") != "yes":
                continue
            cr = row.get("near CR") or row.get("CR land")
            if cr not in CRS:
                raise ValueError("sign_logos.csv: %s is to be checked, but its CR (%r) isn't in crs.CRS" % (row["sign"], cr))
            out.append({"id": "cr-" + row["sign"], "label": row["sign"], "lat": float(row["lat"]), "lon": float(row["lon"]),
                        "question": "Is the post for %s on the %s land (held by %s)?" % (row["sign"], cr.replace(" CR", ""), holders_text(cr)),
                        "choices": ["On CR land", "Not on CR land", "Can't tell"],
                        "why": row["note"][0].upper() + row["note"][1:] + "." if row["note"] else "",
                        "look_for": LOOK_FOR})
    return out
