"""Cenários adicionais do contrato descrito no README."""

import csv
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pytest

from helpers import PROJECT_ROOT, run_cli


def invoke(*args, cwd=PROJECT_ROOT):
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(
        [sys.executable, "-m", "onfly_report", *map(str, args)],
        cwd=cwd, env=env, capture_output=True, text=True, timeout=60,
    )


def money(value):
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def test_readme_sample(tmp_path):
    output = tmp_path / "nested" / "sample.json"
    process = invoke("--input", PROJECT_ROOT / "data/exemplo-validacao.csv",
                     "--rates", PROJECT_ROOT / "data/taxas_cambio.csv", "--output", output)
    assert process.returncode == 0, process.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["summary"] == {
        "total_reservations": 12, "confirmed_reservations": 9,
        "cancelled_reservations": 2, "no_show_reservations": 1,
        "total_room_nights": 28, "total_amount_brl": "7566.00",
        "average_nightly_rate_brl": "270.21",
    }
    assert report["by_month"] == [
        {"month": "2025-01", "reservations": 8, "room_nights": 25, "total_brl": "6684.00"},
        {"month": "2025-02", "reservations": 1, "room_nights": 3, "total_brl": "882.00"},
    ]
    assert report["top_hotels"] == [
        {"hotel_id": hid, "hotel_name": name, "room_nights": nights, "total_brl": amount}
        for hid, name, nights, amount in [
            ("H01", "Hotel Aurora Paulista", 3, "1200.00"),
            ("H02", "Hotel Mirante", 2, "1084.00"),
            ("H12", "Hotel Miami Beach", 1, "1000.00"),
            ("H10", "Hotel Madrid, Gran Vía", 4, "900.00"),
            ("H09", "Hotel Lisboa, Centro", 3, "882.00"),
        ]
    ]


