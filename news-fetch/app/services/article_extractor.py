import logging
import re
from typing import Optional, Tuple
import httpx
import trafilatura
from bs4 import BeautifulSoup

try:
    from curl_cffi.requests import AsyncSession as CurlAsyncSession
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

from app.models.documents.article import ArticleDocument

logger = logging.getLogger("news_pipeline.extractor")

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
}

BLOCK_SIGNATURES = [
    "the request is blocked",
    "access denied",
    "cloudflare ray id",
    "attention required! | cloudflare",
    "verify you are human",
    "security check to access",
    "bot detection",
    "service unavailable",
    "enable cookies to continue",
]


class ArticleExtractor:
    """
    Extracts the exact substantive text of a news article from its URL,
    filtering out navigation, headers, ads, footers, and sidebars.
    Supports browser TLS impersonation via curl_cffi with httpx fallback.
    """

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    async def fetch_html(self, url: str) -> Optional[str]:
        """
        Fetches HTML string asynchronously using curl_cffi (impersonate='chrome120')
        with httpx fallback.
        """
        # 1. Try curl_cffi with Chrome TLS fingerprint impersonation
        if HAS_CURL_CFFI:
            try:
                async with CurlAsyncSession(impersonate="chrome120", timeout=self.timeout) as session:
                    resp = await session.get(url, headers=DEFAULT_HEADERS)
                    if resp.status_code == 200:
                        return resp.text
                    else:
                        logger.debug(f"curl_cffi HTTP {resp.status_code} on {url}")
            except Exception as e:
                logger.debug(f"curl_cffi fetch notice on {url}: {e}")

        # 2. Fallback to standard httpx client
        try:
            async with httpx.AsyncClient(
                headers=DEFAULT_HEADERS,
                timeout=self.timeout,
                follow_redirects=True,
            ) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.text
                else:
                    logger.debug(f"httpx HTTP {resp.status_code} on {url}")
                    return None
        except Exception as e:
            logger.debug(f"httpx fetch notice on {url}: {e}")
            return None

    def is_block_page(self, text: str) -> bool:
        """Detects if extracted text is a WAF / CAPTCHA / 403 block page rather than news."""
        if not text:
            return True
        lower = text.lower()
        if len(text.strip()) < 400:
            for sig in BLOCK_SIGNATURES:
                if sig in lower:
                    return True
        return False

    def extract_clean_content(self, html: str, url: Optional[str] = None) -> Optional[str]:
        """
        Extracts clean article body text from HTML.
        Strips ads, navbars, sidebars, scripts, and footers.
        """
        if not html or len(html.strip()) < 50:
            return None

        # 1. Primary extraction with trafilatura (industry-standard precision)
        try:
            extracted = trafilatura.extract(
                html,
                url=url,
                include_comments=False,
                include_tables=False,
                include_links=False,
                include_images=False,
                no_fallback=False,
                deduplicate=True,
            )
            if extracted and len(extracted.strip()) >= 150:
                clean = self._clean_text(extracted)
                if not self.is_block_page(clean):
                    return clean
        except Exception as e:
            logger.debug(f"Trafilatura extraction notice: {e}")

        # 2. Fallback extraction with BeautifulSoup
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Remove unwanted noise elements
            for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "noscript", "svg"]):
                tag.decompose()

            # Search for typical article containers
            container = (
                soup.find("article")
                or soup.find("main")
                or soup.find("div", {"role": "main"})
                or soup.find("div", class_=re.compile(r"(article[-_]?body|story[-_]?content|post[-_]?body)", re.I))
            )

            target = container if container else soup.body
            if not target:
                return None

            paragraphs = target.find_all("p")
            clean_paras = []
            for p in paragraphs:
                txt = p.get_text(separator=" ", strip=True)
                if len(txt) > 30 and not re.search(r"^(copyright|subscribe|sign up|advertisement)", txt, re.I):
                    clean_paras.append(txt)

            if clean_paras:
                full_text = "\n\n".join(clean_paras)
                if len(full_text.strip()) >= 150:
                    clean = self._clean_text(full_text)
                    if not self.is_block_page(clean):
                        return clean
        except Exception as e:
            logger.debug(f"BeautifulSoup fallback notice: {e}")

        return None

    def _clean_text(self, text: str) -> str:
        """Normalizes multiple blank lines and whitespace."""
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    async def extract_from_url(self, url: str) -> Tuple[Optional[str], int]:
        """
        Fetches HTML from URL and extracts clean article text.
        Returns: (extracted_text, word_count)
        """
        html = await self.fetch_html(url)
        if not html:
            return None, 0

        clean_text = self.extract_clean_content(html, url=url)
        if not clean_text:
            return None, 0

        word_count = len(clean_text.split())
        return clean_text, word_count


async def process_article_document(
    doc: ArticleDocument,
    extractor: ArticleExtractor,
) -> bool:
    """
    Fetches full article text for an ArticleDocument and updates MongoDB.
    If webpage is blocked or paywalled, falls back to stored description + snippet.
    """
    if not doc.url:
        return False

    text, word_count = await extractor.extract_from_url(doc.url)
    if text and word_count >= 30:
        doc.full_text = text
        doc.content_extracted = True
        await doc.save()
        return True
    else:
        # Graceful fallback: synthesize full_text from NewsAPI description and snippet
        fallback_parts = [p for p in [doc.title, doc.description, doc.content] if p]
        doc.full_text = "\n\n".join(fallback_parts) if fallback_parts else doc.title
        doc.content_extracted = True
        await doc.save()
        return False
