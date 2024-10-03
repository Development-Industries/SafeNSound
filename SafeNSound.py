import os
import time
import pandas as pd
import requests
import asyncio
from bleak import BleakScanner
from dronekit import connect, VehicleMode
from tkinter import Tk, Label, StringVar
from geopy.distance import geodesic
from colorama import Fore, Style

# Initialize colorama for colored warnings
import colorama
colorama.init(autoreset=True)

# --- Function to Get User Location (IP-Based Geolocation) ---
def get_user_location():
    """
    Fetches the user's current location (latitude, longitude) using the ipinfo.io API.
    This is a simple way to determine the user's location based on their IP address.
    """
    try:
        response = requests.get('https://ipinfo.io/json')
        data = response.json()
        loc = data['loc'].split(',')
        return float(loc[0]), float(loc[1])
    except Exception as e:
        print(f"Failed to retrieve location: {e}")
        return None, None  # Return None if unable to get location

# --- Function to Find Nearest Airports ---
def find_nearest_airports(user_lat, user_lon, airports, num_airports=5):
    """
    Finds the nearest airports to the user's location.
    - user_lat, user_lon: The user's latitude and longitude.
    - airports: The dataset of airports.
    - num_airports: The number of closest airports to return (default is 5).
    """
    airport_distances = []

    # Calculate the distance to each airport
    for airport in airports:
        airport_location = (airport['location'][0], airport['location'][1])
        distance = geodesic((user_lat, user_lon), airport_location).km
        airport_distances.append((airport, distance))

    # Sort the airports by distance
    airport_distances.sort(key=lambda x: x[1])

    # Return the closest airports (based on num_airports)
    return airport_distances[:num_airports]

# --- Tkinter HUD Setup ---
class HUD:
    def __init__(self, root):
        """
        Initializes the Tkinter window for the HUD display.
        - Creates labels for real-time telemetry data.
        - Creates labels for real-time weather data.
        - Creates labels for nearest airports based on user's location.
        """
        self.root = root
        self.root.title("Drone Telemetry, Weather, and Nearest Airports")
        self.root.geometry("800x600")

        # String variables that will dynamically display telemetry, weather, and airport data
        self.telemetry_label = StringVar()
        self.weather_label = StringVar()
        self.airport_label = StringVar()

        # Create labels for telemetry, weather, and airport data display
        Label(root, text="Telemetry Data", font=("Arial", 16)).pack(pady=10)
        Label(root, textvariable=self.telemetry_label, font=("Arial", 12), fg="blue").pack(pady=10)

        Label(root, text="Weather Data", font=("Arial", 16)).pack(pady=10)
        Label(root, textvariable=self.weather_label, font=("Arial", 12), fg="green").pack(pady=10)

        Label(root, text="Nearest Airports", font=("Arial", 16)).pack(pady=10)
        Label(root, textvariable=self.airport_label, font=("Arial", 12), fg="purple").pack(pady=10)

    # --- Telemetry Update Function ---
    def update_telemetry(self, vehicle):
        """
        Updates the telemetry information from the drone and displays it on the HUD.
        This includes:
        - Latitude and Longitude
        - Altitude (meters)
        - Ground Speed (m/s)
        - Battery level (%)
        - Current drone mode (e.g., AUTO, LOITER)
        """
        try:
            telemetry_data = self.get_telemetry_data(vehicle)
            telemetry_text = (
                f"Latitude: {telemetry_data['latitude']}\n"
                f"Longitude: {telemetry_data['longitude']}\n"
                f"Altitude: {telemetry_data['altitude']} meters\n"
                f"Ground Speed: {telemetry_data['ground_speed']} m/s\n"
                f"Battery: {telemetry_data['battery']}%\n"
                f"Mode: {telemetry_data['mode']}"
            )
            self.telemetry_label.set(telemetry_text)
        except Exception as e:
            # If any error occurs, display the error message in the telemetry section
            self.telemetry_label.set(f"Error fetching telemetry: {e}")

    # --- Weather Update Function ---
    def update_weather(self, lat, lon):
        """
        Updates the weather data using the Open-Meteo API and displays it on the HUD.
        This includes:
        - Temperature in Celsius and Fahrenheit
        - Wind Speed in m/s
        """
        weather_data = get_weather_data(lat, lon)
        if weather_data:
            current_weather = weather_data.get('current_weather', {})
            celsius = current_weather.get('temperature', "N/A")
            # Convert Celsius to Fahrenheit if valid data is available
            fahrenheit = (celsius * 9/5) + 32 if isinstance(celsius, (int, float)) else "N/A"
            wind_speed = current_weather.get('windspeed', "N/A")

            # Format the weather information for display
            weather_text = (
                f"Current Temperature: {celsius} C / {fahrenheit} F\n"
                f"Current Wind Speed: {wind_speed} m/s"
            )
            self.weather_label.set(weather_text)
        else:
            # If weather data is not available, display an error message
            self.weather_label.set("Failed to retrieve weather data.")

    # --- Airports Update Function ---
    def update_airports(self, user_lat, user_lon, airports):
        """
        Finds the nearest airports to the user's location and displays them on the HUD.
        - Displays the 5 nearest airports.
        """
        nearest_airports = find_nearest_airports(user_lat, user_lon, airports)
        airport_text = "Nearest Airports:\n"
        for airport, distance in nearest_airports:
            airport_text += (
                f"{airport['name']} ({airport['iata_code']}) - {distance:.2f} km\n"
            )
        self.airport_label.set(airport_text)

    # --- Fetch Telemetry Data Function ---
    def get_telemetry_data(self, vehicle):
        """
        Retrieves real-time telemetry data from the drone using DroneKit.
        - This returns a dictionary with fields:
        - latitude, longitude, altitude, ground speed, battery level, and mode
        """
        telemetry = {
            "latitude": vehicle.location.global_frame.lat,
            "longitude": vehicle.location.global_frame.lon,
            "altitude": vehicle.location.global_frame.alt,
            "ground_speed": vehicle.groundspeed,
            "battery": vehicle.battery.level,
            "mode": vehicle.mode.name
        }
        return telemetry

