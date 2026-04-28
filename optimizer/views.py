from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.views.generic import TemplateView
from .utils import geocode_location, get_route, get_fuel_stations_along_route, calculate_optimal_fuel_stops, get_city_coords
import os

class RouteOptimizerView(APIView):
    def post(self, request):
        try:
            start_location = request.data.get('start')
            finish_location = request.data.get('finish')

            if not start_location or not finish_location:
                return Response({"error": "Start and finish locations are required"}, status=status.HTTP_400_BAD_REQUEST)

            # 1. Geocode start and finish
            start_lat, start_lon = geocode_location(start_location)
            finish_lat, finish_lon = geocode_location(finish_location)

            if not start_lat or not finish_lat:
                return Response({"error": "Could not geocode start or finish location"}, status=status.HTTP_400_BAD_REQUEST)

            # 2. Get route
            route_data = get_route((start_lat, start_lon), (finish_lat, finish_lon))
            if not route_data:
                return Response({"error": "Could not find route"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            geometry = route_data['features'][0]['geometry']['coordinates'] # [lon, lat]
            summary = route_data['features'][0]['properties']['summary']
            total_distance_meters = summary['distance']
            total_distance_miles = total_distance_meters * 0.000621371

            # 4. Find fuel stations along the route
            stations = get_fuel_stations_along_route(geometry)
            
            # 5. Calculate optimal stops
            fuel_stops, total_fuel_cost, total_gallons = calculate_optimal_fuel_stops(geometry, stations)
            
            return Response({
                "start": {"lat": start_lat, "lon": start_lon, "name": start_location},
                "finish": {"lat": finish_lat, "lon": finish_lon, "name": finish_location},
                "total_distance_miles": round(total_distance_miles, 2),
                "total_fuel_cost": round(total_fuel_cost, 2),
                "total_gallons_required": total_gallons,
                "number_of_fuel_stops": len(fuel_stops),
                "fuel_efficiency_mpg": 10,
                "vehicle_range_miles": 500,
                "fuel_stops": fuel_stops,
                "map_url": f"https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route={start_lat}%2C{start_lon}%3B{finish_lat}%2C{finish_lon}",
                "route_coordinates": geometry[::10], # Reduce payload size
                "map_provider": "CartoDB Positron"
            })
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class HomeView(TemplateView):
    template_name = "index.html"
