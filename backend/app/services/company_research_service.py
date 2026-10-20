"""
company_research_service.py

Free-tier company research for SecureHire.

This service does NOT use Gemini Google Search grounding.

Instead it:
1. Accepts a company name and optional website.
2. Fetches publicly accessible company web pages.
3. Extracts readable text from those pages.
4. Sends the collected source material to Gemini.
5. Gemini produces a structured company research report.

This is designed to work with the Gemini free tier without using
the paid Google Search grounding tool.
"""

import html
import ipaddress
import json
import logging
import os
import re
import socket
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, unquote, urljoin, urlparse
from urllib.request import Request, urlopen


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RESEARCH_MODEL_NAME = os.environ.get(
    "GEMINI_RESEARCH_MODEL",
    os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
)

MAX_PAGE_CHARS = 10000
MAX_TOTAL_SOURCE_CHARS = 30000
FETCH_TIMEOUT_SECONDS = 8
MAX_PAGES = 4

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "Chrome/131.0 Safari/537.36 "
    "SecureHireAI/1.0"
)


# ---------------------------------------------------------------------------
# Gemini research instructions
# ---------------------------------------------------------------------------

_RESEARCH_INSTRUCTIONS = """
You are a company research assistant for SecureHire AI.

You are given source material fetched from publicly accessible company
web pages. You MUST base your research only on the supplied source material.

This is NOT a fraud or scam assessment of a job posting.

It is independent research about the company itself.

Research and report on:

- Company overview in 2-3 sentences
- Official website
- Industry / sector
- Founded year, if supported by the sources
- Headquarters location, if supported
- Products or services
- Company size, if supported
- Online presence based on the supplied sources
- Careers/jobs presence
- Recent public information ONLY if present in the supplied sources
- Potential red flags or inconsistencies
- If a job title was supplied, whether the company's public presence
  appears consistent with that type of role
- Overall assessment in plain language

CRITICAL RULES:

1. DO NOT invent facts.

2. Only call something "verified" when it is directly supported by the
   supplied source material.

3. If the source material does not contain enough information, put the
   missing information in "unverifiable".

4. Do not use general knowledge to manufacture missing facts.

5. If the supplied website appears unrelated to the company name, mention
   the mismatch as a possible red flag.

6. Clearly separate:
   - verified_facts
   - ai_interpretation
   - unverifiable

7. Recent news should only be reported if it appears in the supplied
   source material.

8. The company name may be generic. If the supplied material does not
   confidently identify the company, say so instead of guessing.

Respond with ONLY one JSON object.

The JSON object MUST match this schema:

{
  "company_overview": "<2-3 sentence overview, or null>",
  "official_website": "<URL, or null>",
  "industry": "<industry/sector, or null>",
  "founded_year": "<year as a string, or null>",
  "headquarters": "<location, or null>",
  "products_services": "<short description, or null>",
  "company_size": "<employee count/scale, or null>",
  "online_presence": "<description, or null>",
  "careers_presence": "<description, or null>",
  "recent_public_info": "<recent relevant information, or null>",
  "red_flags": "<red flags or inconsistencies, or null>",
  "job_consistency_notes": "<assessment related to the job title, or null>",
  "overall_assessment": "<plain-language summary>",
  "verified_facts": ["<fact 1>", "<fact 2>"],
  "ai_interpretation": ["<interpretation 1>"],
  "unverifiable": ["<thing that could not be verified>"]
}
"""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SourceCitation:
    title: str | None
    url: str
    domain: str | None = None


@dataclass
class CompanyResearchResult:
    status: str

    company_name: str = ""

    company_overview: str | None = None
    official_website: str | None = None
    industry: str | None = None
    founded_year: str | None = None
    headquarters: str | None = None
    products_services: str | None = None
    company_size: str | None = None
    online_presence: str | None = None
    careers_presence: str | None = None
    recent_public_info: str | None = None
    red_flags: str | None = None
    job_consistency_notes: str | None = None
    overall_assessment: str | None = None

    verified_facts: list[str] = field(default_factory=list)
    ai_interpretation: list[str] = field(default_factory=list)
    unverifiable: list[str] = field(default_factory=list)

    sources: list[SourceCitation] = field(default_factory=list)

    llm_model: str | None = None
    error_message: str | None = None


