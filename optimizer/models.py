from django.db import models

class FuelStation(models.Model):
    opis_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=10)
    rack_id = models.IntegerField()
    retail_price = models.FloatField()
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} - {self.city}, {self.state}"

class CityCoordinate(models.Model):
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=10)
    latitude = models.FloatField()
    longitude = models.FloatField()

    class Meta:
        unique_together = ('city', 'state')

    def __str__(self):
        return f"{self.city}, {self.state}"

class RouteCache(models.Model):
    start_location = models.CharField(max_length=255)
    end_location = models.CharField(max_length=255)
    route_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('start_location', 'end_location')
