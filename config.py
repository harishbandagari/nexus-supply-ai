"""NexusSupply AI — Application Configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
VERSIONS_DIR = DATA_DIR / "versions"
DB_PATH = PROJECT_ROOT / "nexus_supply.db"
CHROMA_PERSIST_DIR = str(PROJECT_ROOT / "chroma_db")

# ── OpenAI ─────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# ── RAG Settings ───────────────────────────────────────────────────────
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
SIMILARITY_THRESHOLD = 0.35
TOP_K_RESULTS = 10

# ── Governance ─────────────────────────────────────────────────────────
MIN_CONFIDENCE_SCORE = 0.70
STALE_DATASET_DAYS = 30

# ── Dataset Version ───────────────────────────────────────────────────
CURRENT_DATASET_VERSION = "v1.0"
