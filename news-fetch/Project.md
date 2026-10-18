# Building a News Event Clustering Pipeline from NewsAPI

## 1. Overview

This document describes the complete process of building a news processing pipeline that fetches articles from NewsAPI, deduplicates them, generates semantic embeddings, and clusters similar articles into events. The pipeline is designed so that each stage can be tested independently before moving to the next. The final goal is to feed event clusters into an LLM for analysis and store the results in FalkorDB, but this guide focuses on getting you through **Event Clustering**—the stage where you can verify that your system correctly groups articles reporting on the same real-world event.

The pipeline stages are:

```
NewsAPI → Fetch Yesterday's News → Basic Deduplication (URL/Hash)
→ Generate Embeddings → Event Clustering → LLM Analysis → FalkorDB
```

---

## 2. Prerequisites

Before starting, ensure you have:

- Python 3.10+
- A NewsAPI API key (free tier available at [newsapi.org](https://newsapi.org))
- Familiarity with `requests`, `pandas`, and basic NLP concepts
- Optional GPU for faster embedding generation (CPU works for testing)

Install the required Python packages:

```bash
pip install newsapi-python sentence-transformers scikit-learn numpy pandas simhash
```

For FalkorDB (later stages): `pip install falkordb`

---

## 3. Stage 1: Fetching News from NewsAPI

### 3.1 Using the `newsapi-python` Client

The `newsapi-python` library provides a clean interface to NewsAPI V2. The most relevant endpoint for daily news is `/v2/top-headlines` or `/v2/everything` with date filtering.

```python
from newsapi import NewsApiClient
from datetime import datetime, timedelta

# Initialize the client
newsapi = NewsApiClient(api_key='YOUR_API_KEY')

# Fetch yesterday's news
yesterday = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')

response = newsapi.get_everything(
    q='*',                     # All articles; refine with keywords if needed
    from_param=yesterday,
    to=yesterday,
    language='en',
    sort_by='relevancy',
    page_size=100              # Max 100 per request; paginate if needed
)

articles = response['articles']
```

**Key parameters**:

- `q`: Search query. Use `'*'` to fetch broadly, or a domain-specific keyword.
- `from_param` / `to`: ISO 8601 dates. NewsAPI free tier limits results to 100 per request and only allows articles from the last month.
- `page_size`: Up to 100. Use pagination (`page` parameter) to fetch more.

**What you get per article**: `source`, `author`, `title`, `description`, `url`, `urlToImage`, `publishedAt`, `content` (truncated).

### 3.2 Handling Pagination and Rate Limits

NewsAPI free tier allows **100 requests per day**. To fetch yesterday’s complete news, paginate efficiently:

```python
all_articles = []
page = 1
while True:
    resp = newsapi.get_everything(
        q='*',
        from_param=yesterday,
        to=yesterday,
        language='en',
        page_size=100,
        page=page
    )
    if not resp['articles']:
        break
    all_articles.extend(resp['articles'])
    if len(resp['articles']) < 100:
        break
    page += 1
```

**Testing tip**: For initial testing, fetch only 50–100 articles to keep embedding and clustering fast.

---

## 4. Stage 2: Basic Deduplication

NewsAPI often returns duplicate articles from different sources or syndicated content. Deduplication prevents redundant processing and skews clustering.

### 4.1 URL-Based Deduplication

The simplest approach: normalize URLs and keep only unique ones.

```python
import hashlib
from urllib.parse import urlparse, urlunparse

def normalize_url(url: str) -> str:
    """Strip query params, fragments, and tracking parameters."""
    parsed = urlparse(url)
    # Keep scheme + host + path only
    normalized = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
    return normalized.lower()

def url_fingerprint(url: str) -> str:
    """SHA-1 hash of normalized URL for fast lookup."""
    normalized = normalize_url(url)
    return hashlib.sha1(normalized.encode('utf-8')).hexdigest()

# Build a set of seen fingerprints
seen = set()
unique_articles = []
for art in all_articles:
    fp = url_fingerprint(art['url'])
    if fp not in seen:
        seen.add(fp)
        unique_articles.append(art)
```

This catches exact URL matches and common tracking-parameter variants.

### 4.2 Content-Based Deduplication (SimHash)

URL deduplication alone misses syndicated articles with different URLs but identical content. SimHash is a locality-sensitive hash that produces similar fingerprints for similar texts. Articles with a Hamming distance of 0 or 1 are likely duplicates.

```python
from simhash import Simhash

def content_fingerprint(article: dict) -> Simhash:
    """Combine title + description + content for a robust fingerprint."""
    text = f"{article['title']} {article.get('description', '')} {article.get('content', '')}"
    # SimHash over trigrams of alphanumeric characters
    return Simhash(text.lower())

# After URL dedup, do content-level dedup
content_seen = []
final_articles = []
for art in unique_articles:
    fp = content_fingerprint(art)
    is_duplicate = False
    for existing_fp in content_seen:
        if fp.distance(existing_fp) <= 1:  # Hamming distance threshold
            is_duplicate = True
            break
    if not is_duplicate:
        content_seen.append(fp)
        final_articles.append(art)
```

**Why SimHash works well for news**: News articles are long enough that minor editorial changes (adding a source name, changing punctuation) do not alter the SimHash. The TakeLab Retriever project uses exactly this approach with trigrams of alphanumeric characters and achieved only 2 false positives across ~150,000 articles.

**Testing tip**: Log the number of duplicates removed at each step. A typical daily NewsAPI fetch might have 10–30% duplication.

---

## 5. Stage 3: Generating Embeddings

Embeddings convert article text into dense vectors that capture semantic meaning. Articles about the same event will have similar vectors even if they use different words.

### 5.1 Choosing an Embedding Model

For news clustering, **Sentence-BERT (SBERT)** models are the standard. The `all-MiniLM-L6-v2` model is an excellent trade-off between quality and speed:

- 384-dimensional embeddings
- ~80 MB model size
- Runs on CPU for hundreds of articles in seconds
- Outperforms TF-IDF in all clustering metrics

A 2026 IEEE study on news clustering confirmed that Sentence-BERT embeddings are superior to TF-IDF across ARI, NMI, and Silhouette scores.

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')

def article_to_text(art: dict) -> str:
    """Concatenate the fields most relevant for semantic similarity."""
    parts = [art.get('title', ''), art.get('description', '')]
    return ' '.join(p for p in parts if p)

texts = [article_to_text(art) for art in final_articles]
embeddings = model.encode(texts, show_progress_bar=True, batch_size=64)
# embeddings shape: (n_articles, 384)
```

### 5.2 Why Title + Description (Not Full Content)

NewsAPI's `content` field is truncated and often includes boilerplate ("[+1234 chars]"). The title and description together provide a clean, focused semantic signal. For clustering purposes, this is usually sufficient. If you need finer granularity, include the first 2–3 sentences of the content.

**Testing tip**: After generating embeddings, compute a pairwise cosine similarity matrix for a small sample (10–20 articles) and visually inspect whether articles about the same topic have high similarity (> 0.6).

---

## 6. Stage 4: Event Clustering

This is the core of the pipeline. The goal is to group articles into clusters, where each cluster represents **one real-world event**. Articles in the same cluster should describe the same incident, announcement, or development.

### 6.1 Clustering Algorithm Choice

Three algorithms are commonly used for news event clustering:

| Algorithm         | Strengths                                                             | Weaknesses                                                             | Best For                        |
| ----------------- | --------------------------------------------------------------------- | ---------------------------------------------------------------------- | ------------------------------- |
| **DBSCAN**        | No need to specify K; finds arbitrary shapes; marks outliers as noise | Sensitive to `eps` and `min_samples`; struggles with varying densities | Small-to-medium daily batches   |
| **HDBSCAN**       | Hierarchical; handles varying densities; robust to parameter choice   | Slightly more complex; may produce many small clusters                 | Production pipelines            |
| **Agglomerative** | Deterministic; produces a hierarchy; easy to cut at a threshold       | Need to specify distance threshold; O(n²) memory                       | Small batches ( < 500 articles) |

For a daily news batch of 50–500 articles, **DBSCAN with cosine distance** is the simplest starting point. Many production systems (e.g., NewsKit MCP Server) use DBSCAN with a cosine similarity threshold of 0.75–0.85.

### 6.2 DBSCAN Implementation

```python
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_distances
import numpy as np

# Compute cosine distance matrix (1 - cosine similarity)
distance_matrix = cosine_distances(embeddings)

# DBSCAN with precomputed distance matrix
clustering = DBSCAN(
    eps=0.35,          # max distance between samples in same cluster
    min_samples=2,     # minimum articles to form an event cluster
    metric='precomputed'
)
labels = clustering.fit_predict(distance_matrix)
```

**Parameter tuning**:

- `eps`: For 384-dim SBERT embeddings, cosine distance values typically range from 0.1 (very similar) to 1.0 (unrelated). Start with `eps=0.35` (corresponding to cosine similarity ≈ 0.65). Lower `eps` → tighter clusters; higher → looser.
- `min_samples`: Set to 2 for testing. Raise to 3–5 for production to avoid spurious clusters.
- Articles labeled `-1` are noise/outliers—articles that don't belong to any event cluster.

### 6.3 Interpreting Clusters

```python
from collections import defaultdict

clusters = defaultdict(list)
for idx, label in enumerate(labels):
    if label != -1:
        clusters[label].append(final_articles[idx])

for cluster_id, arts in clusters.items():
    print(f"\n=== Event Cluster {cluster_id} ({len(arts)} articles) ===")
    for a in arts:
        print(f"  - {a['title'][:100]}...")
```

**What a good cluster looks like**: Multiple articles from different sources (e.g., Reuters, BBC, CNN) all reporting on the same event—for example, a specific election result, a natural disaster, or a product launch. Their titles will be paraphrases of each other.

**What a bad cluster looks like**: Articles that share a broad topic (e.g., "technology") but describe different events. This usually means `eps` is too high—the cluster is too loose.

### 6.4 Alternative: HDBSCAN for Production

For more robust clustering, especially when event sizes vary widely:

```python
from sklearn.cluster import HDBSCAN

clusterer = HDBSCAN(
    min_cluster_size=2,
    min_samples=1,
    metric='cosine',
    cluster_selection_epsilon=0.35
)
labels = clusterer.fit_predict(embeddings)
```

HDBSCAN is used in the Chronicle project for exactly this purpose: transforming real-time news streams into coherent clustered timelines.

### 6.5 Evaluation Without Labels

You won't have ground-truth event labels for testing. Use these proxies to evaluate cluster quality:

1. **Silhouette Score**: Measures how similar an article is to its own cluster vs. other clusters. Range: -1 to 1. Higher is better. For SBERT news clustering, scores around 0.1–0.3 are typical.
2. **Manual inspection**: Print cluster contents and check if articles genuinely describe the same event.
3. **Cluster size distribution**: Healthy event clusters typically have 2–10 articles. Very large clusters (> 20) suggest over-merging.
4. **Noise ratio**: The percentage of articles labeled `-1`. A ratio of 10–30% is normal; very low or very high values indicate parameter issues.

```python
from sklearn.metrics import silhouette_score

# Exclude noise points (-1) for silhouette
mask = labels != -1
if len(set(labels[mask])) > 1:
    score = silhouette_score(embeddings[mask], labels[mask], metric='cosine')
    print(f"Silhouette score (excluding noise): {score:.3f}")
```

---

## 7. Testing the Pipeline End-to-End (Up to Clustering)

Before wiring in the LLM and FalkorDB, validate the clustering stage with a controlled experiment.

### 7.1 Test Script Structure

```python
# test_clustering.py
from datetime import datetime, timedelta
from newsapi import NewsApiClient
from sentence_transformers import SentenceTransformer
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_distances
import hashlib
from simhash import Simhash
from collections import defaultdict

def run_pipeline(api_key: str, date_str: str):
    # 1. Fetch
    newsapi = NewsApiClient(api_key=api_key)
    articles = fetch_articles(newsapi, date_str)
    print(f"Fetched {len(articles)} articles")

    # 2. URL dedup
    articles = url_dedup(articles)
    print(f"After URL dedup: {len(articles)}")

    # 3. Content dedup
    articles = content_dedup(articles)
    print(f"After content dedup: {len(articles)}")

    # 4. Embeddings
    model = SentenceTransformer('all-MiniLM-L6-v2')
    texts = [f"{a['title']} {a.get('description','')}" for a in articles]
    embeddings = model.encode(texts)

    # 5. Cluster
    dist = cosine_distances(embeddings)
    labels = DBSCAN(eps=0.35, min_samples=2, metric='precomputed').fit_predict(dist)

    # 6. Report
    clusters = defaultdict(list)
    for idx, label in enumerate(labels):
        if label != -1:
            clusters[label].append(articles[idx])

    print(f"\nFound {len(clusters)} event clusters")
    for cid, arts in sorted(clusters.items(), key=lambda x: -len(x[1])):
        print(f"\nCluster {cid} ({len(arts)} articles):")
        for a in arts:
            print(f"  • {a['title'][:120]}")
```

### 7.2 What to Look For

- **Fetched count**: Should be 50–200 for a single day with `q='*'`. If you get fewer than 20, widen your query or check date formatting.
- **Dedup ratio**: Expect 10–30% reduction after URL + content dedup.
- **Cluster count**: For 100 unique articles, expect 15–40 event clusters.
- **Cluster contents**: Manually verify 3–5 clusters. Do the articles genuinely describe the same event?
- **Noise ratio**: If > 50% of articles are labeled `-1`, lower `eps` or reduce `min_samples`. If < 5%, raise `eps`.

### 7.3 Common Pitfalls

| Issue                     | Symptom                                       | Fix                                                           |
| ------------------------- | --------------------------------------------- | ------------------------------------------------------------- |
| `eps` too high            | One giant cluster containing unrelated events | Lower `eps` to 0.25–0.30                                      |
| `eps` too low             | Almost all articles are noise (`-1`)          | Raise `eps` to 0.40–0.45                                      |
| Truncated NewsAPI content | Embeddings are weak                           | Use title + description only; ignore `content`                |
| Date formatting           | Zero articles fetched                         | Use `YYYY-MM-DD` format for `from_param` and `to`             |
| Duplicate clusters        | Two clusters about the same event             | Lower SimHash Hamming threshold to 0; check embedding quality |

---

## 8. Next Stages (After Clustering Validation)

Once clustering is validated, the remaining pipeline stages are:

### 8.1 LLM Analysis of Clusters

For each event cluster, feed the cluster's articles (titles + descriptions) into an LLM with a prompt like:

```
You are analyzing a news event cluster. The following articles report on the same event:
{articles}

Extract:
1. A concise event summary (2-3 sentences)
2. Key entities (people, organizations, locations)
3. Event category (politics, business, technology, etc.)
4. Sentiment (positive, negative, neutral)
```

### 8.2 Storing in FalkorDB

FalkorDB is a low-latency graph database ideal for storing relationships between events, entities, and articles. Use the Python client:

```python
from falkordb import FalkorDB

db = FalkorDB(host='localhost', port=6379)
graph = db.select_graph('news_events')

# Create event node
graph.query(
    "CREATE (e:Event {id: $id, summary: $summary, category: $category})",
    {'id': cluster_id, 'summary': event_summary, 'category': category}
)

# Link articles to event
for art in cluster_articles:
    graph.query(
        "MATCH (e:Event {id: $eid}) "
        "CREATE (a:Article {url: $url, title: $title}) "
        "CREATE (a)-[:REPORTS_ON]->(e)",
        {'eid': cluster_id, 'url': art['url'], 'title': art['title']}
    )
```

FalkorDB has native integrations with LangChain and LlamaIndex, so you can plug it directly into existing pipelines without custom glue code.

---

## 9. Summary

| Stage         | Key Tool                | Output          | Validation Metric                                 |
| ------------- | ----------------------- | --------------- | ------------------------------------------------- |
| Fetch         | `newsapi-python`        | Raw articles    | 50–200 articles/day                               |
| URL Dedup     | SHA-1 of normalized URL | Unique URLs     | 10–20% reduction                                  |
| Content Dedup | SimHash (trigrams)      | Unique content  | 5–15% further reduction                           |
| Embeddings    | `all-MiniLM-L6-v2`      | 384-dim vectors | Cosine similarity of known-similar articles > 0.7 |
| Clustering    | DBSCAN (cosine)         | Event clusters  | Silhouette > 0.1; manual inspection               |

The pipeline up to event clustering is fully testable with a free NewsAPI key and a CPU. Once you can reliably produce coherent event clusters from a day's news, you are ready to integrate the LLM analysis and FalkorDB storage layers.
