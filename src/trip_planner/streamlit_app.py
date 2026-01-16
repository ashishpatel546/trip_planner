import streamlit as st
import requests
import time
import json
from datetime import datetime, timedelta

# API Configuration
API_BASE_URL = "http://localhost:8000/api/v1"
# Note: Make sure to run: uv run python -m uvicorn trip_planner.api_v2:app --reload --port 8000

# Page config
st.set_page_config(
    page_title="AI Trip Planner",
    page_icon="🌍",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #2E86AB;
        padding: 20px;
    }
    .stButton>button {
        width: 100%;
        background-color: #2E86AB;
        color: white;
    }
    .success-box {
        padding: 20px;
        border-radius: 10px;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
    }
</style>
""", unsafe_allow_html=True)

def check_api_health():
    """Check if API is running"""
    try:
        response = requests.get(f"{API_BASE_URL.replace('/api/v1', '')}/")
        return response.status_code == 200
    except:
        return False

def create_trip_plan(origin, cities, travel_dates, trip_days, interests, budget, currency="USD", travelers=1):
    """Create a new trip plan"""
    payload = {
        "origin": origin,
        "cities": cities,
        "travel_dates": travel_dates,
        "trip_days": trip_days,
        "interests": interests,
        "tip_amount": budget,
        "currency": currency,
        "travelers": travelers
    }
    
    response = requests.post(f"{API_BASE_URL}/trips/plan", json=payload)
    return response.json()

def get_trip_status(request_id):
    """Get trip planning status"""
    response = requests.get(f"{API_BASE_URL}/trips/{request_id}/status")
    return response.json()

def get_trip_result(request_id):
    """Get completed trip plan"""
    response = requests.get(f"{API_BASE_URL}/trips/{request_id}/result")
    return response.json()

# Main App
st.markdown("<h1 class='main-header'>🌍 AI-Powered Trip Planner</h1>", unsafe_allow_html=True)

# Check API health
if not check_api_health():
    st.error("⚠️ API is not running. Please start the API server first: `uvicorn trip_planner.api:app --reload`")
    st.stop()

# Sidebar for input
with st.sidebar:
    st.header("📋 Trip Details")
    
    origin = st.text_input("📍 From City", placeholder="e.g., New York")
    
    cities = st.text_input("🏙️ Destination Cities", 
                          placeholder="e.g., Paris, Rome, Barcelona",
                          help="Comma-separated list of cities to consider")
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("📅 Start Date", 
                                   value=datetime.now() + timedelta(days=30))
    with col2:
        end_date = st.date_input("📅 End Date", 
                                value=datetime.now() + timedelta(days=37))
    
    travel_dates = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
    trip_days = str((end_date - start_date).days)
    
    interests = st.text_input("🎯 Interests", 
                             placeholder="e.g., food, culture, adventure",
                             help="What do you want to experience?")
    
    currency = st.selectbox(
        "💱 Currency",
        options=["USD", "INR"],
        index=0,
        help="Select your preferred currency for pricing"
    )
    
    currency_symbol = "$" if currency == "USD" else "₹"
    budget_label = f"💰 Budget ({currency_symbol} {currency})"
    budget_default = 1000 if currency == "USD" else 75000
    budget_step = 100 if currency == "USD" else 5000
    
    budget = st.number_input(budget_label, min_value=100, value=budget_default, step=budget_step)
    
    travelers = st.number_input("👥 Number of Travelers", min_value=1, max_value=20, value=1, step=1,
                               help="Total number of people traveling")
    
    st.markdown("---")
    
    plan_button = st.button("🚀 Plan My Trip", type="primary")

# Main content area
if plan_button:
    if not all([origin, cities, interests]):
        st.error("❌ Please fill in all required fields")
    else:
        with st.spinner("🔄 Creating your personalized trip plan..."):
            try:
                # Create trip plan
                response = create_trip_plan(
                    origin, cities, travel_dates, trip_days, interests, str(budget), currency, travelers
                )
                
                request_id = response["request_id"]
                st.session_state.request_id = request_id
                
                st.success(f"✅ Trip planning started! Request ID: {request_id}")
                
                # Poll for status
                progress_bar = st.progress(0)
                status_text = st.empty()
                details_expander = st.expander("📊 View detailed progress", expanded=True)
                details_container = details_expander.container()
                
                max_attempts = 60  # 5 minutes max
                attempt = 0
                last_progress_count = 0
                
                while attempt < max_attempts:
                    status = get_trip_status(request_id)
                    
                    # Update main status
                    status_emoji = "⏳" if status['status'] == 'processing' else "✅" if status['status'] == 'completed' else "❌"
                    status_text.info(f"{status_emoji} Status: {status['status'].upper()} - {status['progress']}")
                    
                    # Show detailed progress if available
                    if 'progress_details' in status and status['progress_details']:
                        progress_details = status['progress_details']
                        if len(progress_details) > last_progress_count:
                            # New progress items
                            with details_container:
                                for detail in progress_details[last_progress_count:]:
                                    agent_emoji = "🤖" if detail.get('agent') else "📌"
                                    st.markdown(f"{agent_emoji} **{detail.get('agent', 'System')}**: {detail.get('message', '')}")
                            last_progress_count = len(progress_details)
                    
                    status_text.info(f"{status_emoji} Status: {status['status'].upper()} - {status['progress']}")
                    
                    if status['status'] == 'completed':
                        progress_bar.progress(100)
                        break
                    elif status['status'] == 'failed':
                        st.error(f"❌ Trip planning failed: {status['progress']}")
                        break
                    
                    progress_bar.progress(min((attempt + 1) * 2, 90))
                    time.sleep(5)
                    attempt += 1
                
                if status['status'] == 'completed':
                    result = get_trip_result(request_id)
                    st.session_state.trip_result = result
                    
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

# Display result if available
if 'trip_result' in st.session_state:
    st.markdown("---")
    st.markdown("## 📖 Your Personalized Trip Plan")
    
    result = st.session_state.trip_result
    
    # Tabs for different views
    tab1, tab2 = st.tabs(["📋 Full Itinerary", "💾 Download"])
    
    with tab1:
        if result['result']['raw_output']:
            # Render markdown properly
            st.markdown(result['result']['raw_output'], unsafe_allow_html=False)
    
    with tab2:
        st.download_button(
            label="⬇️ Download Trip Plan (Markdown)",
            data=result['result']['raw_output'],
            file_name=f"trip_plan_{datetime.now().strftime('%Y%m%d')}.md",
            mime="text/markdown"
        )
        
        st.download_button(
            label="⬇️ Download Trip Plan (JSON)",
            data=json.dumps(result, indent=2),
            file_name=f"trip_plan_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json"
        )

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #888;'>
    <p>Powered by CrewAI + OpenAI | Built with ❤️ for travelers</p>
</div>
""", unsafe_allow_html=True)
