import streamlit as st
import asyncio
import os
import nest_asyncio
import atexit
from services.chat_service import init_session
from utils.async_helpers import on_shutdown
from apps import mcp_playground

# Apply nest_asyncio to allow nested asyncio event loops (needed for Streamlit's execution model)
nest_asyncio.apply()

LOGO_URL = "https://www.effectix.com/public/images/logo.svg?v=2"

st.set_page_config(
                   page_title="Effectix AI Playground",
                   page_icon=LOGO_URL,
                   layout='wide',
                   initial_sidebar_state="expanded"
                    )

def main():
    # Add logo to the sidebar
    st.sidebar.image(LOGO_URL, use_container_width=True)
    
    # Initialize session state for event loop
    if "loop" not in st.session_state:
        st.session_state.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(st.session_state.loop)
    
    # Register shutdown handler
    atexit.register(on_shutdown)
    
    # Initialize the primary application
    init_session()
    mcp_playground.main()

if __name__ == "__main__":
    main()