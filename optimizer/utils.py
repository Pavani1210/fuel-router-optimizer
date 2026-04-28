import requests
import os
import json
from django.conf import settings
from .models import FuelStation, RouteCache, CityCoordinate
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import time
import math

ORS_API_KEY = os.getenv('OPENROUTESERVICE_API_KEY')
ORS_BASE_URL = os.getenv('OPENROUTESERVICE_BASE_URL', 'https://api.openrouteservice.org')

geolocator = Nominatim(user_agent="fuel_optimizer_v1")

def geocode_location(query):
    try:
        location = geolocator.geocode(query)
        if location:
            return location.latitude, location.longitude
    except GeocoderTimedOut:
        time.sleep(1)
        return geocode_location(query)
    except Exception as e:
        print(f"Geocoding error for {query}: {e}")
    return None, None

def get_city_coords(city, state):
    city_coord = CityCoordinate.objects.filter(city=city, state=state).first()
    if city_coord:
        return city_coord.latitude, city_coord.longitude
    
    lat, lon = geocode_location(f"{city}, {state}, USA")
    if lat and lon:
        CityCoordinate.objects.get_or_create(city=city, state=state, defaults={'latitude': lat, 'longitude': lon})
        return lat, lon
    return None, None

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 3958.8 # Earth radius in miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

def get_route(start_coords, end_coords):
    url = f"{ORS_BASE_URL}/v2/directions/driving-car/geojson"
    headers = {
        'Authorization': ORS_API_KEY,
        'Content-Type': 'application/json; charset=utf-8'
    }
    body = {
        "coordinates": [
            [start_coords[1], start_coords[0]], # ORS uses [lon, lat]
            [end_coords[1], end_coords[0]]
        ]
    }
    
    response = requests.post(url, json=body, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching route: {response.text}")
        return None

def get_fuel_stations_along_route(route_geometry, max_distance_miles=50):
    # 1. Sample route points more densely to create a broader corridor
    sampled_points = route_geometry[::10] 
    
    # 2. Get Bounding Box with more buffer
    lats = [p[1] for p in route_geometry]
    lons = [p[0] for p in route_geometry]
    min_lat, max_lat = min(lats) - 1.0, max(lats) + 1.0
    min_lon, max_lon = min(lons) - 1.0, max(lons) + 1.0
    
    # 3. Query all cached cities in the bounding box
    cached_cities = CityCoordinate.objects.filter(
        latitude__gte=min_lat, latitude__lte=max_lat,
        longitude__gte=min_lon, longitude__lte=max_lon
    )
    
    stations_near_route = []
    
    # 4. Filter cities by distance to the route corridor
    for city_coord in cached_cities:
        is_near = False
        # Optimized check: only check against every 5th sampled point for speed
        for sp in sampled_points[::5]:
            if abs(city_coord.latitude - sp[1]) < 0.8 and abs(city_coord.longitude - sp[0]) < 0.8:
                if haversine_distance(city_coord.latitude, city_coord.longitude, sp[1], sp[0]) <= max_distance_miles:
                    is_near = True
                    break
        
        if is_near:
            city_stations = FuelStation.objects.filter(city=city_coord.city, state=city_coord.state)
            for s in city_stations:
                stations_near_route.append({
                    "name": s.name,
                    "address": s.address,
                    "city": s.city,
                    "state": s.state,
                    "price": s.retail_price,
                    "lat": city_coord.latitude,
                    "lon": city_coord.longitude
                })
    
    return stations_near_route

def calculate_optimal_fuel_stops(route_geometry, stations):
    if not stations:
        # Fallback to destination if no stations found anywhere
        return [], 0, 0
    
    route_points_dist = []
    total_d = 0
    prev_p = None
    for p in route_geometry:
        if prev_p:
            total_d += haversine_distance(prev_p[1], prev_p[0], p[1], p[0])
        route_points_dist.append(total_d)
        prev_p = p
    
    # Map stations to their distance along the route
    for s in stations:
        min_d = float('inf')
        closest_idx = 0
        # Use sampling for mapping station to route
        for i in range(0, len(route_geometry), 5):
            p = route_geometry[i]
            d = haversine_distance(s['lat'], s['lon'], p[1], p[0])
            if d < min_d:
                min_d = d
                closest_idx = i
        s['distance_from_start'] = route_points_dist[closest_idx]

    stations.sort(key=lambda x: x['distance_from_start'])
    
    max_range = float(os.getenv('MAX_VEHICLE_RANGE', 500))
    mpg = float(os.getenv('VEHICLE_MPG', 10))
    
    current_dist = 0
    current_fuel_range = max_range
    stops = []
    total_cost = 0
    last_stop_dist = 0
    destination_dist = route_points_dist[-1]
    
    # Buffer to ensure we find a station before running out of gas
    safety_buffer = 50 

    while current_dist + current_fuel_range < destination_dist:
        reachable = [s for s in stations if s['distance_from_start'] > current_dist and s['distance_from_start'] <= current_dist + current_fuel_range]
        
        if not reachable:
            break
        
        priority_window = [s for s in reachable if s['distance_from_start'] > current_dist + (max_range * 0.6)]
        candidates = priority_window if priority_window else reachable
        
        best_station = min(candidates, key=lambda x: x['price'])
        
        segment_distance = best_station['distance_from_start'] - last_stop_dist
        gallons_needed = segment_distance / mpg
        
        # If this is the LAST stop (i.e., destination is reachable from here), 
        # include the fuel needed to reach the destination.
        if best_station['distance_from_start'] + max_range >= destination_dist:
            extra_dist = destination_dist - best_station['distance_from_start']
            gallons_needed += extra_dist / mpg
        
        stop_cost = gallons_needed * best_station['price']
        total_cost += stop_cost
        
        best_station.update({
            "selection_reason": "Selected based on lowest fuel price within route corridor before 500-mile range limit",
            "estimated_gallons_purchased": round(gallons_needed, 2),
            "estimated_stop_cost": round(stop_cost, 2),
            "step_distance": round(segment_distance, 2)
        })
        
        stops.append(best_station)
        current_dist = best_station['distance_from_start']
        last_stop_dist = current_dist
        current_fuel_range = max_range

    # If NO stops were needed (destination reachable from start)
    if not stops:
        total_cost = (destination_dist / mpg) * 3.5 # Default fallback price
        
    return stops, round(total_cost, 2), round(destination_dist / mpg, 2)
