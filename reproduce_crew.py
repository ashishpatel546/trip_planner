
import os
import sys
from textwrap import dedent

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from trip_planner.crew import TripPlanner
from dotenv import load_dotenv

def main():
    load_dotenv(override=True)
    
    print("Checking environment variables...")
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not found!")
        return
    else:
        print("OPENAI_API_KEY found")
        
    if not os.getenv("BRAVE_API_KEY"):
        print("BRAVE_API_KEY not found! Search might fail.")
    
    if not os.getenv("AMADEUS_API_KEY"):
        print("AMADEUS_API_KEY not found! Flight search might fail.")

    inputs = {
        'origin': 'London',
        'cities': 'Paris',
        'travel_dates': '2026-07-01 to 2026-07-03',
        'trip_days': '3',
        'interests': 'Art, Food',
        'tip_amount': '1000',
        'currency': 'USD',
        'travelers': 1
    }
    
    print("\nStarting CrewAI reproduction...")
    try:
        planner = TripPlanner()
        crew = planner.crew()
        result = crew.kickoff(inputs=inputs)
        print("\nCrew execution completed!")
        print(result)
    except Exception as e:
        print(f"\nCrew execution failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