# --- Fetch Weather Data from Open-Meteo ---
def get_weather_data(lat, lon):
    """
    Fetches current weather data from the Open-Meteo API based on latitude and longitude.
    - Uses a public API and returns the current temperature (Celsius), wind speed (m/s),
      and other relevant weather data.
    """
    weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&hourly=temperature_2m,wind_speed_10m,relative_humidity_2m"
    response = requests.get(weather_url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to retrieve weather data: {response.status_code}")
        return None

# --- Main Execution ---
if __name__ == '__main__':
    try:
        # Load the airports dataset from OpenFlights
        airport_url = 'https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat'
        airport_columns = ["Airport ID", "Name", "City", "Country", "IATA", "ICAO", "Latitude", "Longitude", "Altitude", "Timezone", "DST", "Tz database time zone", "Type", "Source"]
        airports_df = pd.read_csv(airport_url, header=None, names=airport_columns)
        airports = [
            {
                "name": row["Name"],
                "iata_code": row["IATA"],
                "location": (float(row["Latitude"]), float(row["Longitude"]))
            } 
            for _, row in airports_df.iterrows()
        ]

        # Initialize Tkinter for the graphical HUD
        root = Tk()
        hud = HUD(root)

        # Get the user's current location (latitude, longitude)
        user_lat, user_lon = get_user_location()
        if user_lat and user_lon:
            print(f"User's location: Latitude {user_lat}, Longitude {user_lon}")
        else:
            raise Exception("Unable to determine user's location.")

        # Connect to the drone using DroneKit (replace the IP/port with your specific drone's address)
        vehicle = connect('127.0.0.1:14550', wait_ready=True)  # Replace with the drone's IP or serial port
        
        # Function to update telemetry, weather, and airports periodically
        def update():
            # Update telemetry data from the drone
            hud.update_telemetry(vehicle)

            # Update weather data for user's location
            hud.update_weather(user_lat, user_lon)

            # Update the nearest airports based on user's location
            hud.update_airports(user_lat, user_lon, airports)

            # Set the update interval to every 5 seconds
            root.after(5000, update)

        # Start the periodic updates
        update()

        # Run the Tkinter main loop (for the HUD display)
        root.mainloop()

    except Exception as e:
        print(f"Error: {e}")
