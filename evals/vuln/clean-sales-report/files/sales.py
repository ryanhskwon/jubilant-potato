import csv
import io


def total_by_region(csv_text):
    """Sum the amount column per region from a CSV export."""
    totals = {}
    for row in csv.DictReader(io.StringIO(csv_text)):
        totals[row["region"]] = totals.get(row["region"], 0) + float(row["amount"])
    return totals
