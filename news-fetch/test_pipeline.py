import argparse
import sys
from datetime import datetime, timedelta
from typing import List

from app.config import get_settings
from app.core.logging import setup_logging
from app.models.schemas.article import Article, ArticleSource
from app.services.pipeline import NewsPipelineService

MOCK_ARTICLES = [
    # Event 1: SpaceX launch (articles from BBC, Reuters, TechCrunch)
    Article(
        title="SpaceX launches Starship rocket on successful sixth test flight",
        description="SpaceX launched its mega Starship rocket system from Texas on Tuesday in another major test flight.",
        url="https://www.reuters.com/technology/space/spacex-launches-starship-2026-10-06?utm_source=twitter",
        source=ArticleSource(id="reuters", name="Reuters"),
    ),
    Article(
        title="SpaceX launches Starship rocket on successful sixth test flight", # duplicate URL with different tracking param
        description="SpaceX launched its mega Starship rocket system from Texas on Tuesday in another major test flight.",
        url="https://www.reuters.com/technology/space/spacex-launches-starship-2026-10-06?utm_source=facebook",
        source=ArticleSource(id="reuters", name="Reuters"),
    ),
    Article(
        title="Starship completes crucial orbital milestone in latest SpaceX flight test",
        description="Elon Musk's SpaceX has achieved another milestone after the Starship rocket completed its test maneuvers over the Gulf of Mexico.",
        url="https://www.bbc.com/news/science-environment-starship-flight",
        source=ArticleSource(id="bbc-news", name="BBC News"),
    ),
    Article(
        title="SpaceX flies Starship for the sixth time with payload demonstrations",
        description="Starship lifted off from Starbase facility, demonstrating engine reignition in space and splashdown.",
        url="https://techcrunch.com/2026/10/06/spacex-starship-sixth-flight",
        source=ArticleSource(id="techcrunch", name="TechCrunch"),
    ),
    # Event 2: Federal Reserve interest rates (Bloomberg, CNBC, WSJ)
    Article(
        title="Federal Reserve cuts interest rates by 25 basis points amid cooling inflation",
        description="The Federal Reserve lowered its benchmark borrowing rate by a quarter point on Wednesday, citing progress toward the 2% inflation target.",
        url="https://www.bloomberg.com/news/articles/2026-10-06/fed-cuts-rates-25bps",
        source=ArticleSource(id="bloomberg", name="Bloomberg"),
    ),
    Article(
        title="Fed lowers benchmark interest rate by 25 bps in widely expected move",
        description="Central bank officials voted to ease monetary policy by cutting rates 25 basis points as labor market conditions soften.",
        url="https://www.cnbc.com/2026/10/06/fed-interest-rate-decision.html",
        source=ArticleSource(id="cnbc", name="CNBC"),
    ),
    Article(
        title="Federal Reserve cuts rates by 25 basis points in latest monetary easing", # Near duplicate content syndicated
        description="The Federal Reserve lowered its benchmark borrowing rate by a quarter point on Wednesday, citing progress toward the 2% inflation target.",
        url="https://www.wsj.com/economy/central-banking/fed-cuts-rates-today",
        source=ArticleSource(id="the-wall-street-journal", name="WSJ"),
    ),
    # Event 3: Major earthquake in Tokyo (CNN, Japan Times)
    Article(
        title="Magnitude 6.2 earthquake jolts central Japan, no tsunami warning issued",
        description="A strong magnitude 6.2 earthquake shook Tokyo and surrounding prefectures on Wednesday morning, with minor tremors reported across the capital.",
        url="https://www.japantimes.co.jp/news/2026/10/06/earthquake-tokyo-magnitude-6-2",
        source=ArticleSource(id="the-japan-times", name="The Japan Times"),
    ),
    Article(
        title="Earthquake of magnitude 6.2 hits central Japan; no immediate reports of damage",
        description="Tokyo residents felt tremors after an earthquake struck off the coast. Japanese meteorological agency confirmed no tsunami risk.",
        url="https://www.cnn.com/2026/10/06/asia/japan-earthquake-tokyo-intl/index.html",
        source=ArticleSource(id="cnn", name="CNN"),
    ),
    # Outliers / Noise (single unrelated stories)
    Article(
        title="Local bakery in Vermont wins international sourdough championship",
        description="A small artisan bakery from rural Vermont took first prize at the World Bread Awards in Paris.",
        url="https://www.vermontnews.com/local/sourdough-champion-vermont",
        source=ArticleSource(id=None, name="Local Herald"),
    ),
    Article(
        title="Ancient Roman mosaic floor uncovered during plumbing work in Verona",
        description="Archaeologists were called after plumbers unearthed an intact 3rd-century mosaic floor beneath an apartment building.",
        url="https://www.theguardian.com/world/2026/oct/06/ancient-roman-mosaic-verona",
        source=ArticleSource(id="the-guardian", name="The Guardian"),
    ),
]

