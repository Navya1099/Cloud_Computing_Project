from flask import Flask, render_template, request, jsonify
import requests
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Amadeus API Configuration
AMADEUS_API_KEY = os.getenv('AMADEUS_API_KEY', 'YOUR_API_KEY')
AMADEUS_API_SECRET = os.getenv('AMADEUS_API_SECRET', 'YOUR_API_SECRET')
AMADEUS_BASE_URL = 'https://test.api.amadeus.com'

class AmadeusAPI:
    def __init__(self):
        self.access_token = None
        self.token_expiry = None
    
    def get_access_token(self):
        """Get OAuth2 access token from Amadeus"""
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.access_token
        
        url = f"{AMADEUS_BASE_URL}/v1/security/oauth2/token"
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        data = {
            'grant_type': 'client_credentials',
            'client_id': AMADEUS_API_KEY,
            'client_secret': AMADEUS_API_SECRET
        }
        
        try:
            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data['access_token']
            # Token expires in seconds, set expiry time
            self.token_expiry = datetime.now() + timedelta(seconds=token_data.get('expires_in', 1800))
            return self.access_token
        except Exception as e:
            print(f"Error getting access token: {e}")
            return None
    
    def get_airport_location(self, airport_code):
        """Get coordinates for an airport code"""
        token = self.get_access_token()
        if not token:
            return None
        
        url = f"{AMADEUS_BASE_URL}/v1/reference-data/locations"
        headers = {'Authorization': f'Bearer {token}'}
        params = {
            'subType': 'AIRPORT,CITY',
            'keyword': airport_code,
            'page[limit]': 1
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get('data') and len(data['data']) > 0:
                location = data['data'][0]
                geo_code = location.get('geoCode', {})
                return {
                    'latitude': geo_code.get('latitude'),
                    'longitude': geo_code.get('longitude'),
                    'city_name': location.get('address', {}).get('cityName', ''),
                    'country_code': location.get('address', {}).get('countryCode', '')
                }
            return None
        except Exception as e:
            print(f"Error getting airport location: {e}")
            return None
    
    def search_flights(self, origin, destination, departure_date, return_date, adults=1):
        """Search for flights"""
        token = self.get_access_token()
        if not token:
            return None
        
        url = f"{AMADEUS_BASE_URL}/v2/shopping/flight-offers"
        headers = {'Authorization': f'Bearer {token}'}
        params = {
            'originLocationCode': origin,
            'destinationLocationCode': destination,
            'departureDate': departure_date,
            'returnDate': return_date,
            'adults': adults,
            'max': 10
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error searching flights: {e}")
            return None
    
    def search_hotels(self, city_code, check_in, check_out, adults=1):
        """Search for hotels"""
        token = self.get_access_token()
        if not token:
            return None
        
        # First, get hotel list by city
        url = f"{AMADEUS_BASE_URL}/v1/reference-data/locations/hotels/by-city"
        headers = {'Authorization': f'Bearer {token}'}
        params = {'cityCode': city_code}
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            hotel_data = response.json()
            
            if not hotel_data.get('data'):
                return None
            
            # Get hotel IDs (limit to first 50 for performance)
            hotel_ids = [hotel['hotelId'] for hotel in hotel_data['data'][:50]]
            
            # Search for hotel offers
            offers_url = f"{AMADEUS_BASE_URL}/v3/shopping/hotel-offers"
            offers_params = {
                'hotelIds': ','.join(hotel_ids),
                'checkInDate': check_in,
                'checkOutDate': check_out,
                'adults': adults
            }
            
            offers_response = requests.get(offers_url, headers=headers, params=offers_params)
            offers_response.raise_for_status()
            return offers_response.json()
        except Exception as e:
            print(f"Error searching hotels: {e}")
            return None
    
    def get_points_of_interest(self, latitude, longitude):
        """Get points of interest (restaurants, attractions)"""
        token = self.get_access_token()
        if not token:
            return None
        
        url = f"{AMADEUS_BASE_URL}/v1/shopping/activities"
        headers = {'Authorization': f'Bearer {token}'}
        params = {
            'latitude': latitude,
            'longitude': longitude,
            'radius': 20
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error getting points of interest: {e}")
            return None
    
    def get_activities_by_city(self, city_code):
        """Get activities by city code (alternative method)"""
        token = self.get_access_token()
        if not token:
            return None
        
        url = f"{AMADEUS_BASE_URL}/v1/shopping/activities"
        headers = {'Authorization': f'Bearer {token}'}
        params = {
            'cityCode': city_code
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error getting activities by city: {e}")
            return None

amadeus_api = AmadeusAPI()

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    """Search for travel options"""
    try:
        data = request.json
        origin = data.get('origin')
        destination = data.get('destination')
        check_in = data.get('checkIn')
        check_out = data.get('checkOut')
        adults = int(data.get('adults', 1))
        
        # Calculate duration in days
        check_in_date = datetime.strptime(check_in, '%Y-%m-%d')
        check_out_date = datetime.strptime(check_out, '%Y-%m-%d')
        duration = (check_out_date - check_in_date).days
        
        # Search flights
        flights = amadeus_api.search_flights(origin, destination, check_in, check_out, adults)
        
        # Search hotels
        hotels = amadeus_api.search_hotels(destination, check_in, check_out, adults)
        
        # Get destination location coordinates
        destination_location = amadeus_api.get_airport_location(destination)
        
        # Get activities based on destination
        activities = None
        if destination_location and destination_location.get('latitude') and destination_location.get('longitude'):
            # Try getting activities by coordinates
            activities = amadeus_api.get_points_of_interest(
                destination_location['latitude'],
                destination_location['longitude']
            )
        
        # If coordinate-based search fails or returns nothing, try city code
        if not activities or not activities.get('data'):
            activities = amadeus_api.get_activities_by_city(destination)
        
        # Process and combine results
        results = process_results(flights, hotels, activities, duration, adults, destination_location)
        
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def process_results(flights, hotels, activities, duration, adults, destination_info=None):
    """Process and combine all travel data"""
    flight_options = []
    hotel_options = []
    activity_options = []
    
    # Process flights
    if flights and 'data' in flights:
        for flight in flights['data'][:10]:
            flight_options.append({
                'id': flight.get('id'),
                'price': float(flight['price']['total']),
                'currency': flight['price']['currency'],
                'airline': flight['validatingAirlineCodes'][0] if flight.get('validatingAirlineCodes') else 'N/A',
                'duration': flight['itineraries'][0].get('duration', 'N/A'),
                'stops': len(flight['itineraries'][0]['segments']) - 1,
                'details': flight
            })
    
    # Process hotels
    if hotels and 'data' in hotels:
        for hotel in hotels['data'][:10]:
            if 'offers' in hotel and hotel['offers']:
                offer = hotel['offers'][0]
                hotel_options.append({
                    'id': hotel.get('hotel', {}).get('hotelId'),
                    'name': hotel.get('hotel', {}).get('name', 'Unknown Hotel'),
                    'price_per_night': float(offer['price']['total']),
                    'total_price': float(offer['price']['total']) * duration,
                    'currency': offer['price']['currency'],
                    'details': hotel
                })
    
    # Process activities (restaurants, attractions)
    if activities and 'data' in activities:
        for activity in activities['data'][:10]:
            activity_options.append({
                'id': activity.get('id'),
                'name': activity.get('name', 'Unknown Activity'),
                'price': float(activity.get('price', {}).get('amount', 0)),
                'currency': activity.get('price', {}).get('currencyCode', 'USD'),
                'type': activity.get('type', 'activity'),
                'description': activity.get('shortDescription', 'No description available'),
                'details': activity
            })
    
    # Calculate total costs for different combinations
    packages = calculate_best_packages(flight_options, hotel_options, activity_options, duration, adults)
    
    result = {
        'flights': flight_options,
        'hotels': hotel_options,
        'activities': activity_options,
        'packages': packages,
        'duration': duration
    }
    
    # Add destination info if available
    if destination_info:
        result['destination'] = {
            'city': destination_info.get('city_name', ''),
            'country': destination_info.get('country_code', ''),
            'latitude': destination_info.get('latitude'),
            'longitude': destination_info.get('longitude')
        }
    
    return result

def calculate_best_packages(flights, hotels, activities, duration, adults):
    """Calculate best package combinations"""
    packages = []
    
    # Ensure we have data
    if not flights or not hotels:
        return packages
    
    # Calculate estimated daily food/restaurant costs (approximate)
    avg_daily_food_cost = 50 * adults  # $50 per person per day
    
    # Create packages with different flight and hotel combinations
    for flight in flights[:3]:  # Top 3 flights
        for hotel in hotels[:3]:  # Top 3 hotels
            # Calculate activity costs (optional activities)
            activity_cost = sum([a['price'] for a in activities[:5]]) if activities else 0
            
            total_cost = (
                flight['price'] + 
                hotel['total_price'] + 
                (avg_daily_food_cost * duration) +
                activity_cost
            )
            
            packages.append({
                'flight': flight,
                'hotel': hotel,
                'estimated_food_cost': avg_daily_food_cost * duration,
                'activities_cost': activity_cost,
                'total_cost': total_cost,
                'currency': flight['currency']
            })
    
    # Sort packages by total cost
    packages.sort(key=lambda x: x['total_cost'])
    
    return packages

@app.route('/api/test', methods=['GET'])
def test_api():
    """Test API connection"""
    token = amadeus_api.get_access_token()
    if token:
        return jsonify({'status': 'success', 'message': 'API connection successful'})
    else:
        return jsonify({'status': 'error', 'message': 'API connection failed'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)