from flask import Flask, render_template, request, jsonify, session
import requests
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from auth import auth_bp, login_required, save_search_history, get_search_history, delete_history_item

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')

# Register authentication blueprint
app.register_blueprint(auth_bp)

# Amadeus API Configuration
# These will be set via environment variables or Secret Manager on GCP
AMADEUS_API_KEY = os.environ.get('AMADEUS_API_KEY', 'YOUR_API_KEY')
AMADEUS_API_SECRET = os.environ.get('AMADEUS_API_SECRET', 'YOUR_API_SECRET')
AMADEUS_BASE_URL = 'https://test.api.amadeus.com'
DEFAULT_CURRENCY = 'GBP'

# Airline code to full name mapping
AIRLINE_NAMES = {
    'AA': 'American Airlines',
    'BA': 'British Airways',
    'CA': 'Air China',
    'CX': 'Cathay Pacific',
    'DL': 'Delta Air Lines',
    'EK': 'Emirates',
    'EY': 'Etihad Airways',
    'LH': 'Lufthansa',
    'QF': 'Qantas',
    'QR': 'Qatar Airways',
    'SQ': 'Singapore Airlines',
    'TG': 'Thai Airways',
    'UA': 'United Airlines',
    'VS': 'Virgin Atlantic',
    'AF': 'Air France',
    'KL': 'KLM',
    'NH': 'ANA',
    'JL': 'Japan Airlines',
    'CZ': 'China Southern',
    'MU': 'China Eastern',
    'TR': 'Scoot',
    'AK': 'AirAsia',
    'FD': 'Thai AirAsia',
    'SU': 'Aeroflot',
    'TK': 'Turkish Airlines',
    'LX': 'Swiss',
    'OS': 'Austrian Airlines',
    'IB': 'Iberia',
    'AZ': 'ITA Airways',
    'KE': 'Korean Air',
    'OZ': 'Asiana Airlines',
    'BR': 'EVA Air',
    'CI': 'China Airlines',
    'MH': 'Malaysia Airlines',
    'GA': 'Garuda Indonesia',
    'PR': 'Philippine Airlines',
    'VN': 'Vietnam Airlines',
    'AI': 'Air India',
    'EI': 'Aer Lingus',
    'SK': 'SAS',
    'AY': 'Finnair',
    'TP': 'TAP Portugal',
    'WN': 'Southwest Airlines',
    'B6': 'JetBlue',
    'AS': 'Alaska Airlines',
    'AC': 'Air Canada',
    'WS': 'WestJet',
    'LA': 'LATAM',
    'AM': 'Aeromexico',
    'AV': 'Avianca',
    'CM': 'Copa Airlines',
    'SA': 'South African Airways',
    'ET': 'Ethiopian Airlines',
    'MS': 'EgyptAir',
    'RJ': 'Royal Jordanian',
    'GF': 'Gulf Air',
    'WY': 'Oman Air',
    'UL': 'SriLankan Airlines',
    'PK': 'Pakistan International',
    'BG': 'Biman Bangladesh',
    'SV': 'Saudia',
    'FZ': 'flydubai',
    'G9': 'Air Arabia',
    'UK': 'Vistara',
    '6E': 'IndiGo',
    'SG': 'SpiceJet',
}