def test_full_dataset_against_independent_aggregation(tmp_path):
    with (PROJECT_ROOT / "data/reservas_hoteis.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    with (PROJECT_ROOT / "data/taxas_cambio.csv").open(encoding="utf-8", newline="") as handle:
        rates = {r["currency"]: Decimal(r["rate_to_brl"]) for r in csv.DictReader(handle)}
    counts = Counter(r["status"] for r in rows)
    monthly = defaultdict(list)
    hotels = defaultdict(list)
    for row in rows:
        if row["status"] == "CONFIRMED":
            monthly[row["checkin_date"][:7]].append(row)
            hotels[row["hotel_id"]].append(row)

    def aggregate(group):
        nights = sum((date.fromisoformat(r["checkout_date"]) - date.fromisoformat(r["checkin_date"])).days
                     * int(r["rooms"]) for r in group)
        amount = sum((Decimal(r["amount"]) * rates[r["currency"]] for r in group), Decimal(0))
        return nights, amount

    confirmed = [r for r in rows if r["status"] == "CONFIRMED"]
    nights, amount = aggregate(confirmed)
    output = tmp_path / "full.json"
    process = invoke("--input", PROJECT_ROOT / "data/reservas_hoteis.csv",
                     "--rates", PROJECT_ROOT / "data/taxas_cambio.csv", "--output", output, "--top", 999)
    assert process.returncode == 0, process.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert len(rows) == 300
    assert report["summary"] == {
        "total_reservations": len(rows), "confirmed_reservations": counts["CONFIRMED"],
        "cancelled_reservations": counts["CANCELLED"], "no_show_reservations": counts["NO_SHOW"],
        "total_room_nights": nights, "total_amount_brl": money(amount),
        "average_nightly_rate_brl": money(amount / nights) if nights else "0.00",
    }
    assert report["by_month"] == [
        {"month": month, "reservations": len(group), "room_nights": aggregate(group)[0],
         "total_brl": money(aggregate(group)[1])}
        for month, group in sorted(monthly.items())
    ]
    assert report["top_hotels"] == [
        {"hotel_id": hid, "hotel_name": group[-1]["hotel_name"], "room_nights": aggregate(group)[0],
         "total_brl": money(aggregate(group)[1])}
        for hid, group in sorted(hotels.items(), key=lambda item: (-aggregate(item[1])[1], item[0]))
    ]


def test_tie_break_and_top_limit(tmp_path):
    report = run_cli(tmp_path, [
        {"hotel_id": "H03", "amount": "100"}, {"hotel_id": "H02", "amount": "200"},
        {"hotel_id": "H01", "amount": "100"},
    ], top=2)
    assert [r["hotel_id"] for r in report["top_hotels"]] == ["H02", "H01"]


def test_round_only_after_aggregation_and_half_up(tmp_path):
    report = run_cli(tmp_path, [{"amount": "0.005"}, {"amount": "0.005"}])
    assert report["summary"]["total_amount_brl"] == "0.01"
    assert report["summary"]["average_nightly_rate_brl"] == "0.01"
    assert report["by_month"][0]["total_brl"] == "0.01"
    assert report["top_hotels"][0]["total_brl"] == "0.01"


def test_year_boundary_rooms_and_checkin_month(tmp_path):
    report = run_cli(tmp_path, [
        {"checkin_date": "2025-12-30", "checkout_date": "2026-01-02", "rooms": "2"},
        {"checkin_date": "2025-01-01", "checkout_date": "2025-01-02"},
    ])
    assert report["summary"]["total_room_nights"] == 7
    assert [r["month"] for r in report["by_month"]] == ["2025-01", "2025-12"]
    assert report["by_month"][1]["room_nights"] == 6


@pytest.mark.parametrize("rows", [[], [{"status": "CANCELLED"}, {"status": "NO_SHOW"}]])
def test_no_billable_reservations(tmp_path, rows):
    report = run_cli(tmp_path, rows)
    assert report["summary"]["total_reservations"] == len(rows)
    assert report["summary"]["total_room_nights"] == 0
    assert report["summary"]["total_amount_brl"] == "0.00"
    assert report["summary"]["average_nightly_rate_brl"] == "0.00"
    assert report["by_month"] == report["top_hotels"] == []


def test_schema_money_and_timezone(tmp_path):
    report = run_cli(tmp_path, [{}])
    assert set(report) == {"report_version", "generated_at", "summary", "by_month", "top_hotels"}
    assert report["report_version"] == "1.0"
    assert report["generated_at"].endswith("-03:00")
    assert set(report["summary"]) == {
        "total_reservations", "confirmed_reservations", "cancelled_reservations", "no_show_reservations",
        "total_room_nights", "total_amount_brl", "average_nightly_rate_brl",
    }
    for key, value in report["summary"].items():
        if key.endswith("brl"):
            assert isinstance(value, str) and re.fullmatch(r"-?\d+\.\d{2}", value)
        else:
            assert type(value) is int


@pytest.mark.parametrize("args", [[], ["--top", "0"], ["--top", "-1"], ["--top", "abc"]])
def test_invalid_arguments(args):
    process = invoke("--input", PROJECT_ROOT / "data/exemplo-validacao.csv",
                     "--rates", PROJECT_ROOT / "data/taxas_cambio.csv", *args) if args else invoke()
    assert process.returncode == 2


@pytest.mark.parametrize("kind", ["missing", "columns", "date", "rate"])
def test_invalid_input_exit_code(tmp_path, kind):
    run_cli(tmp_path, [{}])
    source = tmp_path / "reservas.csv"
    rates = tmp_path / "rates.csv"
    if kind == "missing":
        source = tmp_path / "missing.csv"
    elif kind == "columns":
        source.write_text("wrong\nvalue\n", encoding="utf-8")
    elif kind == "date":
        source.write_text(source.read_text(encoding="utf-8").replace("2025-01-10", "invalid"), encoding="utf-8")
    else:
        rates.write_text("currency,rate_to_brl\nBRL,invalid\n", encoding="utf-8")
    assert invoke("--input", source, "--rates", rates, "--output", tmp_path / "invalid.json").returncode == 2


def test_default_output_and_stdout(tmp_path):
    process = invoke("--input", PROJECT_ROOT / "data/exemplo-validacao.csv",
                     "--rates", PROJECT_ROOT / "data/taxas_cambio.csv", cwd=tmp_path)
    assert process.returncode == 0, process.stderr
    report = json.loads((tmp_path / "output/report.json").read_text(encoding="utf-8"))
    assert len(report["top_hotels"]) == 5
    assert "Reservas: 12" in process.stdout
    assert "7566.00" in process.stdout


def test_output_failure_exit_code(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("block directory creation", encoding="utf-8")
    process = invoke("--input", PROJECT_ROOT / "data/exemplo-validacao.csv",
                     "--rates", PROJECT_ROOT / "data/taxas_cambio.csv", "--output", blocker / "report.json")
    assert process.returncode == 1
