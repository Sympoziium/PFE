import os
import json

BASE = "c:/Users/Ced/Documents/ETS/S10-H-2026/GPA_793/PFE/MLP_model_trainer/sequences"
DIRS = [
    os.path.join(BASE, "sortie de route"),
    os.path.join(BASE, "sortie de route 2"),
]

ZERO_THRESH = 0.02  # below this absolute value = "zero/null"
FORWARD_LEAD_MIN = 40  # minimum forward frames for GOOD classification


def classify_label(left, right):
    """Classify a single label pair."""
    l_abs, r_abs = abs(left), abs(right)
    if l_abs < ZERO_THRESH and r_abs < ZERO_THRESH:
        return "ZERO"
    if left < -ZERO_THRESH and right < -ZERO_THRESH:
        return "REVERSE"
    if left > ZERO_THRESH and right > ZERO_THRESH:
        return "FORWARD"
    if left > ZERO_THRESH and r_abs < ZERO_THRESH:
        return "TURN_L"
    if right > ZERO_THRESH and l_abs < ZERO_THRESH:
        return "TURN_R"
    if left > ZERO_THRESH and right < -ZERO_THRESH:
        return "SPIN_L"
    if right > ZERO_THRESH and left < -ZERO_THRESH:
        return "SPIN_R"
    if left < -ZERO_THRESH and r_abs < ZERO_THRESH:
        return "REV_TURN_L"
    if right < -ZERO_THRESH and l_abs < ZERO_THRESH:
        return "REV_TURN_R"
    return "OTHER"


def summarize_phases(labels, n=50):
    """Summarize first n labels into phases."""
    phases = []
    current_phase = None
    count = 0
    for i, (left, right) in enumerate(labels[:n]):
        cls = classify_label(left, right)
        if cls == current_phase:
            count += 1
        else:
            if current_phase is not None:
                phases.append((current_phase, count))
            current_phase = cls
            count = 1
    if current_phase is not None:
        phases.append((current_phase, count))
    return phases


def classify_sequence(labels):
    """Classify entire sequence as GOOD or BAD."""
    if len(labels) == 0:
        return "BAD", "Empty sequence"

    n_analyze = min(60, len(labels))
    classes = [classify_label(l, r) for l, r in labels[:n_analyze]]

    # Find first non-zero index
    first_nonzero = None
    for i, cls in enumerate(classes):
        if cls != "ZERO":
            first_nonzero = i
            break

    if first_nonzero is None:
        return "BAD", "All zeros in first %d frames" % n_analyze

    # Find first forward-driving index
    first_forward = None
    for i, cls in enumerate(classes):
        if cls in ("FORWARD", "TURN_L", "TURN_R"):
            first_forward = i
            break

    # Find first reverse/correction index
    first_reverse = None
    for i, cls in enumerate(classes):
        if cls in ("REVERSE", "REV_TURN_L", "REV_TURN_R", "SPIN_L", "SPIN_R"):
            first_reverse = i
            break

    # Classification logic
    if first_forward is None:
        if first_reverse is not None:
            return "BAD", "No forward driving; reverse at frame %d" % first_reverse
        return "BAD", "No forward driving found"

    if first_reverse is None:
        return "GOOD", "Forward driving, no reverse in first %d frames" % n_analyze

    if first_forward > first_reverse:
        return "BAD", "Reverse at frame %d before first forward at frame %d" % (first_reverse, first_forward)

    # Forward comes before reverse - count forward frames before first reverse
    forward_frames_before_reverse = 0
    for i in range(first_reverse):
        if classes[i] in ("FORWARD", "TURN_L", "TURN_R"):
            forward_frames_before_reverse += 1

    if forward_frames_before_reverse >= FORWARD_LEAD_MIN:
        return "GOOD", "%d forward frames before reverse at frame %d" % (forward_frames_before_reverse, first_reverse)
    elif forward_frames_before_reverse >= 10:
        return "AMBIGUOUS", "Only %d forward frames before reverse at frame %d (need %d)" % (
            forward_frames_before_reverse, first_reverse, FORWARD_LEAD_MIN)
    else:
        return "BAD", "Only %d forward frames before reverse at frame %d" % (
            forward_frames_before_reverse, first_reverse)