# ---------------------------------------------------------------------------
# HTML text extraction
# ---------------------------------------------------------------------------

class _TextExtractor(HTMLParser):
    """
    Small dependency-free HTML-to-text extractor.
    """

    SKIP_TAGS = {
        "script",
        "style",
        "noscript",
        "svg",
        "template",
        "iframe",
    }

    def __init__(self):
        super().__init__()

        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self.SKIP_TAGS:
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() in self.SKIP_TAGS:
            if self.skip_depth > 0:
                self.skip_depth -= 1

    def handle_data(self, data):
        if self.skip_depth != 0:
            return

        text = html.unescape(data)
        text = re.sub(r"\s+", " ", text).strip()

        if text:
            self.parts.append(text)

    def get_text(self) -> str:
        return "\n".join(self.parts)


class _SearchLinkParser(HTMLParser):
    """Collect ordinary search-result links from DuckDuckGo's HTML page."""

    def __init__(self):
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        href = attrs.get("href", "")
        if "result__a" in classes and href:
            parsed = urlparse(href)
            if parsed.hostname and parsed.hostname.endswith("duckduckgo.com"):
                query = parse_qs(parsed.query)
                href = query.get("uddg", [href])[0]
            href = unquote(href)
            if href.startswith(("http://", "https://")) and href not in self.links:
                self.links.append(href)


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------

def _unavailable(
    internal_reason: str,
    user_message: str,
) -> CompanyResearchResult:
    logger.info(
        "Company research unavailable: %s",
        internal_reason,
    )

    return CompanyResearchResult(
        status="unavailable",
        error_message=user_message,
    )


def _error(
    internal_reason: str,
    user_message: str = "Company research is temporarily unavailable.",
) -> CompanyResearchResult:
    logger.warning(
        "Company research error: %s",
        internal_reason,
    )

    return CompanyResearchResult(
        status="error",
        error_message=user_message,
    )


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------

def _extract_json(raw_text: str) -> dict:
    """
    Extract a JSON object from Gemini's response.

    Handles:
    - Normal JSON
    - ```json ... ``` fenced JSON
    - Responses containing extra text around the JSON object
    """

    text = raw_text.strip()

    # Remove markdown code fences.
    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    # First attempt: direct JSON parsing.
    try:
        parsed = json.loads(text)

        if isinstance(parsed, dict):
            return parsed

    except json.JSONDecodeError:
        pass

    # Second attempt: locate the first JSON object.
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise json.JSONDecodeError(
            "No JSON object found",
            text,
            0,
        )

    candidate = text[start:end + 1]

    parsed = json.loads(candidate)

    if not isinstance(parsed, dict):
        raise json.JSONDecodeError(
            "Gemini response is not a JSON object",
            text,
            start,
        )

    return parsed


# ---------------------------------------------------------------------------
# SSRF protection
# ---------------------------------------------------------------------------

def _is_public_host(hostname: str) -> bool:
    """
    Basic SSRF protection.

    Rejects localhost, private IPs, loopback addresses, link-local
    addresses, multicast addresses, reserved addresses, and unspecified
    addresses.
    """

    if not hostname:
        return False

    hostname = hostname.lower().strip()

    blocked_names = {
        "localhost",
        "localhost.localdomain",
        "host.docker.internal",
    }

    if hostname in blocked_names:
        return False

    try:
        addresses = socket.getaddrinfo(
            hostname,
            None,
            type=socket.SOCK_STREAM,
        )

        for result in addresses:
            ip_string = result[4][0]

            ip = ipaddress.ip_address(ip_string)

            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
            ):
                return False

    except socket.gaierror:
        return False

    except Exception as exc:
        logger.info(
            "Could not validate host %s: %s",
            hostname,
            exc,
        )
        return False

    return True


