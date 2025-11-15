"""Streamlit Frontend for Financial AI Assistant"""
import streamlit as st
import json
import logging
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from core.query_router import QueryRouter
from core.llm_engine import LLMEngine
from agents.market_data_agent import MarketDataAgent
from agents.user_profile import UserProfileManager
from core.retriever import Retriever
import yfinance as yf
import time

logger = logging.getLogger(__name__)

# Status checking functions
def check_llm_status() -> tuple[str, str]:
    """Check LLM connection status

    Returns:
        Tuple of (status, message) where status is 'connected', 'limited', or 'disconnected'
    """
    try:
        if st.session_state.get("llm_engine") is None:
            return "disconnected", "LLM Engine not initialized"

        # Quick test call with timeout
        test_response = st.session_state.llm_engine.generate(
            "test",
            json_mode=False,
            max_tokens=10
        )

        if test_response and len(test_response) > 0:
            return "connected", "LLM responding normally"
        else:
            return "limited", "LLM connection unstable"

    except Exception as e:
        logger.warning(f"LLM status check failed: {str(e)}")
        return "limited", f"Limited mode: {str(e)[:50]}"

def check_market_data_status() -> tuple[str, str]:
    """Check market data API status

    Returns:
        Tuple of (status, message) where status is 'online' or 'offline'
    """
    try:
        # Quick test with a known ticker
        test_ticker = yf.Ticker("RELIANCE.NS")
        hist = test_ticker.history(period="1d")

        if not hist.empty:
            return "online", "Yahoo Finance API responding"
        else:
            return "offline", "No data returned from Yahoo Finance"

    except Exception as e:
        logger.warning(f"Market data status check failed: {str(e)}")
        return "offline", f"Connection error: {str(e)[:50]}"

def update_system_status():
    """Update system status in session state"""
    llm_status, llm_msg = check_llm_status()
    market_status, market_msg = check_market_data_status()

    st.session_state.system_status = {
        "llm": {"status": llm_status, "message": llm_msg},
        "market_data": {"status": market_status, "message": market_msg},
        "last_updated": datetime.now().strftime("%H:%M:%S")
    }

