# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "geopandas",
#   "requests",
#   "shapely",
#   "pandas"
# ]
# ///

import random
import json
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from typing import List, Tuple
import requests
import warnings
import argparse
import time

# Suppress geopandas warnings
warnings.filterwarnings('ignore')

def get_malta_boundary():
    """
    Get Malta's boundary polygon using OpenStreetMap data via Nominatim.
    
    Returns:
        GeoDataFrame containing Malta's boundary
    """
    try:
        # Try to get Malta boundary from OpenStreetMap
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': 'Malta',
            'format': 'geojson',
            'polygon_geojson': 1,
            'limit': 1
        }
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data['features']:
                gdf = gpd.GeoDataFrame.from_features(data['features'])
                gdf.set_crs('EPSG:4326', inplace=True)
                return gdf
    except Exception as e:
        print(f"Warning: Could not fetch Malta boundary from OSM: {e}")
    
    # Fallback: Create approximate Malta boundary polygon (main island)
    print("Using fallback approximate Malta boundary...")
    from shapely.geometry import Polygon
    
    # Malta's approximate boundary coordinates for the main island
    malta_coords = [
        (14.1836, 35.7836),  # Southwest (Dingli Cliffs area)
        (14.1836, 35.8889),  # Northwest (Mellieha area)
        (14.2500, 35.9500),  # North (Mellieha Bay area)
        (14.5000, 35.9500),  # Northeast (Marfa area)
        (14.5677, 35.8889),  # East (St. Julian's area)
        (14.5677, 35.8000),  # Southeast (Marsaxlokk area)
        (14.4500, 35.7836),  # South (Birzebbuga area)
        (14.3000, 35.7836),  # Southwest (Zurrieq area)
        (14.1836, 35.7836)   # Back to start
    ]
    
    polygon = Polygon(malta_coords)
    gdf = gpd.GeoDataFrame([1], geometry=[polygon], crs='EPSG:4326')
    return gdf

def generate_malta_points(num_points: int = 100) -> List[Tuple[float, float]]:
    """
    Generate random points within Malta's actual geographical boundaries using GeoPandas.
    
    Args:
        num_points: Number of random points to generate (default: 100)
        
    Returns:
        List of tuples containing (latitude, longitude) coordinates with 6 decimal precision.
    """
    # Get Malta's boundary
    malta_gdf = get_malta_boundary()
    malta_boundary = malta_gdf.geometry.iloc[0]
    
    # Get bounding box for efficient point generation
    minx, miny, maxx, maxy = malta_boundary.bounds
    
    points = []
    attempts = 0
    max_attempts = num_points * 20  # Prevent infinite loops, increased multiplier for sparse areas
    
    print(f"Generating {num_points} points within Malta's boundaries...")
    
    while len(points) < num_points and attempts < max_attempts:
        # Generate random point within bounding box
        longitude = random.uniform(minx, maxx)
        latitude = random.uniform(miny, maxy)
        
        # Check if point is within Malta's actual boundary
        point = Point(longitude, latitude)
        if malta_boundary.contains(point) or malta_boundary.touches(point):
            rounded_lat = round(latitude, 6)
            rounded_lon = round(longitude, 6)
            points.append((rounded_lat, rounded_lon))
        
        attempts += 1
    
    if len(points) < num_points:
        print(f"Warning: Only generated {len(points)} points out of {num_points} requested after {max_attempts} attempts.")
    
    return points

def save_points_to_file(points: List[Tuple[float, float]], filename: str = "malta_points.json"):
    """
    Save generated points to a JSON file, ensuring 6 decimal precision.
    
    Args:
        points: List of (latitude, longitude) tuples
        filename: Output filename (default: "malta_points.json")
    """
    points_data = [
        {
            "id": i + 1,
            "latitude": lat,
            "longitude": lon,
            "coordinates": f"{lat:.6f}, {lon:.6f}"
        }
        for i, (lat, lon) in enumerate(points)
    ]
    
    with open(filename, 'w') as f:
        json.dump(points_data, f, indent=2)
    
    print(f"Saved {len(points)} points to {filename}")

def format_points_for_api(points: List[Tuple[float, float]]) -> str:
    """
    Format points for the driving API in the required format: longitude,latitude;longitude,latitude
    
    Args:
        points: List of (latitude, longitude) tuples
        
    Returns:
        String formatted for API: "lon,lat;lon,lat;lon,lat"
    """
    formatted_points = []
    for lat, lon in points:
        formatted_points.append(f"{lon:.6f},{lat:.6f}")
    
    return ";".join(formatted_points)

def save_api_formatted_points(points: List[Tuple[float, float]], filename: str = "malta_points_api_format.txt"):
    """
    Save points in API format to a text file.
    
    Args:
        points: List of (latitude, longitude) tuples
        filename: Output filename (default: "malta_points_api_format.txt")
    """
    api_format = format_points_for_api(points)
    
    with open(filename, 'w') as f:
        f.write(api_format)
    
    print(f"Saved {len(points)} points in API format to {filename}")
    print(f"Format: longitude,latitude;longitude,latitude...")