def format_phases(phases):
    """Format phases into a compact string."""
    parts = []
    for cls, count in phases:
        parts.append("%dx%s" % (count, cls))
    return " -> ".join(parts)


# Collect results
results = []

for parent_dir in DIRS:
    dir_label = os.path.basename(parent_dir)
    if not os.path.isdir(parent_dir):
        print("WARNING: %s not found" % parent_dir)
        continue

    subdirs = sorted(os.listdir(parent_dir))
    for subdir in subdirs:
        subdir_path = os.path.join(parent_dir, subdir)
        labels_path = os.path.join(subdir_path, "labels.jsonl")

        if not os.path.isfile(labels_path):
            continue

        # Read labels
        labels = []
        with open(labels_path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        pair = json.loads(line)
                        labels.append(pair)
                    except Exception:
                        pass

        total = len(labels)
        phases = summarize_phases(labels, n=50)
        classification, reason = classify_sequence(labels)
        phase_str = format_phases(phases)

        results.append({
            "parent": dir_label,
            "subdir": subdir,
            "total": total,
            "classification": classification,
            "reason": reason,
            "phases": phase_str,
            "first5": labels[:5] if labels else [],
        })

# Print results grouped by parent directory and classification
print("=" * 170)
print("SEQUENCE ANALYSIS REPORT")
print("=" * 170)

for parent_dir_name in ["sortie de route", "sortie de route 2"]:
    parent_results = [r for r in results if r["parent"] == parent_dir_name]

    print()
    print("=" * 170)
    print("DIRECTORY: %s (%d sequences)" % (parent_dir_name, len(parent_results)))
    print("=" * 170)

    for classification in ["BAD", "AMBIGUOUS", "GOOD"]:
        filtered = [r for r in parent_results if r["classification"] == classification]
        if not filtered:
            continue

        print()
        print("--- %s (%d sequences) ---" % (classification, len(filtered)))
        print("%-35s %6s  %-65s  %s" % ("Subdirectory", "Total", "Reason", "First 50 pattern"))
        print("%-35s %6s  %-65s  %s" % ("-" * 35, "-" * 6, "-" * 65, "-" * 60))

        for r in filtered:
            print("%-35s %6d  %-65s  %s" % (r["subdir"], r["total"], r["reason"], r["phases"]))

# Summary
print()
print("=" * 170)
print("SUMMARY")
print("=" * 170)

for parent_dir_name in ["sortie de route", "sortie de route 2"]:
    parent_results = [r for r in results if r["parent"] == parent_dir_name]
    bad = [r for r in parent_results if r["classification"] == "BAD"]
    ambig = [r for r in parent_results if r["classification"] == "AMBIGUOUS"]
    good = [r for r in parent_results if r["classification"] == "GOOD"]
    print()
    print("%s:" % parent_dir_name)
    print("  GOOD:      %3d sequences" % len(good))
    print("  AMBIGUOUS: %3d sequences" % len(ambig))
    print("  BAD:       %3d sequences" % len(bad))
    print("  TOTAL:     %3d sequences" % len(parent_results))

    if bad:
        print("  BAD subdirs: %s" % ", ".join(r["subdir"] for r in bad))
    if ambig:
        print("  AMBIGUOUS subdirs: %s" % ", ".join(r["subdir"] for r in ambig))

# Grand total
all_bad = [r for r in results if r["classification"] == "BAD"]
all_ambig = [r for r in results if r["classification"] == "AMBIGUOUS"]
all_good = [r for r in results if r["classification"] == "GOOD"]
print()
print("GRAND TOTAL: %d sequences" % len(results))
print("  GOOD:      %d" % len(all_good))
print("  AMBIGUOUS: %d" % len(all_ambig))
print("  BAD:       %d" % len(all_bad))