def get_airline_name(code):
    """Get full airline name from code"""
    return AIRLINE_NAMES.get(code, code)

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
        # Don't force currency - let Amadeus return natural currency for the route
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
            if response.status_code != 200:
                print(f"Flight API error: {response.status_code} - {response.text}")
                # Return special indicator for API issues vs no flights
                try:
                    error_data = response.json()
                    if error_data.get('errors'):
                        error_code = error_data['errors'][0].get('code')
                        if error_code == 141:  # System error - Amadeus test API limitation
                            return {'api_error': 'Flight search temporarily unavailable (Amadeus test API limitation)'}
                except:
                    pass
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error searching flights: {e}")
            return {'api_error': 'Flight search service unavailable'}
    
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
                'adults': adults,
                'currency': DEFAULT_CURRENCY
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
@login_required
def index():
    """Home page - requires login"""
    return render_template('index.html', username=session.get('user_id'))

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
        
        # Save search history with best deal if user is logged in
        if 'user_id' in session and results.get('packages'):
            best_package = results['packages'][0] if results['packages'] else None
            if best_package:
                history_data = {
                    'origin': origin,
                    'destination': destination,
                    'departure_date': check_in,
                    'return_date': check_out,
                    'adults': adults,
                    'best_package': {
                        'flight': {
                            'airline': best_package['flight'].get('airline'),
                            'price': best_package['flight'].get('price'),
                            'currency': best_package['flight'].get('currency'),
                            'stops': best_package['flight'].get('stops')
                        },
                        'hotel': {
                            'name': best_package['hotel'].get('name'),
                            'price_per_night': best_package['hotel'].get('price_per_night'),
                            'total_price': best_package['hotel'].get('total_price'),
                            'currency': best_package['hotel'].get('currency')
                        },
                        'destination_total': best_package.get('destination_total'),
                        'destination_currency': best_package.get('destination_currency')
                    }
                }
                save_search_history(session['user_id'], history_data)
        
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def process_results(flights, hotels, activities, duration, adults, destination_info=None):
    """Process and combine all travel data - uses destination currency for consistency"""
    flight_options = []
    hotel_options = []
    activity_options = []
    seen_flights = set()  # Track unique flights
    seen_hotels = set()   # Track unique hotels
    flight_api_error = None
    
    # Check for flight API error
    if flights and 'api_error' in flights:
        flight_api_error = flights['api_error']
        flights = None  # Reset to prevent processing
    
    # Determine destination currency from hotels (most reliable for destination)
    destination_currency = DEFAULT_CURRENCY
    if hotels and 'data' in hotels and len(hotels['data']) > 0:
        first_hotel = hotels['data'][0]
        if 'offers' in first_hotel and first_hotel['offers']:
            destination_currency = first_hotel['offers'][0]['price'].get('currency', DEFAULT_CURRENCY)
    
    # Process flights (deduplicate by airline + price + stops)
    # Keep original currency for flights as they're booked from origin
    if flights and 'data' in flights:
        for flight in flights['data'][:10]:
            airline_code = flight['validatingAirlineCodes'][0] if flight.get('validatingAirlineCodes') else 'N/A'
            airline_name = get_airline_name(airline_code)
            price = float(flight['price']['total'])
            currency = flight['price'].get('currency', DEFAULT_CURRENCY)
            stops = len(flight['itineraries'][0]['segments']) - 1
            flight_key = (airline_code, price, stops)
            
            if flight_key not in seen_flights:
                seen_flights.add(flight_key)
                flight_options.append({
                    'id': flight.get('id'),
                    'price': price,
                    'currency': currency,
                    'airline_code': airline_code,
                    'airline': airline_name,
                    'duration': flight['itineraries'][0].get('duration', 'N/A'),
                    'stops': stops,
                    'details': flight
                })
    
    # Process hotels (deduplicate by name + price) - uses destination currency
    if hotels and 'data' in hotels:
        for hotel in hotels['data'][:10]:
            if 'offers' in hotel and hotel['offers']:
                offer = hotel['offers'][0]
                # The API returns total price for entire stay
                total_price = float(offer['price']['total'])
                currency = offer['price'].get('currency', destination_currency)
                hotel_name = hotel.get('hotel', {}).get('name', 'Unknown Hotel')
                hotel_key = (hotel_name, total_price)
                
                if hotel_key not in seen_hotels:
                    seen_hotels.add(hotel_key)
                    # Calculate per-night price
                    price_per_night = total_price / duration if duration > 0 else total_price
                    hotel_options.append({
                        'id': hotel.get('hotel', {}).get('hotelId'),
                        'name': hotel_name,
                        'price_per_night': price_per_night,
                        'total_price': total_price,
                        'currency': currency,
                        'details': hotel
                    })
    
    # Process activities - keep original currency from API
    if activities and 'data' in activities:
        for activity in activities['data'][:10]:
            # Get original price and currency from API
            original_price = float(activity.get('price', {}).get('amount', 0))
            original_currency = activity.get('price', {}).get('currencyCode', 'USD')
            
            activity_options.append({
                'id': activity.get('id'),
                'name': activity.get('name', 'Unknown Activity'),
                'price': original_price,
                'currency': original_currency,  # Display in actual currency from API
                'type': activity.get('type', 'activity'),
                'description': activity.get('shortDescription', 'No description available'),
                'details': activity
            })
    
    # Calculate total costs for different combinations
    packages = calculate_best_packages(flight_options, hotel_options, activity_options, duration, adults, destination_currency)
    
    result = {
        'flights': flight_options,
        'hotels': hotel_options,
        'activities': activity_options,
        'packages': packages,
        'duration': duration,
        'destination_currency': destination_currency
    }
    
    # Add flight API error message if present
    if flight_api_error:
        result['flight_api_error'] = flight_api_error
    
    # Add destination info if available
    if destination_info:
        result['destination'] = {
            'city': destination_info.get('city_name', ''),
            'country': destination_info.get('country_code', ''),
            'latitude': destination_info.get('latitude'),
            'longitude': destination_info.get('longitude')
        }
    
    return result

def calculate_best_packages(flights, hotels, activities, duration, adults, destination_currency):
    """Calculate best package combinations using destination currency for hotels/activities"""
    packages = []
    
    # Ensure we have data
    if not flights or not hotels:
        return packages
    
    # Create packages with different flight and hotel combinations
    for flight in flights[:3]:  # Top 3 flights
        for hotel in hotels[:3]:  # Top 3 hotels
            # Calculate total in destination currency (hotel + activities)
            # Flight stays in its original currency since booked from origin
            destination_total = hotel['total_price']
            if activities:
                destination_total += sum([a['price'] for a in activities[:5]])
            
            packages.append({
                'flight': flight,
                'hotel': hotel,
                'destination_total': destination_total,
                'destination_currency': destination_currency
            })
    
    # Sort packages by hotel price (destination currency)
    packages.sort(key=lambda x: x['hotel']['total_price'])
    
    # Return only top 5 unique packages
    return packages[:5]

@app.route('/history')
@login_required
def history():
    """Display search history page"""
    user_history = get_search_history(session.get('user_id'))
    return render_template('history.html', username=session.get('user_id'), history=user_history)

@app.route('/api/history/<history_id>', methods=['DELETE'])
@login_required
def delete_history(history_id):
    """Delete a history item"""
    username = session.get('user_id')
    if delete_history_item(username, history_id):
        return jsonify({'status': 'success', 'message': 'History item deleted'})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to delete history item'}), 500

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