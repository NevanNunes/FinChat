"""Configuration constants for the Financial AI Assistant"""

# ===== FINANCIAL CALCULATION DEFAULTS =====
DEFAULT_SIP_RETURN = 0.12           # 12% annual return
DEFAULT_EMI_INTEREST = 8.5          # 8.5% annual interest rate
DEFAULT_INFLATION = 0.06            # 6% inflation
DEFAULT_POST_RET_RETURN = 0.04      # 4% post-retirement return
DEFAULT_POST_RET_YEARS = 25         # 25 years post-retirement

# ===== CACHE SETTINGS =====
STOCK_CACHE_EXPIRY = 300            # 5 minutes for stock data
MF_CACHE_EXPIRY = 3600              # 1 hour for mutual fund data
NEGATIVE_CACHE_EXPIRY = 3600        # 1 hour for not-found stocks
PROFILE_CACHE_EXPIRY = 1800         # 30 minutes for user profiles

# ===== API SETTINGS =====
NSE_MAX_RETRIES = 2                 # Max retries for NSE API
NSE_BASE_DELAY = 0.5                # Base delay for exponential backoff
NSE_TIMEOUT = 5                     # Timeout in seconds for NSE API
YFINANCE_TIMEOUT = 8                # Timeout for Yahoo Finance

# ===== VALIDATION LIMITS =====
# SIP
SIP_MIN_AMOUNT = 100
SIP_MAX_AMOUNT = 1000000
SIP_MIN_YEARS = 1
SIP_MAX_YEARS = 50

# EMI
EMI_MIN_LOAN = 50000
EMI_MAX_LOAN = 100000000           # 10 crore
EMI_MIN_INTEREST = 1
EMI_MAX_INTEREST = 30
EMI_MIN_TENURE = 1
EMI_MAX_TENURE = 30

# Age
MIN_AGE = 18
MAX_AGE = 80
MIN_RETIREMENT_AGE = 30
MAX_RETIREMENT_AGE = 100

# Investment
MIN_INVESTMENT = 1000
MAX_INVESTMENT = 100000000         # 10 crore

# Expense
MIN_MONTHLY_EXPENSE = 1000
MAX_MONTHLY_EXPENSE = 1000000

# ===== LLM SETTINGS =====
LLM_MAX_TOKENS_QUERY = 300         # Max tokens for action detection
LLM_MAX_TOKENS_SUMMARY = 200       # Max tokens for summaries
LLM_MAX_TOKENS_CONVERSATION = 500  # Max tokens for conversation
LLM_TEMPERATURE_JSON = 0.3         # Temperature for JSON mode
LLM_TEMPERATURE_CHAT = 0.4         # Temperature for chat mode
LLM_MAX_HISTORY = 3                # Keep only last 3 conversation turns

# ===== RETRIEVER SETTINGS =====
CHUNK_SIZE = 400                   # Optimized chunk size for embeddings
CHUNK_OVERLAP = 100                # Overlap between chunks
RAG_TOP_K = 3                      # Number of chunks to retrieve

# ===== MUTUAL FUND SETTINGS =====
MF_TOP_FUNDS_LIMIT = 10            # Max funds to return in category queries
MF_SEARCH_MIN_SCORE = 70           # Minimum fuzzy match score

