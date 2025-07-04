import streamlit as st
from config import MODEL_OPTIONS
import traceback
from services.mcp_service import connect_to_mcp_servers, run_tool
from services.chat_service import create_chat, delete_chat
from utils.tool_schema_parser import extract_tool_parameters
from utils.async_helpers import reset_connection_state, run_async
import asyncio


def create_history_chat_container():
    history_container = st.sidebar.container(height=200, border=None)
    with history_container:
        chat_history_menu = [
                f"{chat['chat_name']}_::_{chat['chat_id']}"
                for chat in st.session_state["history_chats"]
            ]
        chat_history_menu = chat_history_menu[:50][::-1]
        
        if chat_history_menu:
            current_chat = st.radio(
                label="History Chats",
                format_func=lambda x: x.split("_::_")[0] + '...' if "_::_" in x else x,
                options=chat_history_menu,
                label_visibility="collapsed",
                index=st.session_state["current_chat_index"],
                key="current_chat"
            )
            
            if current_chat:
                st.session_state['current_chat_id'] = current_chat.split("_::_")[1]


def create_sidebar_chat_buttons():
    with st.sidebar:
        c1, c2 = st.columns(2)
        create_chat_button = c1.button(
            "New Chat", use_container_width=True, key="create_chat_button"
        )
        if create_chat_button:
            create_chat()
            st.rerun()

        delete_chat_button = c2.button(
            "Delete Chat", use_container_width=True, key="delete_chat_button"
        )
        if delete_chat_button and st.session_state.get('current_chat_id'):
            delete_chat(st.session_state['current_chat_id'])
            st.rerun()

def create_model_select_widget():
    params = st.session_state["params"]
    params['model_id'] = st.sidebar.selectbox('🔎 Choose model',
                               options=MODEL_OPTIONS.keys(),
                               index=0)
    
def create_provider_select_widget():
    params = st.session_state.setdefault('params', {})
    # Load previously selected provider or default to the first
    default_provider = params.get("model_id", list(MODEL_OPTIONS.keys())[0])
    default_index = list(MODEL_OPTIONS.keys()).index(default_provider)
    # Provider selector with synced state
    selected_provider = st.sidebar.selectbox(
        '🔎 Choose Provider',
        options=list(MODEL_OPTIONS.keys()),
        index=default_index,
        key="provider_selection",
        on_change=reset_connection_state
    )
    # Save new provider and its index
    if selected_provider:
        params['model_id'] = selected_provider
        params['provider_index'] = list(MODEL_OPTIONS.keys()).index(selected_provider)
        st.sidebar.success(f"Model: {MODEL_OPTIONS[selected_provider]}")

    # Dynamic input fields based on provider
    with st.sidebar.container():
        if selected_provider == "Bedrock":
            with st.expander("🔐 Bedrock Credentials", expanded=True):
                params['region_name'] = st.text_input("AWS Region", value=params.get('region_name'),key="region_name")
                params['aws_access_key'] = st.text_input("AWS Access Key", value=params.get('aws_access_key'), type="password", key="aws_access_key")
                params['aws_secret_key'] = st.text_input("AWS Secret Key", value=params.get('aws_secret_key'), type="password", key="aws_secret_key")
        else:
            with st.expander("🔐 API Key", expanded=True):
                params['api_key'] = st.text_input(f"{selected_provider} API Key", value=params.get('api_key'), type="password", key="api_key")
    

def create_advanced_configuration_widget():
    params = st.session_state["params"]
    with st.sidebar.expander("⚙️  Basic config", expanded=False):
        params['max_tokens'] = st.number_input("Max tokens",
                                    min_value=1024,
                                    max_value=10240,
                                    value=4096,
                                    step=512,)
        params['temperature'] = st.slider("Temperature", 0.0, 1.0, step=0.05, value=1.0)
                
