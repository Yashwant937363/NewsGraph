import logging
import sys

def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    Configures structured and clean console logging for the pipeline.
    """
    log_format = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )

    # Mute noisy third-party loggers
    for noisy in ["httpx", "httpcore", "sentence_transformers", "urllib3", "transformers", "huggingface_hub"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logger = logging.getLogger("news_pipeline")
    return logger

logger = setup_logging()
