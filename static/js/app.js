
const form = document.getElementById("route-form");
const resultsContainer = document.getElementById("route-results");
const trafficMessage = document.getElementById("traffic-message");

const map = L.map("map").setView([14.9136, 79.9930], 10);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 19
}).addTo(map);

let routeLayers = [];
let locationMarkers = [];

function clearMap() {
    routeLayers.forEach(layer => map.removeLayer(layer));
    locationMarkers.forEach(marker => map.removeLayer(marker));

    routeLayers = [];
    locationMarkers = [];
}

function displayRoutesOnMap(routes) {
    clearMap();

    routes.forEach((route, index) => {
        if (!route.geometry || !route.geometry.coordinates) {
            return;
        }

        const coordinates = route.geometry.coordinates.map(point => [
            point[1],
            point[0]
        ]);

        const isRecommended = route.recommended;

        const line = L.polyline(coordinates, {
            color: isRecommended ? "#22d3ee" : "#7188a4",
            weight: isRecommended ? 6 : 4,
            opacity: isRecommended ? 1 : 0.8
        }).addTo(map);

        line.bindPopup(`
            <strong>${route.name}</strong><br>
            Distance: ${route.distance}<br>
            Estimated time: ${route.duration}
        `);

        routeLayers.push(line);
    });

    if (routeLayers.length > 0) {
        const allRoutes = L.featureGroup(routeLayers);

        map.fitBounds(allRoutes.getBounds(), {
            padding: [25, 25]
        });
    }
}

function displayRouteCards(routes) {
    resultsContainer.innerHTML = routes.map(route => `
        <article class="route-card ${route.recommended ? "recommended" : ""}">
            <h3>${route.name}</h3>

            ${route.recommended
                ? '<span class="recommended-label">Fastest Base Estimate</span>'
                : ""}

            <p><strong>Distance:</strong> ${route.distance}</p>
            <p><strong>Estimated Time:</strong> ${route.duration}</p>
            <p><strong>Traffic:</strong> ${route.traffic}</p>
        </article>
    `).join("");
}

form.addEventListener("submit", async event => {
    event.preventDefault();

    const origin = document.getElementById("origin").value.trim();
    const destination = document.getElementById("destination").value.trim();

    if (!origin || !destination) {
        resultsContainer.innerHTML =
            '<p class="error">Enter both locations.</p>';
        return;
    }

    resultsContainer.innerHTML = "<p>Searching for routes...</p>";
    trafficMessage.textContent = "Retrieving route information...";
    clearMap();

    try {
        const response = await fetch("/api/routes/search", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                origin: origin,
                destination: destination
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Unable to find routes.");
        }

        if (!data.routes || data.routes.length === 0) {
            resultsContainer.innerHTML =
                "<p>No routes were found for these locations.</p>";
            return;
        }

        displayRouteCards(data.routes);
        displayRoutesOnMap(data.routes);

        trafficMessage.textContent = data.message ||
            "Live traffic data is not available.";

    } catch (error) {
        resultsContainer.innerHTML = `
            <p class="error">${error.message}</p>
        `;

        trafficMessage.textContent =
            "Route information could not be retrieved. Please try again.";
    }
});