# ---------------------------------------------------------------------------
# URL handling
# ---------------------------------------------------------------------------

def _normalize_website(
    url: str | None,
) -> str | None:
    """
    Normalize a supplied company URL.

    Supports normal URLs and LinkedIn safety redirect URLs.
    """

    if not url:
        return None

    url = url.strip()

    if not url:
        return None

    # Handle LinkedIn safety redirect URLs.
    try:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)

        redirected = query.get("url")

        if redirected:
            candidate = unquote(redirected[0])

            if candidate.startswith(
                ("http://", "https://")
            ):
                url = candidate

    except Exception:
        pass

    # Add HTTPS when the user supplied only a domain.
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        parsed = urlparse(url)

        if parsed.scheme not in {
            "http",
            "https",
        }:
            return None

        if not parsed.hostname:
            return None

        if not _is_public_host(parsed.hostname):
            return None

        return url

    except Exception:
        return None


# ---------------------------------------------------------------------------
# Web fetching
# ---------------------------------------------------------------------------

def _fetch_page(
    url: str,
) -> tuple[str | None, str | None]:
    """
    Fetch a public HTML page and extract readable text.

    Returns:
        (text, final_url)
    """

    try:
        parsed = urlparse(url)

        if parsed.scheme not in {
            "http",
            "https",
        }:
            return None, None

        if not parsed.hostname:
            return None, None

        if not _is_public_host(parsed.hostname):
            logger.info(
                "Rejected non-public URL: %s",
                url,
            )
            return None, None

        request = Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": (
                    "text/html,"
                    "application/xhtml+xml"
                ),
            },
        )

        with urlopen(
            request,
            timeout=FETCH_TIMEOUT_SECONDS,
        ) as response:

            content_type = (
                response.headers
                .get("Content-Type", "")
                .lower()
            )

            if (
                "text/html" not in content_type
                and "application/xhtml+xml"
                not in content_type
            ):
                return None, None

            final_url = response.geturl()

            # Validate the redirect destination too.
            final_parsed = urlparse(final_url)

            if not final_parsed.hostname:
                return None, None

            if not _is_public_host(
                final_parsed.hostname
            ):
                logger.info(
                    "Rejected unsafe redirect: %s -> %s",
                    url,
                    final_url,
                )
                return None, None

            # Limit downloaded data.
            raw = response.read(500_000)

            charset = (
                response.headers.get_content_charset()
                or "utf-8"
            )

            html_text = raw.decode(
                charset,
                errors="replace",
            )

            parser = _TextExtractor()

            parser.feed(html_text)

            text = parser.get_text()

            text = re.sub(
                r"\n{3,}",
                "\n\n",
                text,
            ).strip()

            if not text:
                return None, final_url

            return (
                text[:MAX_PAGE_CHARS],
                final_url,
            )

    except HTTPError as exc:
        logger.info(
            "HTTP error fetching %s: %s",
            url,
            exc,
        )

    except URLError as exc:
        logger.info(
            "URL error fetching %s: %s",
            url,
            exc,
        )

    except Exception as exc:
        logger.info(
            "Unexpected error fetching %s: %s",
            url,
            exc,
        )

    return None, None


# ---------------------------------------------------------------------------
# Candidate company pages
# ---------------------------------------------------------------------------

def _build_candidate_urls(
    base_url: str,
) -> list[str]:
    """
    Build a small list of likely useful company pages.
    """

    base_url = base_url.rstrip("/") + "/"

    paths = [
        "",
        "about",
        "about-us",
        "company",
        "careers",
        "jobs",
    ]

    urls: list[str] = []

    for path in paths:

        candidate = urljoin(
            base_url,
            path,
        )

        if candidate not in urls:
            urls.append(candidate)

        if len(urls) >= MAX_PAGES:
            break

    return urls


# ---------------------------------------------------------------------------
# Collect web sources
# ---------------------------------------------------------------------------

