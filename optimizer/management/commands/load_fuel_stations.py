import csv
import os
import pandas as pd
from django.core.management.base import BaseCommand
from optimizer.models import FuelStation

class Command(BaseCommand):
    help = 'Load fuel stations from CSV'

    def handle(self, *args, **options):
        csv_path = os.getenv('FUEL_CSV_PATH', 'fuel-prices-for-be-assessment.csv')
        if not os.path.exists(csv_path):
            self.stdout.write(self.style.ERROR(f'File {csv_path} not found'))
            return

        df = pd.read_csv(csv_path)
        stations = []
        for _, row in df.iterrows():
            stations.append(FuelStation(
                opis_id=row['OPIS Truckstop ID'],
                name=row['Truckstop Name'],
                address=row['Address'],
                city=row['City'],
                state=row['State'],
                rack_id=row['Rack ID'],
                retail_price=row['Retail Price']
            ))
        
        FuelStation.objects.bulk_create(stations, ignore_conflicts=True)
        self.stdout.write(self.style.SUCCESS(f'Successfully loaded {len(stations)} fuel stations'))
