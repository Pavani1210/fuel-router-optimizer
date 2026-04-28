from django.core.management.base import BaseCommand
from optimizer.utils import get_city_coords
from optimizer.models import FuelStation

class Command(BaseCommand):
    help = 'Pre-geocode major cities along a common route'

    def handle(self, *args, **options):
        # Major cities along I-80 (common East-West route)
        cities = [
            ("New York", "NY"),
            ("Jersey City", "NJ"),
            ("Easton", "PA"),
            ("Hazleton", "PA"),
            ("Clearfield", "PA"),
            ("Youngstown", "OH"),
            ("Akron", "OH"),
            ("Toledo", "OH"),
            ("South Bend", "IN"),
            ("Chicago", "IL"),
            ("Davenport", "IA"),
            ("Des Moines", "IA"),
            ("Omaha", "NE"),
            ("Lincoln", "NE"),
            ("Kearney", "NE"),
            ("North Platte", "NE"),
            ("Cheyenne", "WY"),
            ("Laramie", "WY"),
            ("Rawlins", "WY"),
            ("Rock Springs", "WY"),
            ("Salt Lake City", "UT"),
            ("Wendover", "UT"),
            ("Elko", "NV"),
            ("Winnemucca", "NV"),
            ("Reno", "NV"),
            ("Sacramento", "CA"),
            ("San Francisco", "CA")
        ]
        
        for city, state in cities:
            self.stdout.write(f"Geocoding {city}, {state}...")
            lat, lon = get_city_coords(city, state)
            if lat:
                self.stdout.write(self.style.SUCCESS(f"Success: {lat}, {lon}"))
            else:
                self.stdout.write(self.style.ERROR(f"Failed to geocode {city}"))
