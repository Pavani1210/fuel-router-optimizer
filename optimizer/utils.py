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

def get_fuel_stations_along_route(route_geometry, max_distance_miles=10):
    sampled_points = []
    accumulated_dist = 0
    prev_p = None
    for p in route_geometry:
        if prev_p is None:
            sampled_points.append(p)
            prev_p = p
            continue
        d = haversine_distance(prev_p[1], prev_p[0], p[1], p[0])
        accumulated_dist += d
        if accumulated_dist >= 50: # Increased sampling distance to speed up
            sampled_points.append(p)
            accumulated_dist = 0
        prev_p = p
    
    lats = [p[1] for p in route_geometry]
    lons = [p[0] for p in route_geometry]
    min_lat, max_lat = min(lats) - 0.5, max(lats) + 0.5
    min_lon, max_lon = min(lons) - 0.5, max(lons) + 0.5
    
    # Get all cities already geocoded in the bounding box
    potential_cities = CityCoordinate.objects.filter(
        latitude__gte=min_lat, latitude__lte=max_lat,
        longitude__gte=min_lon, longitude__lte=max_lon
    )
    
    # If no cities are cached, we might need to geocode some.
    # To keep it fast for the user, we'll only geocode a few cities near the route points
    if not potential_cities.exists():
        # This is a fallback for the first run
        pass

    stations_near_route = []
    
    # Filter all stations by the bounding box of cached cities
    for city_coord in potential_cities:
        # Check if city is near any sampled point
        is_near = False
        for sp in sampled_points:
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
        return [], 0, 0
    
    route_points_dist = []
    total_d = 0
    prev_p = None
    for p in route_geometry:
        if prev_p:
            total_d += haversine_distance(prev_p[1], prev_p[0], p[1], p[0])
        route_points_dist.append(total_d)
        prev_p = p
    
    for s in stations:
        min_d = float('inf')
        closest_idx = 0
        for i, p in enumerate(route_geometry):
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
    
    while current_dist + current_fuel_range < destination_dist:
        reachable = [s for s in stations if s['distance_from_start'] > current_dist and s['distance_from_start'] <= current_dist + current_fuel_range]
        
        if not reachable:
            # If no stations reachable, try to reach the furthest one anyway to make progress
            break
        
        # Greedy strategy: find the cheapest station reachable
        best_station = min(reachable, key=lambda x: x['price'])
        
        segment_distance = best_station['distance_from_start'] - last_stop_dist
        gallons_needed = segment_distance / mpg
        stop_cost = gallons_needed * best_station['price']
        
        total_cost += stop_cost
        
        best_station.update({
            "selection_reason": "Cheapest fuel station within current vehicle range",
            "estimated_gallons_purchased": round(gallons_needed, 2),
            "estimated_stop_cost": round(stop_cost, 2),
            "step_distance": round(segment_distance, 2)
        })
        
        stops.append(best_station)
        current_dist = best_station['distance_from_start']
        last_stop_dist = current_dist
        current_fuel_range = max_range

    # Final segment from last stop to destination
    final_segment_dist = destination_dist - last_stop_dist
    final_gallons = final_segment_dist / mpg
    if stops:
        total_cost += final_gallons * stops[-1]['price']
    else:
        total_cost += final_gallons * 3.5 # Default fallback
        
    return stops, round(total_cost, 2), round(destination_dist / mpg, 2)
