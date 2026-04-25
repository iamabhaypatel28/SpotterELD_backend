import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime
from .hos_engine import HOSEngine

class CalculateTripView(APIView):
    def post(self, request):
        current_loc = request.data.get('current_location')
        pickup_loc = request.data.get('pickup_location')
        dropoff_loc = request.data.get('dropoff_location')
        cycle_used = float(request.data.get('cycle_used', 0))
        
        # 1. Geocoding
        def geocode(location):
            if not location: return None
            url = f"https://nominatim.openstreetmap.org/search?q={location}&format=json&limit=1"
            headers = {'User-Agent': 'SpotterAssessment/1.0'}
            try:
                resp = requests.get(url, headers=headers).json()
                if resp:
                    return {
                        'lat': float(resp[0]['lat']),
                        'lon': float(resp[0]['lon']),
                        'display_name': resp[0]['display_name']
                    }
            except:
                pass
            return None

        loc_current = geocode(current_loc)
        loc_pickup = geocode(pickup_loc)
        loc_dropoff = geocode(dropoff_loc)
        
        if not loc_pickup or not loc_dropoff:
            return Response({'error': 'Invalid locations'}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Routing (Pickup to Dropoff)
        # We assume the trip starts from Current Location -> Pickup -> Dropoff
        # For simplicity, we'll just calculate Pickup to Dropoff for the HOS engine
        # and include the Current to Pickup distance if they are different.
        
        def get_route(start, end):
            url = f"http://router.project-osrm.org/route/v1/driving/{start['lon']},{start['lat']};{end['lon']},{end['lat']}?overview=full&geometries=geojson"
            try:
                resp = requests.get(url).json()
                if resp['code'] == 'Ok':
                    route = resp['routes'][0]
                    return {
                        'distance_meters': route['distance'],
                        'duration_seconds': route['duration'],
                        'geometry': route['geometry']
                    }
            except:
                pass
            return None

        # Distance from Current to Pickup
        dist_to_pickup = 0
        if loc_current:
            route_to_pickup = get_route(loc_current, loc_pickup)
            if route_to_pickup:
                dist_to_pickup = route_to_pickup['distance_meters']
        
        # Main trip: Pickup to Dropoff
        main_route = get_route(loc_pickup, loc_dropoff)
        if not main_route:
            return Response({'error': 'Could not calculate route'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        total_distance_miles = (dist_to_pickup + main_route['distance_meters']) * 0.000621371
        
        # 3. HOS Calculation
        start_time = datetime.now()
        
        pre_trip_miles = dist_to_pickup * 0.000621371
        main_trip_miles = main_route['distance_meters'] * 0.000621371
        
        engine = HOSEngine(
            start_time=start_time, 
            pre_trip_distance=pre_trip_miles, 
            main_trip_distance=main_trip_miles, 
            cycle_used=cycle_used
        )
        segments = engine.calculate_trip()
        
        # Serialize segments for JSON
        serialized_segments = []
        for seg in segments:
            serialized_segments.append({
                'status': seg['status'],
                'start': seg['start'].isoformat(),
                'end': seg['end'].isoformat(),
                'remarks': seg['remarks']
            })
            
        return Response({
            'pickup': loc_pickup,
            'dropoff': loc_dropoff,
            'distance_miles': round(pre_trip_miles + main_trip_miles, 2),
            'duration_hours': round(main_route['duration_seconds'] / 3600, 2),
            'geometry': main_route['geometry'],
            'segments': serialized_segments
        })