def _collect_web_sources(
    company_name: str,
    company_website: str | None,
) -> tuple[str, list[SourceCitation]]:

    normalized = _normalize_website(company_website)

    if normalized:
        candidate_urls = _build_candidate_urls(normalized)
    else:
        # Search by company name when the user has not supplied a website.
        # Search result links are fetched through _fetch_page(), which
        # rejects private/loopback hosts and unsafe redirect destinations.
        query_url = "https://html.duckduckgo.com/html/?" + urlencode({
            "q": f"{company_name} official website company careers"
        })
        candidate_urls = []
        try:
            request = Request(
                query_url,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
            )
            with urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
                search_html = response.read(500_000).decode("utf-8", errors="replace")
            parser = _SearchLinkParser()
            parser.feed(search_html)
            candidate_urls = parser.links[:MAX_PAGES]
        except Exception as exc:
            logger.info("Company web search failed for %s: %s", company_name, exc)

    if not candidate_urls:
        return "", []

    source_blocks: list[str] = []
    sources: list[SourceCitation] = []

    total_chars = 0

    for url in candidate_urls:

        if total_chars >= MAX_TOTAL_SOURCE_CHARS:
            break

        text, final_url = _fetch_page(url)

        if not text or not final_url:
            continue

        parsed = urlparse(final_url)

        domain = parsed.hostname

        title = (
            f"{company_name} public webpage"
        )

        block = (
            "\n\n===== SOURCE =====\n"
            f"URL: {final_url}\n"
            f"Domain: {domain or ''}\n"
            "CONTENT:\n"
            f"{text}\n"
            "===== END SOURCE =====\n"
        )

        remaining = (
            MAX_TOTAL_SOURCE_CHARS
            - total_chars
        )

        block = block[:remaining]

        source_blocks.append(block)

        sources.append(
            SourceCitation(
                title=title,
                url=final_url,
                domain=domain,
            )
        )

        total_chars += len(block)

    return (
        "".join(source_blocks),
        sources,
    )


# ---------------------------------------------------------------------------
# Main research function
# ---------------------------------------------------------------------------