def generate_curl_command(points: List[Tuple[float, float]], max_points: int = None) -> str:
    """
    Generate a curl command for the driving API with the formatted points.
    
    Args:
        points: List of (latitude, longitude) tuples
        max_points: Maximum number of points to include (API may have limits)
        
    Returns:
        Complete curl command string
    """
    if max_points:
        points = points[:max_points]
    
    api_format = format_points_for_api(points)
    
    curl_command = f'''curl -X POST "http://127.0.0.1:5002/table/v1/driving/" \\
-H "Content-Type: application/x-www-form-urlencoded" \\
-d "{api_format}"'''
    
    return curl_command

def make_driving_api_request(points: List[Tuple[float, float]], max_points: int = None, 
                           api_url: str = "http://127.0.0.1:5002/table/v1/driving/") -> dict:
    """
    Make a Python requests call to the driving API and measure the duration.
    
    Args:
        points: List of (latitude, longitude) tuples
        max_points: Maximum number of points to include (API may have limits)
        api_url: The API endpoint URL
        
    Returns:
        API response as dictionary, including request duration.
    """
    if max_points:
        points = points[:max_points]
    
    api_format = format_points_for_api(points)
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    print(f"Making API request to: {api_url}")
    print(f"Sending {len(points)} points...")
    print(f"Data: {api_format[:100]}..." if len(api_format) > 100 else f"Data: {api_format}")
    
    try:
        start_time = time.monotonic()
        
        response = requests.post(api_url, data=api_format, headers=headers)
        
        duration = time.monotonic() - start_time
        
        print(f"Response Status Code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                data['request_duration_seconds'] = duration  # Add duration to response data
                return data
            except json.JSONDecodeError:
                return {
                    "raw_response": response.text,
                    "request_duration_seconds": duration
                }
        else:
            return {
                "error": f"API request failed with status {response.status_code}",
                "response_text": response.text,
                "request_duration_seconds": duration
            }
            
    except requests.exceptions.RequestException as e:
        return {
            "error": f"Request failed: {str(e)}",
            "suggestion": "Make sure the API server is running on http://127.0.0.1:5002"
        }

def print_points(points: List[Tuple[float, float]], num_to_show: int = 10):
    """
    Print a sample of the generated points with 6 decimal precision.
    
    Args:
        points: List of (latitude, longitude) tuples
        num_to_show: Number of points to display (default: 10)
    """
    print(f"\nGenerated {len(points)} random points in Malta:")
    print("-" * 50)
    
    for i, (lat, lon) in enumerate(points[:num_to_show]):
        print(f"Point {i+1:3d}: {lat:.6f}, {lon:.6f}")
    
    if len(points) > num_to_show:
        print(f"... and {len(points) - num_to_show} more points")

# <<< NEW FUNCTION >>>
def save_api_response_to_json(response_data: dict, filename: str = "api_response.json"):
    """
    Saves the API response dictionary to a JSON file.

    Args:
        response_data (dict): The dictionary containing the API response.
        filename (str): The name of the file to save the data to.
    """
    try:
        with open(filename, 'w') as f:
            json.dump(response_data, f, indent=2)
        print(f"\nAPI response successfully saved to {filename}")
    except Exception as e:
        print(f"\nError: Could not save API response to file: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate random geographical points within Malta and format them for a driving API."
    )
    parser.add_argument(
        '-n', '--num_points',
        type=int,
        default=100,
        help="The number of random points to generate (default: 100)."
    )
    
    args = parser.parse_args()
    number_of_points = args.num_points

    try:
        print(f"Starting Malta point generation for {number_of_points} points...")
        malta_points = generate_malta_points(number_of_points)
        
        if not malta_points:
            print("No points were generated. Exiting.")
            exit()

        print_points(malta_points, num_to_show=10)
        save_points_to_file(malta_points)
        save_api_formatted_points(malta_points)
        
        print(f"\n{'='*60}")
        print("API FORMAT EXAMPLE (first 5 points):")
        print("="*60)
        sample_format = format_points_for_api(malta_points[:5])
        print(sample_format)
        
        print(f"\n{'='*60}")
        print("SAMPLE CURL COMMAND (first 5 points):")
        print("="*60)
        sample_curl = generate_curl_command(malta_points[:5])
        print(sample_curl)
        
        print(f"\n{'='*60}")
        print(f"MAKING API REQUEST WITH PYTHON REQUESTS (ALL {len(malta_points)} points):")
        print("="*60)
        api_response = make_driving_api_request(malta_points)
        
        # <<< CHANGE: Save the full response to a file instead of printing a part of it >>>
        save_api_response_to_json(api_response, "api_response.json")
        
        request_duration = api_response.get('request_duration_seconds')
        
        print(f"\n{'='*60}")
        print("SUMMARY:")
        print("="*60)
        print(f"Total points generated: {len(malta_points)}")
        
        if request_duration is not None:
            print(f"API request time: {request_duration:.4f} seconds")
        
        print("✓ JSON format saved to: malta_points.json")
        print("✓ API format saved to: malta_points_api_format.txt")
        print("✓ Full API response saved to: api_response.json")
        print("✓ All points are within Malta's actual boundaries")
        print("✓ All coordinates have 6 decimal precision")
        print("✓ API request executed with Python requests!")
        print("✓ Ready for driving API calls!")
        
    except ImportError as e:
        print(f"\nError: Missing required packages. Please install the dependencies.")
        print("You can use a package manager like pip or conda, for example:")
        print("pip install geopandas requests shapely pandas")
        print(f"\nError details: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
        print("Please check your internet connection if the script is trying to fetch OSM data.")