import pytest
from app.services.article_extractor import ArticleExtractor


def test_article_extractor_cleans_noise():
    extractor = ArticleExtractor()
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head><title>Test News Article</title></head>
    <body>
      <nav><a href='/home'>Home</a> <a href='/contact'>Contact</a></nav>
      <header><h1>News Outlet Header</h1></header>
      <aside class='sidebar'>Sponsored links and ads here</aside>
      <article>
        <h1>Global Semiconductor Production Expands</h1>
        <p class='byline'>By Jane Doe | Published Oct 14, 2026</p>
        <p>Leading chip foundries announced a major expansion in advanced node production today, following new trade agreements.</p>
        <p>The move is expected to alleviate automotive supply shortages that have persisted over the past two quarters.</p>
        <p>Industry analysts noted that supply chains in North America and Europe will see immediate inventory stabilization.</p>
      </article>
      <footer>Copyright 2026. All rights reserved. <a href='/privacy'>Privacy Policy</a></footer>
    </body>
    </html>
    """
    clean_text = extractor.extract_clean_content(sample_html)
    assert clean_text is not None
    # Verify main text is present
    assert "Global Semiconductor Production Expands" in clean_text
    assert "Leading chip foundries announced a major expansion" in clean_text
    # Verify navigation and footer noise are stripped
    assert "Home" not in clean_text
    assert "Privacy Policy" not in clean_text
    assert "Sponsored links" not in clean_text
