import logging
import os

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=f"{LOG_DIR}/activitate.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("elibrary_logger")

# --- ADAUGĂ LINIA ASTA AICI: ---
# Îi spunem lui SQLAlchemy să trimită în log doar avertismente sau erori, nu și interogările INFO
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)