from django.urls import path
from .views import RouteOptimizerView, HomeView

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('optimize-route/', RouteOptimizerView.as_view(), name='optimize-route'),
]