# Page configuration
st.set_page_config(
    page_title="Financial AI Assistant",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styling
st.markdown("""
<style>
#root, .main {
    background: #f6f9ff;
}
.stTextInput>div>div>input {
    border-radius: 10px;
    border: 2px solid #4CAF50;
    padding: 12px;
    font-size: 16px;
}
.stButton>button {
    border-radius: 10px;
    background-color: #4CAF50;
    color: white;
    font-weight: bold;
    padding: 10px 24px;
    font-size: 16px;
    border: none;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
.stButton>button:hover {
    background-color: #45a049;
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
}
.chat-message {
    padding: 15px;
    border-radius: 10px;
    margin: 10px 0;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}
.user-message {
    background-color: #e3f2fd;
    border-left: 4px solid #2196F3;
}
.assistant-message {
    background-color: #e8f5e9;
    border-left: 4px solid #4CAF50;
    color: #1b5e20;
}
.success-box {
    background-color: #d4edda;
    border: 1px solid #c3e6cb;
    border-radius: 8px;
    padding: 15px;
    margin: 10px 0;
    color: #155724;
}
.error-box {
    background-color: #f8d7da;
    border: 1px solid #f5c6cb;
    border-radius: 8px;
    padding: 15px;
    margin: 10px 0;
    color: #721c24;
}
.disclaimer-box {
    background-color: #fff3cd;
    border: 2px solid #ffc107;
    border-radius: 10px;
    padding: 20px;
    margin: 15px 0;
    color: #856404;
    font-weight: 500;
    text-align: center;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
h1 {
    color: #1e3a8a;
    font-weight: 700;
}
h2 {
    color: #2563eb;
}
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "history" not in st.session_state:
    st.session_state.history = []

if "user_id" not in st.session_state:
    st.session_state.user_id = "user_1"

if "profile_manager" not in st.session_state:
    st.session_state.profile_manager = UserProfileManager()

if "llm_engine" not in st.session_state:
    # Try to initialize LLM engine with error handling
    try:
        st.session_state.llm_engine = LLMEngine()
        st.session_state.llm_status = "connected"
        logger.info("LLM Engine initialized successfully")
    except Exception as e:
        st.session_state.llm_engine = None
        st.session_state.llm_status = "disconnected"
        logger.warning(f"LLM Engine initialization failed: {str(e)}")
        # Show warning message (will be displayed in sidebar)
        st.session_state.llm_error = str(e)

if "router" not in st.session_state:
    # Initialize router with LLM engine (may be None if connection failed)
    st.session_state.router = QueryRouter(
        llm_engine=st.session_state.llm_engine,
        retriever=Retriever()
    )

# Header
st.markdown("<h1 style='text-align: center;'>💰 Financial AI Assistant</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 18px; color: #64748b;'>Real-time stocks, mutual funds, portfolios, SIP/EMI calculations</p>", unsafe_allow_html=True)
st.markdown("---")

# Disclaimer Box
st.markdown("""
<div class="disclaimer-box">
    ⚠️ <strong>DISCLAIMER:</strong> This is for educational purposes only. Not financial advice. 
    Please consult a SEBI-registered financial advisor before making investment decisions.
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings & Profile")

    # Initialize status checking on first run or if not checked in last 60 seconds
    if "system_status" not in st.session_state or \
       "last_status_check" not in st.session_state or \
       (time.time() - st.session_state.get("last_status_check", 0)) > 60:

        with st.spinner("Checking system status..."):
            update_system_status()
            st.session_state.last_status_check = time.time()

    # System Status Dashboard
    st.markdown("### 🔌 System Status")

    status_data = st.session_state.get("system_status", {})

    # LLM Status
    llm_info = status_data.get("llm", {})
    llm_status = llm_info.get("status", "unknown")
    llm_msg = llm_info.get("message", "Status unknown")

    if llm_status == "connected":
        st.markdown("**LLM Engine:** ✅ **Connected**")
        st.caption(llm_msg)
    elif llm_status == "limited":
        st.markdown("**LLM Engine:** ⚠️ **Limited Mode**")
        st.caption(llm_msg)
        with st.expander("🔧 Troubleshooting"):
            st.info("""
            **Limited Mode** means:
            - Data queries (stocks, mutual funds, SIP/EMI) work normally
            - Conversational AI features may be limited
            
            **To restore full functionality:**
            1. Start LM Studio
            2. Load a model (e.g., Mistral)
            3. Start the local server on port 1234
            4. Click "Refresh Status" below
            """)
    else:
        st.markdown("**LLM Engine:** ❌ **Disconnected**")
        st.caption(llm_msg)
        if "llm_error" in st.session_state:
            with st.expander("🔧 Connection Details"):
                st.error(f"Error: {st.session_state.llm_error}")
                st.info("""
                **To fix this:**
                1. Start LM Studio
                2. Load a model (e.g., Mistral)
                3. Start the local server
                4. Refresh this page
                
                **Note:** Data queries (stocks, mutual funds, SIP/EMI) will still work!
                """)

    # Market Data Status
    market_info = status_data.get("market_data", {})
    market_status = market_info.get("status", "unknown")
    market_msg = market_info.get("message", "Status unknown")

    if market_status == "online":
        st.markdown("**Market Data:** ✅ **Online**")
        st.caption(market_msg)
    else:
        st.markdown("**Market Data:** ❌ **Offline**")
        st.caption(market_msg)
        with st.expander("🔧 Troubleshooting"):
            st.warning("""
            **Market Data is offline:**
            - Check your internet connection
            - Verify Yahoo Finance is accessible
            - Some features may be limited
            
            **Affected features:**
            - Real-time stock prices
            - ETF data
            - Market indices
            """)

    # Last Updated timestamp
    last_updated = status_data.get("last_updated", "Never")
    st.caption(f"🕒 Last checked: {last_updated}")

    # Refresh Status button
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Refresh Status", use_container_width=True):
            with st.spinner("Checking..."):
                update_system_status()
                st.session_state.last_status_check = time.time()
                st.rerun()
    with col2:
        # Auto-refresh toggle
        auto_refresh = st.checkbox("Auto-refresh", value=False, help="Check status every 60 seconds")
        if auto_refresh:
            time.sleep(60)
            st.rerun()

    st.markdown("---")

    # User profile section
    st.subheader("User Profile")
    user_age = st.number_input("Age", min_value=18, max_value=100, value=30, step=1)
    user_income = st.number_input("Monthly Income (₹)", min_value=0, value=50000, step=1000)
    user_risk = st.selectbox("Risk Appetite", ["conservative", "moderate", "aggressive"])

    if st.button("Save Profile"):
        profile_data = {
            "age": user_age,
            "monthly_income": user_income,
            "risk_appetite": user_risk
        }
        st.session_state.profile_manager.create_profile(st.session_state.user_id, profile_data)
        st.success("✅ Profile saved!")

    st.markdown("---")

    # Chat history
    st.subheader("💬 Chat History")
    if st.button("🗑️ Clear History"):
        st.session_state.history = []
        st.rerun()

    # Display chat history in sidebar
    if st.session_state.history:
        for i, item in enumerate(reversed(st.session_state.history[-10:])):
            with st.expander(f"Q: {item['query'][:40]}...", expanded=False):
                st.write(f"**Query:** {item['query']}")
                st.write(f"**Response:** {item['response'][:100]}...")
    else:
        st.info("No chat history yet")

# Main input section
st.subheader("🔍 Ask me anything about finance")

# Example queries
with st.expander("📝 Example Queries"):
    st.markdown("""
    - **Stock Prices:** "Reliance stock price", "TCS share price"
    - **Metrics:** "P/E ratio of Infosys", "Dividend yield of ITC"
    - **Mutual Funds:** "Best large cap mutual funds", "Top ELSS funds"
    - **SIP:** "Calculate SIP 5000 for 10 years", "SIP 10000 for 15 years"
    - **EMI:** "EMI for 50 lakh loan at 8.5% for 20 years"
    - **Portfolio:** "Recommend portfolio for 2 lakh investment"
    - **Retirement:** "Retirement corpus for age 30, expense 50000"
    """)

query = st.text_input(
    "Your question:",
    placeholder="e.g., Reliance stock price, calculate SIP 5000 for 10 years, best large cap mutual funds...",
    key="query_input"
)

col1, col2, col3 = st.columns([1, 1, 4])
with col1:
    submit_button = st.button("🚀 Submit", use_container_width=True)
with col2:
    clear_button = st.button("🔄 Clear", use_container_width=True)

if clear_button:
    st.rerun()

# Process query
if submit_button and query:
    with st.spinner("🤔 Thinking..."):
        try:
            # Validate query is not empty after strip
            if not query.strip():
                st.warning("Please enter a valid query")
                st.stop()

            # Get response from router with error handling
            try:
                response = st.session_state.router.handle_query(query, st.session_state.user_id)
            except Exception as e:
                logger.error(f"Query handling error: {e}", exc_info=True)
                st.error(f"⚠️ Error processing your query: {str(e)}")
                st.stop()

            # Extract response and data
            summary = response.get("response", "No response generated")
            data = response.get("data", {})
            response_type = response.get("type", "conversational")

            # Add to history
            st.session_state.history.append({
                "query": query,
                "response": summary,
                "data": data,
                "type": response_type
            })

            # Save conversation to profile
            try:
                st.session_state.profile_manager.add_conversation(
                    st.session_state.user_id,
                    query,
                    summary
                )
            except Exception as e:
                logger.warning(f"Failed to save conversation: {e}")

            # Display results
            st.markdown("---")

            # Check for errors
            if "error" in data:
                st.markdown(f"""
                <div class="error-box">
                    <strong>⚠️ Error:</strong> {data['error']}
                </div>
                """, unsafe_allow_html=True)
            else:
                # Display assistant response
                st.markdown(f"""
                <div class="chat-message assistant-message">
                    <strong>🤖 Assistant:</strong><br>
                    {summary}
                </div>
                """, unsafe_allow_html=True)

                # Auto-render visualizations based on data type

                # 1. SIP Calculation Visualization
                if "monthly_sip" in data and "maturity_value" in data:
                    st.markdown("### 📊 SIP Investment Breakdown")

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("💰 Total Invested", f"₹{data['total_invested']:,.0f}")
                    with col2:
                        st.metric("🎯 Maturity Value", f"₹{data['maturity_value']:,.0f}")
                    with col3:
                        st.metric("📈 Gains", f"₹{data['gains']:,.0f}", f"{data.get('returns_percentage', 0)}%")

                    # Bar chart
                    fig = go.Figure(data=[
                        go.Bar(name='Total Invested', x=['Investment'], y=[data['total_invested']], marker_color='#3b82f6'),
                        go.Bar(name='Final Value', x=['Investment'], y=[data['maturity_value']], marker_color='#10b981'),
                        go.Bar(name='Gains', x=['Investment'], y=[data['gains']], marker_color='#f59e0b')
                    ])
                    fig.update_layout(
                        title="SIP Returns Breakdown",
                        barmode='group',
                        height=400,
                        template="plotly_white"
                    )
                    st.plotly_chart(fig, use_container_width=True)

                # 2. EMI Calculation Visualization
                elif "monthly_emi" in data and "total_interest" in data:
                    st.markdown("### 🏦 EMI Calculation Summary")

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("💳 Monthly EMI", f"₹{data['monthly_emi']:,.0f}")
                    with col2:
                        st.metric("💰 Total Payment", f"₹{data['total_payment']:,.0f}")
                    with col3:
                        st.metric("📊 Total Interest", f"₹{data['total_interest']:,.0f}")

                    # Pie chart: Principal vs Interest
                    fig = go.Figure(data=[go.Pie(
                        labels=['Principal', 'Interest'],
                        values=[data['loan_amount'], data['total_interest']],
                        marker_colors=['#3b82f6', '#ef4444'],
                        hole=.3
                    )])
                    fig.update_layout(
                        title="Loan Breakdown: Principal vs Interest",
                        height=400,
                        template="plotly_white"
                    )
                    st.plotly_chart(fig, use_container_width=True)

                # 3. Portfolio Recommendation Visualization
                elif "allocation" in data and isinstance(data["allocation"], dict):
                    st.markdown("### 🎯 Recommended Portfolio Allocation")

                    # Show profile info
                    if "profile" in data:
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Age", data["profile"].get("age", "N/A"))
                        with col2:
                            st.metric("Risk Profile", data["profile"].get("risk_appetite", "N/A").title())
                        with col3:
                            st.metric("Equity Allocation", f"{data['profile'].get('equity_allocation', 0)}%")

                    # Pie chart for allocation
                    allocation = data["allocation"]
                    labels = [k.replace("_", " ").title() for k in allocation.keys()]
                    values = [v * 100 for v in allocation.values()]

                    fig = go.Figure(data=[go.Pie(
                        labels=labels,
                        values=values,
                        marker_colors=['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'],
                        hole=.3
                    )])
                    fig.update_layout(
                        title="Asset Allocation (%)",
                        height=400,
                        template="plotly_white"
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    # Show recommended funds
                    if "recommended_funds" in data:
                        st.markdown("### 🏆 Top Recommended Funds")
                        for category, fund_data in data["recommended_funds"].items():
                            with st.expander(f"📁 {category.replace('_', ' ').title()} - ₹{fund_data.get('monthly_amount', 0):,.0f}/month"):
                                funds = fund_data.get("top_funds", [])
                                for i, fund in enumerate(funds[:3], 1):
                                    st.markdown(f"""
                                    **{i}. {fund.get('name', 'N/A')}**
                                    - NAV: ₹{fund.get('nav', 0)}
                                    - 1Y Returns: {fund.get('returns_1y', 0)}%
                                    - 3Y Returns: {fund.get('returns_3y', 0)}%
                                    - Fund House: {fund.get('fund_house', 'N/A')}
                                    """)

                # 4. Stock/ETF Data Visualization
                elif "symbol" in data and "price" in data:
                    st.markdown("### 📈 Stock/ETF Information")

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        change_color = "🟢" if data.get("change", 0) >= 0 else "🔴"
                        st.metric(
                            "Current Price",
                            f"₹{data['price']:,.2f}",
                            f"{change_color} {data.get('change', 0):+,.2f} ({data.get('change_percent', 0):+.2f}%)"
                        )
                    with col2:
                        st.metric("Day High", f"₹{data.get('day_high', 0):,.2f}")
                    with col3:
                        st.metric("Day Low", f"₹{data.get('day_low', 0):,.2f}")
                    with col4:
                        st.metric("Volume", f"{data.get('volume', 0):,}")

                    if data.get('dividend_yield', 0) > 0:
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Dividend Yield", f"{data.get('dividend_yield', 0):.2f}%")
                        with col2:
                            st.metric("Dividend Rate", f"₹{data.get('dividend_rate', 0):.2f}")
                        with col3:
                            st.metric("P/E Ratio", data.get('pe_ratio', 'N/A'))

                # 5. Multiple Stocks (Top Dividend, etc.)
                elif "stocks" in data and isinstance(data["stocks"], list):
                    st.markdown("### 📊 Stock Comparison")
                    for i, stock in enumerate(data["stocks"][:10], 1):
                        with st.expander(f"{i}. {stock.get('company', 'N/A')} ({stock.get('symbol', 'N/A')})"):
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.write(f"**Price:** ₹{stock.get('price', 0):,.2f}")
                                st.write(f"**Change:** {stock.get('change', 0):+.2f} ({stock.get('change_percent', 0):+.2f}%)")
                            with col2:
                                st.write(f"**Dividend Yield:** {stock.get('dividend_yield', 0):.2f}%")
                                st.write(f"**P/E Ratio:** {stock.get('pe_ratio', 'N/A')}")
                            with col3:
                                st.write(f"**Day High:** ₹{stock.get('day_high', 0):,.2f}")
                                st.write(f"**Day Low:** ₹{stock.get('day_low', 0):,.2f}")

                # 6. Mutual Funds List
                elif "funds" in data and isinstance(data["funds"], list):
                    st.markdown(f"### 🏆 Top {data.get('category', 'Mutual')} Funds")
                    for i, fund in enumerate(data["funds"], 1):
                        with st.expander(f"{i}. {fund.get('name', 'N/A')}"):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**NAV:** ₹{fund.get('nav', 0):.2f}")
                                st.write(f"**Fund House:** {fund.get('fund_house', 'N/A')}")
                            with col2:
                                st.write(f"**1Y Returns:** {fund.get('returns_1y', 0):.2f}%")
                                st.write(f"**3Y Returns:** {fund.get('returns_3y', 0):.2f}%")

                # 7. Retirement Corpus Calculation
                elif "corpus_needed" in data:
                    st.markdown("### 🏖️ Retirement Planning")

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("💰 Corpus Needed", f"₹{data['corpus_needed']:,.0f}")
                    with col2:
                        st.metric("📅 Years to Retirement", data.get('years_to_retirement', 'N/A'))
                    with col3:
                        st.metric("💳 Monthly SIP Required", f"₹{data.get('monthly_sip_required', 0):,.0f}")

                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Current Monthly Expense", f"₹{data.get('current_monthly_expense', 0):,.0f}")
                    with col2:
                        st.metric("Future Monthly Expense", f"₹{data.get('future_monthly_expense', 0):,.0f}")

                    # Show calculation breakdown if available
                    if "calculation_breakdown" in data:
                        st.markdown("---")
                        st.markdown("### 🧮 Calculation Breakdown")
                        st.markdown(f"""
                        **How we calculated the corpus of ₹{data['corpus_needed']:,.0f}:**
                        
                        **Assumptions:**
                        - Inflation Rate: **{data.get('inflation_rate', 0.06) * 100}%** per year
                        - Post-Retirement Period: **{data.get('post_retirement_years', 25)} years** (age {60}-{60 + data.get('post_retirement_years', 25)})
                        - Post-Retirement Returns: **{data.get('assumed_post_retirement_return', 0.04) * 100}%** per year (safe investments)
                        - SIP Expected Returns: **{data.get('assumed_sip_return', 0.12) * 100}%** per year
                        """)

                        breakdown = data['calculation_breakdown']

                        with st.expander("📊 Step-by-Step Calculation", expanded=True):
                            st.markdown(f"""
                            **Step 1: Years to Retirement**
                            - Current Age to Retirement Age = **{breakdown['step1_years_to_retirement']} years**
                            
                            **Step 2: Inflation Impact**
                            - Inflation Multiplier = (1 + 0.06)^{breakdown['step1_years_to_retirement']} = **{breakdown['step2_inflation_multiplier']}x**
                            - This means prices will be {breakdown['step2_inflation_multiplier']}x higher in {breakdown['step1_years_to_retirement']} years
                            
                            **Step 3: Future Monthly Expense**
                            - Current Expense × Inflation Multiplier
                            - ₹{data.get('current_monthly_expense', 0):,.0f} × {breakdown['step2_inflation_multiplier']} = **₹{breakdown['step3_future_monthly_expense']:,.0f}**
                            
                            **Step 4: Annual Expense at Retirement**
                            - Monthly Expense × 12
                            - ₹{breakdown['step3_future_monthly_expense']:,.0f} × 12 = **₹{breakdown['step4_annual_expense_at_retirement']:,.0f}**
                            
                            **Step 5: Total Needed for {data.get('post_retirement_years', 25)} Years**
                            - Annual Expense × {data.get('post_retirement_years', 25)} years
                            - ₹{breakdown['step4_annual_expense_at_retirement']:,.0f} × {data.get('post_retirement_years', 25)} = **₹{breakdown['step5_total_for_25_years']:,.0f}**
                            
                            **Step 6: Apply Discount Factor (Present Value)**
                            - Your money will continue earning {data.get('assumed_post_retirement_return', 0.04) * 100}% returns post-retirement
                            - Discount Factor = (1.04)^({data.get('post_retirement_years', 25)}/2) = **{breakdown['step6_discount_factor']}**
                            
                            **Step 7: Final Corpus Required**
                            - Total Needed ÷ Discount Factor
                            - ₹{breakdown['step5_total_for_25_years']:,.0f} ÷ {breakdown['step6_discount_factor']} = **₹{breakdown['step7_final_corpus']:,.0f}**
                            """)

                        # SIP Investment Breakdown
                        st.markdown("---")
                        st.markdown("### 💰 Investment Plan")

                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Monthly SIP", f"₹{data.get('monthly_sip_required', 0):,.0f}")
                        with col2:
                            st.metric("Total Investment", f"₹{data.get('total_sip_investment', 0):,.0f}")
                        with col3:
                            wealth_gain = data['corpus_needed'] - data.get('total_sip_investment', 0)
                            st.metric("Wealth Created", f"₹{wealth_gain:,.0f}", f"{(wealth_gain / data.get('total_sip_investment', 1)) * 100:.1f}%")

                        st.info(f"""
                        💡 **Summary:** To build a retirement corpus of ₹{data['corpus_needed']:,.0f}, you need to invest 
                        ₹{data.get('monthly_sip_required', 0):,.0f} per month for {data.get('years_to_retirement', 0)} years 
                        (assuming {data.get('assumed_sip_return', 0.12) * 100}% annual returns). Your total investment will be 
                        ₹{data.get('total_sip_investment', 0):,.0f}, creating wealth of ₹{wealth_gain:,.0f} through compounding!
                        """)

                # Expandable raw data viewer
                with st.expander("🔍 View Raw Data"):
                    st.json(data)

        except Exception as e:
            st.error(f"❌ An error occurred: {str(e)}")
            st.exception(e)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #64748b; padding: 20px;'>
    <p>💡 <strong>Powered by Yahoo Finance, MFApi, and Advanced AI</strong></p>
    <p style='font-size: 12px;'>Disclaimer: This is for educational purposes only. Please consult a financial advisor before making investment decisions.</p>
</div>
""", unsafe_allow_html=True)
