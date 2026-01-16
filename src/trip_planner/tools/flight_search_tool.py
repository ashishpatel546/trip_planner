from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import os
import requests
import json
from datetime import datetime
from typing import Optional


class FlightSearchInput(BaseModel):
    """Input schema for FlightSearchTool."""
    origin: str = Field(..., description="Origin city or IATA airport code (e.g., 'NYC' or 'JFK')")
    destination: str = Field(..., description="Destination city or IATA airport code (e.g., 'Tokyo' or 'NRT')")
    departure_date: str = Field(..., description="Departure date in YYYY-MM-DD format")
    return_date: Optional[str] = Field(None, description="Return date in YYYY-MM-DD format (optional)")
    currency: Optional[str] = Field("USD", description="Currency code: USD or INR (default: USD)")


class AmadeusFlightSearchTool(BaseTool):
    """Tool to search for flight prices using Amadeus API"""
    name: str = "Flight Price Search"
    description: str = "Search for actual flight prices between cities using Amadeus API. Requires origin, destination, and dates."
    args_schema: type[BaseModel] = FlightSearchInput
    
    # Declare these as fields that won't be validated
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    access_token: Optional[str] = None
    token_expiry: Optional[float] = None

    def __init__(self, **data):
        super().__init__(**data)
        self.api_key = os.getenv("AMADEUS_API_KEY")
        self.api_secret = os.getenv("AMADEUS_API_SECRET")

    def _get_access_token(self) -> str:
        """Get or refresh Amadeus access token"""
        if self.access_token and self.token_expiry:
            # Check if token is still valid
            if datetime.now().timestamp() < self.token_expiry:
                return self.access_token

        # Get new token
        url = "https://test.api.amadeus.com/v1/security/oauth2/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.api_secret
        }

        try:
            response = requests.post(url, headers=headers, data=data, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            self.access_token = result["access_token"]
            # Token expires in seconds, set expiry time
            self.token_expiry = datetime.now().timestamp() + result["expires_in"] - 60
            
            return self.access_token
        except Exception as e:
            raise Exception(f"Failed to get Amadeus access token: {str(e)}")

    def _get_iata_code(self, city_name: str) -> str:
        """Get IATA code for a city"""
        # Common city to IATA mappings
        city_codes = {
            "new york": "NYC", "nyc": "NYC",
            "london": "LON",
            "paris": "PAR",
            "tokyo": "TYO", 
            "los angeles": "LAX", "la": "LAX",
            "san francisco": "SFO",
            "chicago": "CHI",
            "dubai": "DXB",
            "singapore": "SIN",
            "hong kong": "HKG",
            "sydney": "SYD",
            "melbourne": "MEL",
            "bangkok": "BKK",
            "seoul": "SEL",
            "beijing": "BJS",
            "shanghai": "SHA",
            "mumbai": "BOM",
            "delhi": "DEL", "new delhi": "DEL",
            "bangalore": "BLR", "bengaluru": "BLR",
            "chennai": "MAA",
            "hyderabad": "HYD",
            "kolkata": "CCU",
            "pune": "PNQ",
            "ahmedabad": "AMD",
            "goa": "GOI",
            "kochi": "COK", "cochin": "COK",
            "jaipur": "JAI",
            "lucknow": "LKO",
            "chandigarh": "IXC",
            "indore": "IDR",
            "bhubaneswar": "BBI",
            "coimbatore": "CJB",
            "toronto": "YTO",
            "vancouver": "YVR",
            "rome": "ROM",
            "barcelona": "BCN",
            "amsterdam": "AMS",
            "madrid": "MAD",
            "berlin": "BER",
            "miami": "MIA",
            "boston": "BOS",
            "seattle": "SEA",
            "las vegas": "LAS",
            "orlando": "ORL"
        }
        
        # If it's already a 3-letter code, return it
        if len(city_name) == 3 and city_name.isupper():
            return city_name
        
        # Try to find in mapping
        normalized = city_name.lower().strip()
        return city_codes.get(normalized, city_name[:3].upper())

    def _run(self, origin: str, destination: str, departure_date: str, return_date: Optional[str] = None, currency: Optional[str] = "USD") -> str:
        """Search for flights using Amadeus API with currency support (USD/INR)"""
        
        if not self.api_key or not self.api_secret:
            return "❌ Amadeus API credentials not configured. Add AMADEUS_API_KEY and AMADEUS_API_SECRET to .env file"

        try:
            # Get access token
            token = self._get_access_token()
            
            # Convert city names to IATA codes
            origin_code = self._get_iata_code(origin)
            dest_code = self._get_iata_code(destination)
            
            # Build request
            url = "https://test.api.amadeus.com/v2/shopping/flight-offers"
            headers = {"Authorization": f"Bearer {token}"}
            # Validate currency
            currency_code = currency.upper() if currency else "USD"
            if currency_code not in ["USD", "INR"]:
                currency_code = "USD"  # Default to USD if invalid
            
            params = {
                "originLocationCode": origin_code,
                "destinationLocationCode": dest_code,
                "departureDate": departure_date,
                "adults": 1,
                "max": 5,  # Get top 5 offers
                "currencyCode": currency_code
            }
            
            if return_date:
                params["returnDate"] = return_date
            
            # Make API call
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Parse results
            if "data" not in data or len(data["data"]) == 0:
                return f"No flights found from {origin} ({origin_code}) to {destination} ({dest_code}) on {departure_date}"
            
            # Get currency symbol
            currency_symbol = "₹" if currency_code == "INR" else "$"
            
            results = []
            results.append(f"✈️ Flight Options from {origin} to {destination}")
            results.append(f"Departure: {departure_date}" + (f" | Return: {return_date}" if return_date else " (One-way)"))
            results.append(f"Currency: {currency_code} ({currency_symbol})")
            results.append("=" * 60)
            
            for idx, offer in enumerate(data["data"][:5], 1):
                price = offer["price"]["total"]
                currency = offer["price"]["currency"]
                
                # Get itinerary details
                itineraries = offer["itineraries"]
                segments = itineraries[0]["segments"]
                
                # Departure info
                first_seg = segments[0]
                last_seg = segments[-1]
                
                airline = first_seg["carrierCode"]
                stops = len(segments) - 1
                duration = itineraries[0]["duration"]
                
                results.append(f"\nOption {idx}:")
                results.append(f"  Price: {currency_symbol}{price} {currency}")
                results.append(f"  Airline: {airline}")
                results.append(f"  Stops: {stops} {'stop' if stops == 1 else 'stops' if stops > 1 else 'Direct'}")
                results.append(f"  Duration: {duration}")
                results.append(f"  Departure: {first_seg['departure']['at']}")
                results.append(f"  Arrival: {last_seg['arrival']['at']}")
            
            # Add summary
            prices = [float(offer["price"]["total"]) for offer in data["data"][:5]]
            results.append("\n" + "=" * 60)
            results.append(f"💰 Price Range: {currency_symbol}{min(prices):.2f} - {currency_symbol}{max(prices):.2f}")
            results.append(f"📊 Average Price: {currency_symbol}{sum(prices)/len(prices):.2f}")
            
            return "\n".join(results)
            
        except requests.exceptions.RequestException as e:
            return f"❌ API Error: {str(e)}"
        except Exception as e:
            return f"❌ Error searching flights: {str(e)}"


def get_flight_search_tool():
    """Get Amadeus flight search tool"""
    return AmadeusFlightSearchTool()