def create_mcp_connection_widget():
    with st.sidebar:
        st.subheader("Server Management")
        with st.expander(f"MCP Servers ({len(st.session_state.servers)})"):
            for name, config in st.session_state.servers.items():
                with st.container(border=True):
                    st.markdown(f"**Server:** {name}")
                    st.markdown(f"**URL:** {config['url']}")
                    if st.button(f"Remove {name}", key=f"remove_{name}"):
                        del st.session_state.servers[name]
                        st.rerun()

        if st.session_state.get("agent"):
            st.success(f"📶 Connected to {len(st.session_state.servers)} MCP servers!"
                       f" Found {len(st.session_state.tools)} tools.")
            if st.button("Disconnect to MCP Servers"):
                with st.spinner("Connecting to MCP servers..."):
                    try:
                        reset_connection_state()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error disconnecting to MCP servers: {str(e)}")
                        st.code(traceback.format_exc(), language="python")
        else:
            st.warning("⚠️ Not connected to MCP server")
            if st.button("Connect to MCP Servers"):
                with st.spinner("Connecting to MCP servers..."):
                    try:
                        connect_to_mcp_servers()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error connecting to MCP servers: {str(e)}")
                        st.code(traceback.format_exc(), language="python")

def create_mcp_tools_widget():
    with st.sidebar:
        if st.session_state.tools:
            st.subheader("🧰 Available Tools")

            # Store selected tool in session state to persist
            if 'selected_tool_name' not in st.session_state:
                st.session_state.selected_tool_name = st.session_state.tools[0].name

            def on_tool_change():
                st.session_state.selected_tool_name = st.session_state.new_tool_selection
            
            selected_tool_name = st.selectbox(
                "Select a Tool",
                options=[tool.name for tool in st.session_state.tools],
                index=[tool.name for tool in st.session_state.tools].index(st.session_state.selected_tool_name),
                key="new_tool_selection",
                on_change=on_tool_change
            )

            # GA4 Property Selector
            if "ga" in selected_tool_name:
                with st.container(border=True):
                    st.write("**Google Analytics Property**")
                    if 'ga_accounts' not in st.session_state:
                        st.session_state.ga_accounts = []
                        try:
                            list_tool = next((t for t in st.session_state.tools if t.name == "list_ga_accounts"), None)
                            if list_tool:
                                with st.spinner("Loading GA Accounts..."):
                                    # Define and run an async function to fetch accounts
                                    async def fetch_ga_accounts():
                                        return await run_tool(list_tool, tool_input={})
                                    
                                    # Run the async function and store the result
                                    st.session_state.ga_accounts = asyncio.run(fetch_ga_accounts())
                            else:
                                st.warning("Could not find 'list_ga_accounts' tool.")
                        except Exception as e:
                            st.error(f"Failed to load GA accounts: {e}")

                    if st.session_state.ga_accounts:
                        # Check if the accounts data is valid
                        if isinstance(st.session_state.ga_accounts, list) and all(isinstance(acc, dict) for acc in st.session_state.ga_accounts):
                            options = {acc['property_id']: acc['display_name'] for acc in st.session_state.ga_accounts}
                            
                            # Set default if not set
                            if 'ga_property_id' not in st.session_state or st.session_state.ga_property_id not in options:
                                st.session_state.ga_property_id = list(options.keys())[0] if options else None

                            if st.session_state.ga_property_id:
                                def on_property_change():
                                    st.session_state.ga_property_id = st.session_state.new_ga_property_id

                                st.selectbox(
                                    "Select Property",
                                    options=list(options.keys()),
                                    format_func=lambda x: options[x],
                                    key="new_ga_property_id",
                                    on_change=on_property_change,
                                    index=list(options.keys()).index(st.session_state.ga_property_id)
                                )
                        else:
                            st.error("GA accounts data is not in the expected format.")
                            st.write(st.session_state.ga_accounts) # Display the problematic data
                    else:
                        st.write("No GA properties found or failed to load.")


            if selected_tool_name:
                selected_tool = next(
                    (tool for tool in st.session_state.tools if tool.name == selected_tool_name),
                    None
                )

                if selected_tool:
                    with st.container():
                        st.write("**Description:**")
                        st.write(selected_tool.description)

                        parameters = extract_tool_parameters(selected_tool)

                        if parameters:
                            st.write("**Parameters:**")
                            for param in parameters:
                                st.code(param)