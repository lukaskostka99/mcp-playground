import requests
from datetime import datetime, timedelta
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("Weather Service", host="0.0.0.0", port=8000)

@mcp.tool()
async def get_current_weather(location: str) -> str:
    """Get the current weather for a location.
    
    Args:
        location: The name of the city or location

    Returns:
        A string describing the current weather conditions
    """
    url = f"https://wttr.in/{location}?format=j1"  # JSON format
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        current = data['current_condition'][0]

        weather = {
            "temperature": current['temp_C'],
            "description": current['weatherDesc'][0]['value'],
            "humidity": current['humidity'],
            "wind_speed": current['windspeedKmph']
        }

        return weather

    except requests.exceptions.RequestException as err:
        return f"Request failed: {err}"
    except KeyError:
        return "Could not parse weather data."

@mcp.tool()
async def get_forecast(location: str, days: int = 3) -> str:
    """Get a weather forecast for a location.
    
    Args:
        location: The name of the city or location
        days: Number of days to forecast (default: 3)
    
    Returns:
        A string describing the weather forecast
    """
    url = f"https://wttr.in/{location}?format=j1"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        # Get the date N days from now
        target_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

        for day in data['weather']:
            if day['date'] == target_date:
                avg_temp = day['avgtempC']
                description = day['hourly'][4]['weatherDesc'][0]['value']  # Around mid-day
                humidity = day['hourly'][4]['humidity']
                wind_speed = day['hourly'][4]['windspeedKmph']

                return {
                    "date": target_date,
                    "temperature": avg_temp,
                    "description": description,
                    "humidity": humidity,
                    "wind_speed": wind_speed
                }

        return "No forecast found for that day."

    except requests.exceptions.RequestException as err:
        return f"Request failed: {err}"
    except KeyError:
        return "Could not parse forecast data."

if __name__ == "__main__":
    print("Starting Weather Service MCP server on port 8000...")
    print("Connect to this server using http://localhost:8000/sse")
    mcp.run(transport="sse")