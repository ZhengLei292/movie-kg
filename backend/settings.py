"""Local configuration. The bundled database listens on loopback only."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URI = os.getenv('NEO4J_URI', 'bolt://127.0.0.1:17687')
USER = os.getenv('NEO4J_USER', 'neo4j')
PASSWORD = os.getenv('NEO4J_PASSWORD', '')
DATABASE = os.getenv('NEO4J_DATABASE', 'neo4j')
API_URL = os.getenv('MOVIEGRAPH_API', 'http://127.0.0.1:18080')

