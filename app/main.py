import asyncio
import csv
import httpx

from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(
    title="AI Traffic Surveillance",
    description="AI Traffic Analysis and Best Route Recommendation System",
    version="1.0.0"
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

TRAFFIC_CSV = BASE_DIR / "data" / "traffic_video_analysis.csv"

VIDEO_LABELS = {
    "A": {"video": "route_a.mp4", "traffic": "HIGH"},
    "B": {"video": "route_b.mp4", "traffic": "MEDIUM"},
    "C": {"video": "route_c.mp4", "traffic": "LOW"},
}

TRAFFIC_PENALTY = {
    "LOW": 0,
    "MEDIUM": 600,
    "HIGH": 1500,
}


def load_video_traffic():
    latest = {}

    if not TRAFFIC_CSV.exists():
        return latest

    with TRAFFIC_CSV.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        for row in reader:
            route_id = row.get("route_id", "").strip().upper()

            if route_id not in VIDEO_LABELS:
                continue

            try:
                elapsed = float(row.get("elapsed_seconds") or 0)
            except (ValueError, TypeError):
                elapsed = 0

            try:
                total_vehicles = int(float(row.get("total_vehicles") or 0))
            except (ValueError, TypeError):
                total_vehicles = 0

            if (
                route_id not in latest
                or elapsed >= latest[route_id]["elapsed_seconds"]
            ):
                latest[route_id] = {
                    "elapsed_seconds": elapsed,
                    "video_id": row.get("video_id", ""),
                    "total_vehicles": total_vehicles,
                    "traffic_level": VIDEO_LABELS[route_id]["traffic"],
                }

    return latest



class RouteSearch(BaseModel):
    origin: str
    destination: str


@app.get("/api/health")
def health():
    return {"status": "running", "project": "AI Traffic Surveillance"}


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={}
    )


async def geocode(client, place):
    response = await client.get(
        "https://nominatim.openstreetmap.org/search",
        params={
            "q": place,
            "format": "jsonv2",
            "limit": 1
        },
        headers={
            "User-Agent": "AITrafficSurveillance/1.0 (educational project)"
        }
    )
    response.raise_for_status()
    results = response.json()

    if not results:
        return None

    return {
        "latitude": float(results[0]["lat"]),
        "longitude": float(results[0]["lon"]),
        "display_name": results[0]["display_name"]
    }


def format_distance(meters):
    return f"{meters / 1000:.1f} km"


def format_duration(seconds):
    minutes = round(seconds / 60)
    hours, remaining_minutes = divmod(minutes, 60)

    if hours:
        return f"{hours} hr {remaining_minutes} min"

    return f"{remaining_minutes} min"


@app.post("/api/routes/search")
async def search_routes(search: RouteSearch):
    origin = search.origin.strip()
    destination = search.destination.strip()

    if not origin or not destination:
        raise HTTPException(
            status_code=400,
            detail="Enter both starting location and destination."
        )

    if origin.casefold() == destination.casefold():
        raise HTTPException(
            status_code=400,
            detail="Starting location and destination must be different."
        )

    timeout = httpx.Timeout(20.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            start = await geocode(client, origin)

            if not start:
                raise HTTPException(
                    status_code=404,
                    detail=f"Starting location not found: {origin}"
                )

            await asyncio.sleep(1.1)

            end = await geocode(client, destination)

            if not end:
                raise HTTPException(
                    status_code=404,
                    detail=f"Destination not found: {destination}"
                )

            coordinates = (
                f"{start['longitude']},{start['latitude']};"
                f"{end['longitude']},{end['latitude']}"
            )

            response = await client.get(
                f"https://router.project-osrm.org/route/v1/driving/{coordinates}",
                params={
                    "alternatives": "3",
                    "overview": "full",
                    "geometries": "geojson",
                    "steps": "false"
                }
            )
            response.raise_for_status()
            routing_data = response.json()

    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="The routing service took too long. Please try again."
        )
    except httpx.HTTPError:
        raise HTTPException(
            status_code=502,
            detail="The map service is temporarily unavailable. Please try again."
        )

    if routing_data.get("code") != "Ok" or not routing_data.get("routes"):
        raise HTTPException(
            status_code=404,
            detail="No driving route found between these locations."
        )

    routes = []

    for index, route in enumerate(routing_data["routes"]):
        routes.append({
            "id": index + 1,
            "name": f"Route {chr(65 + index)}",
            "distance": format_distance(route["distance"]),
            "duration": format_duration(route["duration"]),
            "distance_meters": round(route["distance"]),
            "duration_seconds": round(route["duration"]),
            "traffic": "Live traffic unavailable",
            "recommended": False,
            "geometry": route["geometry"]
        })

    fastest_route = min(routes, key=lambda route: route["duration_seconds"])
    fastest_route["recommended"] = True
    fastest_route["name"] += " Â· Fastest base estimate"

    return {
        "origin": origin,
        "destination": destination,
        "routes": routes,
        "traffic_available": False,
        "message": (
            "Routes are based on OpenStreetMap routing data. "
            "Live traffic and AI video analysis are not connected yet."
        ),
        "map_attribution": "Â© OpenStreetMap contributors"
    }