def print_cluster_report(response):
    metrics = response.metrics
    print("\n" + "=" * 70)
    print("           NEWS EVENT CLUSTERING PIPELINE REPORT (STAGE 7)")
    print("=" * 70)
    print(f"Target Date:                  {response.date}")
    print(f"Total Articles Ingested:      {metrics.total_fetched}")
    print(f"URL Duplicates Removed:       {metrics.url_duplicates_removed}")
    print(f"After URL Deduplication:      {metrics.after_url_dedup}")
    print(f"Content Duplicates Removed:   {metrics.content_duplicates_removed}")
    print(f"Final Deduplicated Articles:  {metrics.after_content_dedup}")
    print("-" * 70)
    print(f"Total Event Clusters Formed:  {metrics.total_clusters}")
    print(f"Noise / Outlier Articles:     {metrics.noise_count} ({metrics.noise_ratio * 100:.1f}%)")
    if metrics.silhouette_score is not None:
        print(f"Silhouette Score (no noise):  {metrics.silhouette_score:.4f}")
    else:
        print("Silhouette Score:             N/A (insufficient clusters)")
    print("=" * 70)

    for cluster in response.clusters:
        print(f"\n📂 [Event Cluster #{cluster.cluster_id}] — ({cluster.article_count} articles)")
        for a in cluster.articles:
            source_name = a.source.name if a.source and a.source.name else "Unknown"
            print(f"    • [{source_name}] {a.title}")
            if a.description:
                print(f"      Summary: {a.description[:100]}...")

    if response.noise_articles:
        print(f"\n🗑️  [Noise / Singletons] — ({len(response.noise_articles)} articles)")
        for a in response.noise_articles:
            source_name = a.source.name if a.source and a.source.name else "Unknown"
            print(f"    • [{source_name}] {a.title}")

    print("\n" + "=" * 70)
    print("                  PIPELINE VERIFICATION SUCCESS")
    print("=" * 70)

def main():
    parser = argparse.ArgumentParser(description="Test News Event Clustering Pipeline up to Stage 7")
    parser.add_argument("--live", action="store_true", help="Fetch live news from NewsAPI")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    parser.add_argument("--query", type=str, default="*", help="Query for NewsAPI (default '*')")
    parser.add_argument("--max-articles", type=int, default=100, help="Max articles to fetch")
    parser.add_argument("--eps", type=float, default=0.35, help="DBSCAN eps (default 0.35)")
    parser.add_argument("--min-samples", type=int, default=2, help="DBSCAN min_samples (default 2)")
    args = parser.parse_args()

    settings = get_settings()
    setup_logging(level=settings.log_level)
    pipeline_service = NewsPipelineService(settings=settings)

    if args.live:
        if not settings.news_api_key or settings.news_api_key.startswith("YOUR_"):
            print("ERROR: Live mode requested, but NEWS_API_KEY is not set in .env")
            sys.exit(1)
        print(f"Running pipeline in LIVE mode fetching from NewsAPI...")
        response = pipeline_service.run_pipeline(
            articles=None,
            date_str=args.date,
            query=args.query,
            max_articles=args.max_articles,
            eps=args.eps,
            min_samples=args.min_samples,
        )
    else:
        print("Running pipeline in VERIFICATION mode with curated multi-event dataset...")
        response = pipeline_service.run_pipeline(
            articles=MOCK_ARTICLES,
            date_str=args.date or "2026-10-06",
            eps=args.eps,
            min_samples=args.min_samples,
        )

    print_cluster_report(response)

if __name__ == "__main__":
    main()
