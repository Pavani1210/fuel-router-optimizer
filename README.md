# Fuel Route Optimizer

A Django-based API that calculates the optimal fuel stops along a route within the USA, minimizing fuel costs based on provided fuel price data.

## Features
- **Route Optimization**: Finds the most cost-effective fuel stops along a route.
- **Interactive Map**: Visualizes the route and fuel stops using Leaflet.js.
- **Greedy Optimization Algorithm**: Ensures the vehicle never runs out of fuel while minimizing total cost.
- **Efficient Geocoding**: Caches city coordinates to minimize external API calls.
- **Environment Driven**: Fully configurable via `.env` file.

## Tech Stack
- **Backend**: Django, Django REST Framework
- **Database**: SQLite (Relational), MongoDB (Ready for caching/storage as per requirements)
- **APIs**: OpenRouteService (Routing), Nominatim (Geocoding fallback)
- **Frontend**: Vanilla JS, Leaflet.js

## Setup Instructions

### 1. Prerequisites
- Python 3.10+
- `pip`

### 2. Installation
1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure environment variables in `.env`:
   ```env
   OPENROUTESERVICE_API_KEY=your_key_here
   FUEL_CSV_PATH=fuel-prices-for-be-assessment.csv
   ```

### 3. Database Initialization
1. Run migrations:
   ```bash
   python manage.py migrate
   ```
2. Load fuel station data from CSV:
   ```bash
   python manage.py load_fuel_stations
   ```
3. (Optional) Pre-geocode some cities to speed up the first run:
   ```bash
   python manage.py pregeocode_cities
   ```

### 4. Running the Server
```bash
python manage.py runserver
```
Visit `http://127.0.0.1:8000/api/` to access the interactive map.

## API Documentation

### POST `/api/optimize-route/`
Calculates the optimal route and fuel stops.

**Request Body:**
```json
{
  "start": "New York, NY",
  "finish": "Chicago, IL"
}
```

**Response:**
```json
{
  "start": {"lat": 40.7128, "lon": -74.006, "name": "New York, NY"},
  "finish": {"lat": 41.8781, "lon": -87.6298, "name": "Chicago, IL"},
  "total_distance_miles": 789.2,
  "total_fuel_cost": 254.5,
  "fuel_stops": [...],
  "route": [...]
}
```

## Optimization Algorithm
The algorithm uses a greedy approach with a lookahead:
1. It identifies all fuel stations within 10 miles of the route.
2. It sorts them by distance from the start.
3. It iteratively finds the cheapest reachable station that allows reaching the next segment, ensuring the 500-mile range is never exceeded.
