"""Command-line export used by the support team. Mirrors src/export.js."""
import csv
import io
import json


def export_notes(notes, flagsmith):
    if flagsmith.is_feature_enabled("legacy_export"):
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["id", "text"])
        for note in notes:
            writer.writerow([note["id"], note["text"]])
        return out.getvalue()
    return json.dumps(notes)