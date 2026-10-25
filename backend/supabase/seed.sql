-- =============================================================================
-- Local development seed data
-- Runs after all migrations on `supabase db reset`. Never applied to production.
-- Keep it small: just enough for every page to render with real-looking data.
-- =============================================================================

INSERT INTO tracked_tickers (ticker, status, sentiment_ready, name, sector, region, country)
VALUES
  ('AAPL', 'held',     TRUE, 'Apple Inc.',         'Technology', 'North America', 'United States'),
  ('NVDA', 'tracking', TRUE, 'NVIDIA Corporation', 'Technology', 'North America', 'United States'),
  ('ASML', 'tracking', TRUE, 'ASML Holding N.V.',  'Technology', 'Europe',        'Netherlands');

INSERT INTO articles (id, timestamp, title, body, author, source, url)
OVERRIDING SYSTEM VALUE
VALUES
  (1, NOW() - INTERVAL '1 day',  'Apple beats revenue estimates on services growth', 'Seed article body.', 'Seed', 'reuters',  'https://example.com/seed/1'),
  (2, NOW() - INTERVAL '2 days', 'NVIDIA guidance tops expectations',                 'Seed article body.', 'Seed', 'cnbc',     'https://example.com/seed/2'),
  (3, NOW() - INTERVAL '3 days', 'Export curbs weigh on chip equipment makers',       'Seed article body.', 'Seed', 'ft',       'https://example.com/seed/3'),
  (4, NOW() - INTERVAL '5 days', 'Apple faces antitrust scrutiny in the EU',          'Seed article body.', 'Seed', 'bloomberg','https://example.com/seed/4');

SELECT setval(pg_get_serial_sequence('articles', 'id'), (SELECT MAX(id) FROM articles));

INSERT INTO sentiments (article_id, affected, score, confidence)
VALUES
  (1, 'AAPL',  0.72, 0.91),
  (2, 'NVDA',  0.65, 0.88),
  (3, 'ASML', -0.48, 0.79),
  (3, 'NVDA', -0.21, 0.62),
  (4, 'AAPL', -0.35, 0.74);
