<<<<<<< HEAD
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
## Optimization Algorithm
The algorithm uses a **Greedy Strategy with Distance Lookahead**:
1.  **Buffer Filtering**: It identifies all fuel stations within 10 miles of the calculated route geometry.
2.  **Distance Indexing**: Every station is indexed by its cumulative distance from the start point of the route.
3.  **Cheapest Reachable Search**: 
    *   Starting from the current location (initially 0), it identifies all stations reachable within the vehicle's remaining range (500 miles).
    *   It selects the **cheapest** station among the reachable ones.
    *   It repeats this process until the destination is reachable within the current range.
4.  **Metadata Calculation**: For each stop, it calculates the required gallons for that segment and the estimated cost.

## Example API Response

### NY → Chicago (~800 miles)
```json
{
  "total_distance_miles": 792.76,
  "total_fuel_cost": 242.51,
  "number_of_fuel_stops": 1,
  "fuel_stops": [
    {
      "name": "SHEETZ #639",
      "city": "Youngstown",
      "state": "OH",
      "price": 3.059,
      "selection_reason": "Cheapest fuel station within current vehicle range"
    }
  ]
}
```

### NY → LA (~2,800 miles)
The system will return 5+ stops, each strategically chosen to minimize costs while maintaining range.
