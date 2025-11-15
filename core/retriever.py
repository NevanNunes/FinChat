"""RAG Retriever - Knowledge base retrieval using Chroma"""
import logging
from typing import List, Tuple
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import os
import re
from collections import Counter
from config import *

logger = logging.getLogger(__name__)

class Retriever:
    def __init__(self, docs_path: str = "data/static_docs", persist_dir: str = "chroma_db"):
        self.docs_path = docs_path
        self.persist_dir = persist_dir

        self.embeddings = None
        self.vectorstore = None
        self._documents_cache: List[Document] = []

        # Always try to initialize embeddings
        try:
            from langchain_huggingface import HuggingFaceEmbeddings

            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={"device": "cpu"}
            )
            logger.info("✓ Embeddings loaded successfully")
        except Exception as e:
            logger.warning(f"⚠️ Could not load embeddings: {e}")
            self._load_documents_to_cache()

        # Initialize or load vectorstore
        if self.embeddings:
            self._initialize_vectorstore()

    def _initialize_vectorstore(self) -> None:
        """Initialize or load vector store with PROPER rebuild checks"""
        # Check if we should load existing DB
        if self._should_load_existing_db():
            try:
                logger.info("Loading existing Chroma DB...")
                self.vectorstore = Chroma(
                    persist_directory=self.persist_dir,
                    embedding_function=self.embeddings
                )

                # CRITICAL: Verify the DB actually works
                try:
                    test_results = self.vectorstore.similarity_search("test", k=1)
                    if test_results:
                        logger.info("✓ Loaded Chroma DB successfully (verified)")
                        return
                    else:
                        logger.warning("⚠️ Existing DB appears empty, rebuilding...")
                except Exception as e:
                    logger.warning(f"⚠️ Existing DB verification failed: {e}, rebuilding...")

            except Exception as e:
                logger.warning(f"⚠️ Failed to load existing DB: {e}, rebuilding...")

        # Build new vectorstore if needed
        if self.embeddings:
            self._build_vectorstore()
        else:
            self._load_documents_to_cache()

    def _should_load_existing_db(self) -> bool:
        """Check if we should load existing DB instead of rebuilding

        CRITICAL FIX: Only load if ALL required files exist
        """
        if not os.path.exists(self.persist_dir):
            logger.debug("Persist directory doesn't exist")
            return False

        # Check if directory has content
        if not os.listdir(self.persist_dir):
            logger.debug("Persist directory is empty")
            return False

        # CRITICAL: Check for chroma.sqlite3 (required file)
        chroma_db = os.path.join(self.persist_dir, 'chroma.sqlite3')
        if not os.path.exists(chroma_db):
            logger.debug("chroma.sqlite3 not found, need to rebuild")
            return False

        logger.debug("✓ All required DB files exist")
        return True

    def _build_vectorstore(self) -> None:
        """Build vector store from documents with optimized chunking"""
        logger.info("Building Chroma DB from documents...")
        documents = []

        # Load documents from static_docs directory
        if os.path.exists(self.docs_path):
            for filename in os.listdir(self.docs_path):
                if filename.endswith('.txt'):
                    file_path = os.path.join(self.docs_path, filename)
                    try:
                        loader = TextLoader(file_path, encoding='utf-8')
                        documents.extend(loader.load())
                        logger.debug(f"Loaded {filename}")
                    except Exception as e:
                        logger.error(f"Failed to load {filename}: {e}")

        # Fallback: create default knowledge if no docs exist
        if not documents:
            logger.info("No documents found, using default knowledge...")
            documents = self._create_default_knowledge()

        # Split documents with optimized chunking from config
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP
        )
        splits = text_splitter.split_documents(documents)

        logger.info(f"Creating {len(splits)} chunks...")

        # Create vectorstore
        self.vectorstore = Chroma.from_documents(
            documents=splits,
            embedding=self.embeddings,
            persist_directory=self.persist_dir
        )
        logger.info(f"✓ Built and persisted Chroma DB with {len(splits)} chunks")

    def _load_documents_to_cache(self) -> None:
        """Load documents into cache for keyword retrieval (fallback)"""
        documents = []
        if os.path.exists(self.docs_path):
            for filename in os.listdir(self.docs_path):
                if filename.endswith('.txt'):
                    file_path = os.path.join(self.docs_path, filename)
                    try:
                        loader = TextLoader(file_path, encoding='utf-8')
                        documents.extend(loader.load())
                    except Exception as e:
                        logger.error(f"Failed to load {filename}: {e}")

        if not documents:
            documents = self._create_default_knowledge()

        self._documents_cache = documents
        logger.info(f"✓ Loaded {len(documents)} documents to cache")

    def _create_default_knowledge(self) -> List[Document]:
        """Create default financial knowledge base"""
        default_content = """
# Financial Investment Basics

## SIP (Systematic Investment Plan)
A SIP is a method of investing a fixed amount regularly in mutual funds. It helps in rupee cost averaging and disciplined investing.

Benefits:
- Disciplined investing
- Rupee cost averaging
- Compound growth
- Lower risk through averaging

## Mutual Funds
Mutual funds pool money from investors to invest in diversified portfolios.

Types:
- Large Cap: Invest in top 100 companies by market cap
- Mid Cap: Invest in companies ranked 101-250
- Small Cap: Invest in companies ranked 251+
- ELSS: Tax-saving equity funds (80C benefit)
- Debt: Lower risk, invest in bonds
- Hybrid: Mix of equity and debt

## Stock Market Metrics

P/E Ratio (Price-to-Earnings):
- Valuation metric
- Lower P/E may indicate undervaluation
- Higher P/E may indicate growth expectations

Dividend Yield:
- Annual dividend as % of stock price
- Indicates income generation
- Higher yield = more income

## Tax Saving (Section 80C)
- ELSS mutual funds: Lock-in 3 years, tax benefit up to ₹1.5 lakh
- PPF: Lock-in 15 years, tax-free returns
- EPF: Employer contribution, tax-free

## Risk Appetite
- Aggressive: High equity (80-90%), suitable for young investors
- Moderate: Balanced (50-70% equity), suitable for middle-aged
- Conservative: Low equity (20-40%), suitable for near-retirement

## Retirement Planning
- Start early for compound growth
- Consider inflation (6-7% annually)
- Plan for 25-30 years post-retirement
- Diversify across equity and debt
"""
        return [Document(page_content=default_content, metadata={"source": "default_knowledge"})]

    def get_context(self, query: str, top_k: int = RAG_TOP_K) -> str:
        """Retrieve relevant context for query"""
        try:
            if self.vectorstore:
                # Use vector similarity search
                docs = self.vectorstore.similarity_search(query, k=top_k)
                context = "\n\n".join([doc.page_content for doc in docs])
                logger.debug(f"Retrieved {len(docs)} chunks from vectorstore")
                return context
            elif self._documents_cache:
                # Fallback: simple keyword matching
                return self._keyword_search(query, top_k)
            else:
                logger.warning("No retrieval method available")
                return ""
        except Exception as e:
            logger.error(f"Error retrieving context: {e}")
            return ""

    def _keyword_search(self, query: str, top_k: int = 3) -> str:
        """Simple keyword-based search fallback"""
        query_lower = query.lower()
        query_words = set(re.findall(r'\w+', query_lower))

        # Score documents by keyword overlap
        doc_scores = []
        for doc in self._documents_cache:
            content_lower = doc.page_content.lower()
            content_words = set(re.findall(r'\w+', content_lower))

            # Calculate overlap
            overlap = len(query_words & content_words)
            if overlap > 0:
                doc_scores.append((doc, overlap))

        # Sort by score and return top_k
        doc_scores.sort(key=lambda x: x[1], reverse=True)
        top_docs = [doc for doc, _ in doc_scores[:top_k]]

        context = "\n\n".join([doc.page_content for doc in top_docs])
        logger.debug(f"Retrieved {len(top_docs)} chunks using keyword search")
        return context
