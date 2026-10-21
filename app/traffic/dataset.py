
import csv
from pathlib import Path
from datetime import datetime, timezone

PROJECT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_DIR / "data"
DATASET_FILE = DATA_DIR / "traffic_video_analysis.csv"

FIELDS = [
    "timestamp",
    "video_id",
    "route_id",
    "elapsed_seconds",
    "total_vehicles",
    "moving_vehicles",
    "stopped_vehicles",
    "average_speed_kmh",
    "traffic_level",
    "accident_detected",
    "distance_km",
    "estimated_travel_time_min",
    "data_source"
]


def save_traffic_record(record):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    total = int(record.get("total_vehicles", 0))
    moving = int(record.get("moving_vehicles", 0))
    stopped = int(record.get("stopped_vehicles", 0))

    if min(total, moving, stopped) < 0:
        raise ValueError("Vehicle counts cannot be negative.")

    if moving + stopped > total:
        raise ValueError(
            "Moving and stopped counts cannot exceed total vehicles."
        )

    traffic_level = record.get("traffic_level", "UNKNOWN").upper()

    if traffic_level not in {"LOW", "MEDIUM", "HIGH", "UNKNOWN"}:
        raise ValueError("Invalid traffic level.")

    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "video_id": record.get("video_id", ""),
        "route_id": record.get("route_id", ""),
        "elapsed_seconds": record.get("elapsed_seconds", ""),
        "total_vehicles": total,
        "moving_vehicles": moving,
        "stopped_vehicles": stopped,
        "average_speed_kmh": record.get("average_speed_kmh", ""),
        "traffic_level": traffic_level,
        "accident_detected": record.get("accident_detected", "unknown"),
        "distance_km": record.get("distance_km", ""),
        "estimated_travel_time_min": record.get(
            "estimated_travel_time_min", ""
        ),
        "data_source": record.get("data_source", "video_analysis")
    }

    file_exists = DATASET_FILE.exists()

    with DATASET_FILE.open(
        "a",
        newline="",
        encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)

        if not file_exists or DATASET_FILE.stat().st_size == 0:
            writer.writeheader()

        writer.writerow(row)

    return {
        "saved": True,
        "file": str(DATASET_FILE),
        "traffic_level": traffic_level,
        "total_vehicles": total
    }


if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not DATASET_FILE.exists():
        with DATASET_FILE.open(
            "w",
            newline="",
            encoding="utf-8"
        ) as file:
            csv.DictWriter(file, fieldnames=FIELDS).writeheader()

    print("Dataset file is ready.")
    print(DATASET_FILE)
