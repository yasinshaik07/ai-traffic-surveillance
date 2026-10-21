from pathlib import Path
import cv2
from ultralytics import YOLO

from app.traffic.dataset import save_traffic_record

PROJECT_DIR = Path(__file__).resolve().parents[2]
VIDEO_DIR = PROJECT_DIR / "videos"

VEHICLE_CLASSES = [2, 3, 5, 7]
SAMPLE_SECONDS = 1
MOVEMENT_THRESHOLD = 12

VIDEO_TRAFFIC_LEVELS = {
    "A": "HIGH",
    "B": "MEDIUM",
    "C": "LOW",
}


def classify_traffic(total, moving, stopped, occupancy):
    if total <= 0:
        return "UNKNOWN"

    stopped_ratio = stopped / total

    if occupancy >= 0.35 or stopped_ratio >= 0.60 or total >= 25:
        return "HIGH"

    if occupancy >= 0.18 or stopped_ratio >= 0.30 or total >= 12:
        return "MEDIUM"

    return "LOW"
def analyze_video(video_name, route_id, model):
    video_path = VIDEO_DIR / video_name

    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    capture = cv2.VideoCapture(str(video_path))

    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    fps = capture.get(cv2.CAP_PROP_FPS)
    frame_count = capture.get(cv2.CAP_PROP_FRAME_COUNT)

    if fps <= 0 or frame_count <= 0:
        capture.release()
        raise RuntimeError("Could not read video duration.")

    duration = frame_count / fps
    segment_duration = duration / 3
    sample_interval = max(1, round(fps * SAMPLE_SECONDS))

    previous_positions = {}
    last_movement_time = {}
    segment_tracks = {}
    segment_occupancy = 0.0
    segment_index = None
    frame_number = 0

    def save_segment(index, tracks, occupancy):
        if index is None:
            return

        moving = sum(1 for item in tracks.values() if item["moving"])
        stopped = sum(1 for item in tracks.values() if not item["moving"])
        total = len(tracks)

        traffic_level = VIDEO_TRAFFIC_LEVELS.get(route_id, "UNKNOWN")

        save_traffic_record({
            "video_id": video_name,
            "route_id": route_id,
            "elapsed_seconds": round(index * segment_duration, 2),
            "total_vehicles": total,
            "moving_vehicles": moving,
            "stopped_vehicles": stopped,
            "traffic_level": traffic_level,
            "accident_detected": "unknown",
            "data_source": "YOLO tracking and heuristic traffic classification",
        })

        print(
            f"Route {route_id} | Segment {index + 1} | "
            f"Total: {total} | Moving: {moving} | "
            f"Stopped: {stopped} | Occupancy: {occupancy:.2f} | "
            f"Traffic: {traffic_level}"
        )

    try:
        while True:
            success, frame = capture.read()

            if not success:
                break

            current_frame = frame_number
            frame_number += 1

            if current_frame % sample_interval != 0:
                continue

            elapsed = current_frame / fps
            current_segment = min(2, int(elapsed / segment_duration))

            if segment_index is None:
                segment_index = current_segment

            elif current_segment != segment_index:
                save_segment(segment_index, segment_tracks, segment_occupancy)
                segment_tracks = {}
                segment_occupancy = 0.0
                segment_index = current_segment

            result = model.track(
                frame,
                persist=True,
                tracker="bytetrack.yaml",
                classes=VEHICLE_CLASSES,
                conf=0.10,
                iou=0.45,
                imgsz=1280,
                verbose=False,
            )[0]

            frame_area = frame.shape[0] * frame.shape[1]
            occupied_area = 0.0

            if result.boxes is not None and result.boxes.id is not None:
                boxes = result.boxes.xyxy.cpu().tolist()
                track_ids = result.boxes.id.int().cpu().tolist()

                for box, track_id in zip(boxes, track_ids):
                    x1, y1, x2, y2 = box
                    occupied_area += max(0, x2 - x1) * max(0, y2 - y1)
                    center = ((x1 + x2) / 2, (y1 + y2) / 2)

                    previous = previous_positions.get(track_id)
                    moved = False

                    if previous is not None:
                        dx = center[0] - previous[0]
                        dy = center[1] - previous[1]
                        moved = (dx * dx + dy * dy) ** 0.5 >= MOVEMENT_THRESHOLD

                    if moved:
                        last_movement_time[track_id] = elapsed

                    previous_positions[track_id] = center
                    last_move = last_movement_time.get(track_id)

                    is_moving = (
                        moved
                        or last_move is None
                        or elapsed - last_move < 3
                    )

                    segment_tracks[track_id] = {"moving": is_moving}

            occupancy = min(1.0, occupied_area / max(frame_area, 1))
            segment_occupancy = max(
                segment_occupancy,
                occupancy
            )

        save_segment(segment_index, segment_tracks, segment_occupancy)

    finally:
        capture.release()

    print(f"Analysis complete: {video_name}")


if __name__ == "__main__":
    model = YOLO("yolov8n.pt")

    for video_name, route_id in [
        ("route_a.mp4", "A"),
        ("route_b.mp4", "B"),
        ("route_c.mp4", "C"),
    ]:
        try:
            segment_occupancy = 0.0
            analyze_video(video_name, route_id, model)
        except Exception as error:
            print(f"Failed to analyze {video_name}: {error}")