def research_company(
    company_name: str | None,
    company_website: str | None = None,
    job_title: str | None = None,
) -> CompanyResearchResult:
    """
    Main entry point.

    Never intentionally raises an exception to the API layer.

    Returns a CompanyResearchResult with status:

        ok
        unavailable
        error
    """

    # ---------------------------------------------------------------
    # Validate company name
    # ---------------------------------------------------------------

    if not company_name or not company_name.strip():

        return _unavailable(
            "No company name was supplied.",
            "No company name was provided to research.",
        )

    company = company_name.strip()

    # ---------------------------------------------------------------
    # Collect public company website information first. Even when the
    # Gemini key is not configured, show the user which public pages
    # could be reached instead of presenting an empty dead-end panel.
    # ---------------------------------------------------------------

    source_material, sources = _collect_web_sources(
        company,
        company_website,
    )

    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        return CompanyResearchResult(
            status="partial",
            company_name=company,
            official_website=company_website or None,
            company_overview=(
                "AI-generated company summary is not available until "
                "GEMINI_API_KEY is configured. Public website links "
                "retrieved for this request are listed below."
            ),
            online_presence=(
                f"Retrieved {len(sources)} readable public page(s)."
                if sources else
                "No readable pages were retrieved. Enter the company's official website to try source retrieval."
            ),
            overall_assessment=(
                "This is a source-retrieval preview, not an AI verification "
                "or a finding that the company is safe. Configure Gemini "
                "to generate a sourced company report."
            ),
            unverifiable=[
                "Company legitimacy has not been assessed by AI.",
                "Company facts have not been independently verified.",
            ],
            sources=sources,
            error_message=(
                "Gemini is not configured. Add your own GEMINI_API_KEY "
                "to enable AI-generated company research."
            ),
        )

    # ---------------------------------------------------------------
    # Import current Gemini SDK
    # ---------------------------------------------------------------

    try:
        import google.genai as genai
        from google.genai import types
    except ImportError:
        return _unavailable(
            "google-genai package is not installed.",
            "Company research is not available for this deployment.",
        )

    if not source_material:
        return _unavailable(
            "No readable public company web pages could be fetched.",
            (
                "Could not access readable public information for this company. "
                "Please provide the company's official website and try again."
            ),
        )

    # ---------------------------------------------------------------
    # Build Gemini prompt
    # ---------------------------------------------------------------

    prompt_parts = [
        _RESEARCH_INSTRUCTIONS,
        f"\nCompany name: {company}",
        "\nPUBLIC WEB SOURCE MATERIAL:",
        source_material,
    ]

    if company_website:

        prompt_parts.append(
            "\nUser-supplied website: "
            f"{company_website.strip()}"
        )

    if job_title:

        prompt_parts.append(
            "\nJob context: "
            "The company was listed as the employer "
            f"for a '{job_title}' job posting."
        )

    prompt = "\n".join(prompt_parts)

    # ---------------------------------------------------------------
    # Call Gemini
    # ---------------------------------------------------------------

    try:

        client = genai.Client(
            api_key=api_key
        )

        response = client.models.generate_content(
            model=RESEARCH_MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )

        raw_text = response.text

    except Exception as exc:

        return _error(
            f"Gemini company research call failed: {exc}"
        )

    # ---------------------------------------------------------------
    # Empty Gemini response
    # ---------------------------------------------------------------

    if not raw_text:

        return _error(
            "Gemini returned an empty response.",
            (
                "Company research returned no result. "
                "Please try again."
            ),
        )

    # ---------------------------------------------------------------
    # Parse Gemini JSON
    # ---------------------------------------------------------------

    try:

        parsed = _extract_json(
            raw_text
        )

    except (
        json.JSONDecodeError,
        AttributeError,
    ) as exc:

        logger.info(
            "Company research response was not valid JSON: %s",
            exc,
        )

        return CompanyResearchResult(
            status="ok",
            company_name=company,
            overall_assessment=(
                raw_text.strip()[:2000]
            ),
            unverifiable=[
                (
                    "Structured fields could not be parsed "
                    "from the Gemini response. See overall "
                    "assessment for the returned research."
                )
            ],
            sources=sources,
            llm_model=RESEARCH_MODEL_NAME,
        )

    # ---------------------------------------------------------------
    # Normalize list fields safely
    # ---------------------------------------------------------------

    verified_facts = parsed.get(
        "verified_facts"
    )

    if not isinstance(
        verified_facts,
        list,
    ):
        verified_facts = []

    ai_interpretation = parsed.get(
        "ai_interpretation"
    )

    if not isinstance(
        ai_interpretation,
        list,
    ):
        ai_interpretation = []

    unverifiable = parsed.get(
        "unverifiable"
    )

    if not isinstance(
        unverifiable,
        list,
    ):
        unverifiable = []

    # ---------------------------------------------------------------
    # Return structured result
    # ---------------------------------------------------------------

    return CompanyResearchResult(
        status="ok",
        company_name=company,

        company_overview=parsed.get(
            "company_overview"
        ),

        official_website=parsed.get(
            "official_website"
        ),

        industry=parsed.get(
            "industry"
        ),

        founded_year=parsed.get(
            "founded_year"
        ),

        headquarters=parsed.get(
            "headquarters"
        ),

        products_services=parsed.get(
            "products_services"
        ),

        company_size=parsed.get(
            "company_size"
        ),

        online_presence=parsed.get(
            "online_presence"
        ),

        careers_presence=parsed.get(
            "careers_presence"
        ),

        recent_public_info=parsed.get(
            "recent_public_info"
        ),

        red_flags=parsed.get(
            "red_flags"
        ),

        job_consistency_notes=parsed.get(
            "job_consistency_notes"
        ),

        overall_assessment=parsed.get(
            "overall_assessment"
        ),

        verified_facts=verified_facts,

        ai_interpretation=ai_interpretation,

        unverifiable=unverifiable,

        sources=sources,

        llm_model=RESEARCH_MODEL_NAME,
    )