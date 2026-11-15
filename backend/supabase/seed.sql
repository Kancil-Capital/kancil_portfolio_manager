-- =============================================================================
-- Local development seed data
-- Runs after all migrations on `supabase db reset`. Never applied to production.
-- Small, but shaped like production so every page renders the way it does there.
-- The data is synthetic apart from the NVDA and MU EPS history (public figures).
-- =============================================================================

-- ── Tracked tickers ──────────────────────────────────────────────────────────
-- `region` holds the reporting currency, as /research writes it
-- (yfinance financialCurrency), not a geographic region.
-- MU has never been scraped (sentiment_ready false, last_scraped NULL), so the
-- UI shows it as "new" and its research page takes the new-ticker path.
INSERT INTO public.tracked_tickers (ticker, status, sentiment_ready, last_scraped, added_at, name, sector, region, country)
VALUES
  ('AAPL', 'held',     TRUE,  NOW() - INTERVAL '6 hours', NOW() - INTERVAL '40 days', 'Apple Inc.',              'Technology', 'USD', 'United States'),
  ('NVDA', 'tracking', TRUE,  NOW() - INTERVAL '6 hours', NOW() - INTERVAL '35 days', 'NVIDIA Corporation',      'Technology', 'USD', 'United States'),
  ('ASML', 'tracking', TRUE,  NOW() - INTERVAL '6 hours', NOW() - INTERVAL '30 days', 'ASML Holding N.V.',       'Technology', 'EUR', 'Netherlands'),
  ('MU',   'tracking', FALSE, NULL,                       NOW() - INTERVAL '1 hour',  'Micron Technology, Inc.', 'Technology', 'USD', 'United States');

-- ── Articles ─────────────────────────────────────────────────────────────────
-- Production sources are exactly 'CNBC' and 'Yahoo Finance' (the source filter
-- matches on them), and some authors are empty strings.
INSERT INTO public.articles (id, timestamp, title, body, author, source, url)
OVERRIDING SYSTEM VALUE
VALUES
  (1,  NOW() - INTERVAL '3 hours',            'Apple beats revenue estimates as services hit a record',          'Apple reported quarterly revenue ahead of Wall Street expectations, driven by record services sales. iPhone revenue was roughly flat year over year, while wearables declined for a third straight quarter.', 'Seed Reporter', 'CNBC',          'https://example.com/seed/1'),
  (2,  NOW() - INTERVAL '9 hours',            'Fed holds rates steady, signals patience on cuts',                'The Federal Reserve left its benchmark rate unchanged and said it needs more evidence that inflation is cooling before easing. Bank stocks slipped while Treasury yields edged higher.',                     'Seed Reporter', 'CNBC',          'https://example.com/seed/2'),
  (3,  NOW() - INTERVAL '1 day',              'NVIDIA guidance tops expectations on data center demand',         'NVIDIA forecast revenue above analyst estimates as cloud providers continue to expand AI infrastructure spending. Shares rose in extended trading.',                                                       '',              'CNBC',          'https://example.com/seed/3'),
  (4,  NOW() - INTERVAL '1 day 5 hours',      'Wall Street Analysts See 18% Upside in NVIDIA (NVDA)',            'NVIDIA closed the last trading session higher, and the mean of short-term price targets set by analysts points to further upside. Earnings estimate revisions have trended upward.',                       'Zacks Equity Research', 'Yahoo Finance', 'https://example.com/seed/4'),
  (5,  NOW() - INTERVAL '2 days',             'Export curbs weigh on chip equipment makers',                     'New export restrictions on advanced chipmaking tools to China hit European and U.S. equipment suppliers. Analysts said the rules could shave several points off next year''s order growth.',                 'Seed Reporter', 'CNBC',          'https://example.com/seed/5'),
  (6,  NOW() - INTERVAL '3 days',             'Oil jumps as supply talks stall',                                 'Crude prices rose more than 3% after producers failed to agree on output targets. Energy stocks led the market higher while airlines fell.',                                                               'Seed Reporter', 'CNBC',          'https://example.com/seed/6'),
  (7,  NOW() - INTERVAL '4 days',             'ASML (ASML) Valuation Check After Recent Share Price Swings',     'ASML shares have been volatile over the past month. We look at whether the current valuation reflects the company''s long-term growth expectations in lithography.',                                       'Simply Wall St', 'Yahoo Finance', 'https://example.com/seed/7'),
  (8,  NOW() - INTERVAL '5 days',             'Apple faces fresh antitrust scrutiny in the EU',                  'European regulators opened a new inquiry into Apple''s App Store terms under the Digital Markets Act. The company said it would cooperate with the review.',                                                'Seed Reporter', 'CNBC',          'https://example.com/seed/8'),
  (9,  NOW() - INTERVAL '6 days',             'Big Tech leads Nasdaq to record close',                           'Technology shares pushed the Nasdaq to an all-time high, with chipmakers and software names among the top gainers. Microsoft, Apple and NVIDIA together accounted for most of the index''s advance.',       '',              'CNBC',          'https://example.com/seed/9'),
  (10, NOW() - INTERVAL '8 days',             'China stimulus hopes lift Asian markets',                         'Stocks in Hong Kong and mainland China rallied on reports of new fiscal support. Japanese shares were little changed as the yen strengthened.',                                                            'Seed Reporter', 'CNBC',          'https://example.com/seed/10'),
  (11, NOW() - INTERVAL '10 days',            'Bank earnings preview: trading revenue expected to cushion loan slowdown', 'Large U.S. banks are expected to report strong trading results, offsetting slower loan growth. JPMorgan and Goldman Sachs report next week.',                                                  'Seed Reporter', 'Yahoo Finance', 'https://example.com/seed/11'),
  (12, NOW() - INTERVAL '12 days',            'Retail sales unexpectedly flat in October',                       'U.S. retail sales were unchanged last month, missing forecasts for a modest gain. Department stores and online retailers both reported softer demand.',                                                    'Seed Reporter', 'CNBC',          'https://example.com/seed/12'),
  (13, NOW() - INTERVAL '14 days',            'Is Apple (AAPL) Stock Outpacing Its Computer and Technology Peers?', 'Apple has gained this year, roughly in line with the broader technology sector. The company''s earnings estimate has moved slightly higher over the past quarter.',                                     'Zacks Equity Research', 'Yahoo Finance', 'https://example.com/seed/13'),
  (14, NOW() - INTERVAL '16 days',            'UK inflation eases more than expected',                           'Consumer price growth in the UK slowed for a second month, raising expectations that the Bank of England will cut rates early next year. Sterling weakened against the dollar.',                           'Seed Reporter', 'CNBC',          'https://example.com/seed/14'),
  (15, NOW() - INTERVAL '19 days',            'Memory chip prices climb as AI servers soak up supply',           'Prices for high-bandwidth memory rose again as AI server builds absorbed capacity. Micron and other suppliers are expected to benefit through next year.',                                                 'Seed Reporter', 'Yahoo Finance', 'https://example.com/seed/15'),
  (16, NOW() - INTERVAL '22 days',            'Tariff refunds to start for importers after court ruling',        'A refund process for businesses that paid tariffs later ruled unlawful is scheduled to open next week. Importers of consumer electronics are among the largest claimants.',                               '',              'CNBC',          'https://example.com/seed/16'),
  (17, NOW() - INTERVAL '25 days',            'NVIDIA shares slip as investors rotate out of AI winners',        'NVIDIA fell for a third session as investors took profits in the year''s best-performing stocks and moved into industrials and healthcare.',                                                                'Seed Reporter', 'CNBC',          'https://example.com/seed/17'),
  (18, NOW() - INTERVAL '28 days',            'European stocks close lower as rate worries return',              'The pan-European index fell as bond yields climbed. Technology shares were the weakest sector, with semiconductor names down more than 2%.',                                                                'Seed Reporter', 'CNBC',          'https://example.com/seed/18');

SELECT setval(pg_get_serial_sequence('public.articles', 'id'), (SELECT MAX(id) FROM public.articles));

-- ── Sentiments ───────────────────────────────────────────────────────────────
-- `affected` mixes tickers with sector ('Technology', 'Energy', …) and region
-- ('United States', 'EU', 'China', …) keywords; in production about 40% of rows
-- are keywords, and the research page pulls them in through the ticker's
-- sector/region/country. Most articles have 1–4 rows; some are macro-only with
-- no ticker. Confidence sits in 0.25–0.70, as the model produces. A few scores
-- are inside ±0.1 so the "neutral" filter has results.
INSERT INTO public.sentiments (article_id, affected, score, confidence)
VALUES
  (1,  'AAPL',                    0.7214, 0.4912),
  (1,  'Technology',              0.4103, 0.3127),
  (1,  'United States',           0.2210, 0.2846),
  (2,  'United States',          -0.3418, 0.4101),
  (2,  'Financials',             -0.5520, 0.3355),
  (2,  'JPM',                    -0.1876, 0.2713),
  (3,  'NVDA',                    0.8461, 0.6122),
  (3,  'Technology',              0.6630, 0.3874),
  (3,  'MSFT',                    0.3105, 0.2690),
  (3,  'AMZN',                    0.2982, 0.2655),
  (4,  'NVDA',                    0.5537, 0.4876),
  (5,  'ASML',                   -0.6812, 0.5233),
  (5,  'NVDA',                   -0.2140, 0.3021),
  (5,  'China',                  -0.7395, 0.4410),
  (5,  'EU',                     -0.4472, 0.3518),
  (5,  'Technology',             -0.3901, 0.2934),
  (6,  'Energy',                  0.8120, 0.3054),
  (6,  'Industrials',            -0.2931, 0.2588),
  (6,  'United States',           0.0412, 0.2617),
  (7,  'ASML',                    0.0638, 0.3402),
  (7,  'Technology',              0.1520, 0.2731),
  (8,  'AAPL',                   -0.4950, 0.4377),
  (8,  'EU',                     -0.3366, 0.3962),
  (9,  'Technology',              0.7708, 0.3690),
  (9,  'United States',           0.5281, 0.3014),
  (9,  'AAPL',                    0.4479, 0.2952),
  (9,  'NVDA',                    0.6014, 0.3105),
  (9,  'MSFT',                    0.5823, 0.2881),
  (10, 'China',                   0.6935, 0.4498),
  (10, 'Hong Kong',               0.6140, 0.3307),
  (10, 'Japan',                  -0.0583, 0.2602),
  (11, 'Financials',              0.3846, 0.3471),
  (11, 'JPM',                     0.4211, 0.3290),
  (11, 'GS',                      0.4599, 0.2937),
  (11, 'United States',           0.1734, 0.2551),
  (12, 'Consumer',               -0.6624, 0.3991),
  (12, 'United States',          -0.4807, 0.3492),
  (12, 'AMZN',                   -0.3112, 0.2768),
  (13, 'AAPL',                    0.2865, 0.5017),
  (13, 'Technology',              0.0915, 0.2689),
  (14, 'UK',                      0.5093, 0.4235),
  (14, 'Financials',              0.2247, 0.2806),
  (15, 'MU',                      0.7802, 0.5590),
  (15, 'Technology',              0.5418, 0.3346),
  (15, 'NVDA',                    0.3320, 0.2761),
  (16, 'United States',           0.3957, 0.3183),
  (16, 'Consumer',                0.4628, 0.2930),
  (16, 'AAPL',                    0.1903, 0.2577),
  (17, 'NVDA',                   -0.5734, 0.5126),
  (17, 'Technology',             -0.4421, 0.3277),
  (17, 'Industrials',             0.3368, 0.2711),
  (17, 'Healthcare',              0.2594, 0.2534),
  (18, 'EU',                     -0.5172, 0.4011),
  (18, 'Technology',             -0.6045, 0.3592),
  (18, 'ASML',                   -0.3897, 0.3124);

-- ── EPS cache ────────────────────────────────────────────────────────────────
-- Every tracked ticker has 16 recent quarters with fetched_at = NOW(), so the
-- 90-day cache is fresh and local PEAD never calls Alpha Vantage (25 calls/day).
-- NVDA and MU are real reported figures; AAPL and ASML are synthetic. `sue`
-- uses eps_service's formula (surprise / std of the previous 8 surprises,
-- min 4), so the first 4 quarters of each are NULL, as in production.
INSERT INTO public.eps_cache (ticker, fiscal_date, earnings_date, reported_eps, estimated_eps, eps_surprise, eps_surprise_pct, sue, fetched_at)
VALUES
  ('NVDA', '2022-10-31', '2022-11-16', 0.058, 0.071, -0.013, -0.1831, NULL, NOW()),
  ('NVDA', '2023-01-31', '2023-02-22', 0.088, 0.081, 0.007, 0.0864, NULL, NOW()),
  ('NVDA', '2023-04-30', '2023-05-24', 0.109, 0.092, 0.017, 0.1848, NULL, NOW()),
  ('NVDA', '2023-07-31', '2023-08-23', 0.27, 0.207, 0.063, 0.3043, NULL, NOW()),
  ('NVDA', '2023-10-31', '2023-11-21', 0.402, 0.336, 0.066, 0.1964, 2.0509, NOW()),
  ('NVDA', '2024-01-31', '2024-02-21', 0.516, 0.461, 0.055, 0.1193, 1.5695, NOW()),
  ('NVDA', '2024-04-30', '2024-05-22', 0.612, 0.559, 0.053, 0.0948, 1.5952, NOW()),
  ('NVDA', '2024-07-31', '2024-08-28', 0.68, 0.63, 0.05, 0.0794, 1.5972, NOW()),
  ('NVDA', '2024-10-31', '2024-11-20', 0.81, 0.75, 0.06, 0.08, 2.0383, NOW()),
  ('NVDA', '2025-01-31', '2025-02-26', 0.89, 0.85, 0.04, 0.0471, 1.8171, NOW()),
  ('NVDA', '2025-04-30', '2025-05-28', 0.81, 0.75, 0.06, 0.08, 3.7991, NOW()),
  ('NVDA', '2025-07-31', '2025-08-27', 1.05, 1.01, 0.04, 0.0396, 4.8161, NOW()),
  ('NVDA', '2025-10-31', '2025-11-19', 1.3, 1.26, 0.04, 0.0317, 4.2571, NOW()),
  ('NVDA', '2026-01-31', '2026-02-25', 1.62, 1.54, 0.08, 0.0519, 9.1637, NOW()),
  ('NVDA', '2026-04-30', '2026-05-20', 1.87, 1.77, 0.1, 0.0565, 7.2199, NOW()),
  ('NVDA', '2026-07-31', '2026-08-26', 2.22, 2.09, 0.13, 0.0622, 5.9987, NOW()),
  ('MU', '2022-05-31', '2022-06-30', 2.59, 2.44, 0.15, 0.0615, NULL, NOW()),
  ('MU', '2022-08-31', '2022-09-29', 1.45, 1.37, 0.08, 0.0584, NULL, NOW()),
  ('MU', '2022-11-30', '2022-12-21', -0.04, -0.02, -0.02, -1.0, NULL, NOW()),
  ('MU', '2023-02-28', '2023-03-28', -1.91, -0.88, -1.03, -1.1705, NULL, NOW()),
  ('MU', '2023-05-31', '2023-06-28', -1.43, -1.57, 0.14, 0.0892, 0.2525, NOW()),
  ('MU', '2023-08-31', '2023-09-27', -1.07, -1.18, 0.11, 0.0932, 0.2181, NOW()),
  ('MU', '2023-11-30', '2023-12-20', -0.95, -1.01, 0.06, 0.0594, 0.1298, NOW()),
  ('MU', '2024-02-29', '2024-03-20', 0.42, -0.25, 0.67, 2.68, 1.5731, NOW()),
  ('MU', '2024-05-31', '2024-06-26', 0.62, 0.53, 0.09, 0.1698, 0.19, NOW()),
  ('MU', '2024-08-31', '2024-09-25', 1.18, 1.14, 0.04, 0.0351, 0.0848, NOW()),
  ('MU', '2024-11-30', '2024-12-18', 1.79, 1.77, 0.02, 0.0113, 0.0424, NOW()),
  ('MU', '2025-02-28', '2025-03-20', 1.56, 1.28, 0.28, 0.2188, 0.5943, NOW()),
  ('MU', '2025-05-31', '2025-06-25', 1.91, 1.59, 0.32, 0.2013, 1.487, NOW()),
  ('MU', '2025-08-31', '2025-09-23', 3.03, 2.86, 0.17, 0.0594, 0.7719, NOW()),
  ('MU', '2025-11-30', '2025-12-17', 4.78, 3.94, 0.84, 0.2132, 3.8572, NOW()),
  ('MU', '2026-02-28', '2026-03-18', 12.2, 9.31, 2.89, 0.3104, 9.5864, NOW()),
  ('AAPL', '2022-12-31', '2023-01-30', 1.25, 1.2, 0.05, 0.0417, NULL, NOW()),
  ('AAPL', '2023-03-31', '2023-04-30', 1.26, 1.23, 0.03, 0.0244, NULL, NOW()),
  ('AAPL', '2023-06-30', '2023-07-30', 1.24, 1.26, -0.02, -0.0159, NULL, NOW()),
  ('AAPL', '2023-09-30', '2023-10-30', 1.33, 1.29, 0.04, 0.031, NULL, NOW()),
  ('AAPL', '2023-12-31', '2024-01-30', 1.38, 1.32, 0.06, 0.0455, 1.9298, NOW()),
  ('AAPL', '2024-03-31', '2024-04-30', 1.38, 1.36, 0.02, 0.0147, 0.6422, NOW()),
  ('AAPL', '2024-06-30', '2024-07-30', 1.42, 1.39, 0.03, 0.0216, 1.0607, NOW()),
  ('AAPL', '2024-09-30', '2024-10-30', 1.42, 1.43, -0.01, -0.007, -0.3873, NOW()),
  ('AAPL', '2024-12-31', '2025-01-30', 1.51, 1.46, 0.05, 0.0342, 1.8002, NOW()),
  ('AAPL', '2025-03-31', '2025-04-30', 1.54, 1.5, 0.04, 0.0267, 1.4402, NOW()),
  ('AAPL', '2025-06-30', '2025-07-30', 1.61, 1.54, 0.07, 0.0455, 2.4776, NOW()),
  ('AAPL', '2025-09-30', '2025-10-30', 1.59, 1.57, 0.02, 0.0127, 0.8023, NOW()),
  ('AAPL', '2025-12-31', '2026-01-30', 1.64, 1.61, 0.03, 0.0186, 1.1703, NOW()),
  ('AAPL', '2026-03-31', '2026-04-30', 1.7, 1.65, 0.05, 0.0303, 2.1217, NOW()),
  ('AAPL', '2026-06-30', '2026-07-30', 1.67, 1.7, -0.03, -0.0176, -1.255, NOW()),
  ('AAPL', '2026-09-30', '2026-10-30', 1.78, 1.74, 0.04, 0.023, 1.2021, NOW()),
  ('ASML', '2022-12-31', '2023-01-16', 4.31, 4.1, 0.21, 0.0512, NULL, NOW()),
  ('ASML', '2023-03-31', '2023-04-16', 4.07, 4.22, -0.15, -0.0355, NULL, NOW()),
  ('ASML', '2023-06-30', '2023-07-16', 4.67, 4.35, 0.32, 0.0736, NULL, NOW()),
  ('ASML', '2023-09-30', '2023-10-16', 4.66, 4.48, 0.18, 0.0402, NULL, NOW()),
  ('ASML', '2023-12-31', '2024-01-16', 4.21, 4.61, -0.4, -0.0868, -1.9755, NOW()),
  ('ASML', '2024-03-31', '2024-04-16', 5.0, 4.75, 0.25, 0.0526, 0.8377, NOW()),
  ('ASML', '2024-06-30', '2024-07-16', 5.01, 4.9, 0.11, 0.0224, 0.3909, NOW()),
  ('ASML', '2024-09-30', '2024-10-16', 5.34, 5.04, 0.3, 0.0595, 1.1657, NOW()),
  ('ASML', '2024-12-31', '2025-01-16', 5.11, 5.19, -0.08, -0.0154, -0.3184, NOW()),
  ('ASML', '2025-03-31', '2025-04-16', 5.79, 5.35, 0.44, 0.0822, 1.7293, NOW()),
  ('ASML', '2025-06-30', '2025-07-16', 5.7, 5.51, 0.19, 0.0345, 0.7091, NOW()),
  ('ASML', '2025-09-30', '2025-10-16', 5.46, 5.68, -0.22, -0.0387, -0.8485, NOW()),
  ('ASML', '2025-12-31', '2026-01-16', 6.21, 5.85, 0.36, 0.0615, 1.2665, NOW()),
  ('ASML', '2026-03-31', '2026-04-16', 6.29, 6.02, 0.27, 0.0449, 1.2059, NOW()),
  ('ASML', '2026-06-30', '2026-07-16', 6.29, 6.2, 0.09, 0.0145, 0.3999, NOW()),
  ('ASML', '2026-09-30', '2026-10-16', 6.54, 6.39, 0.15, 0.0235, 0.6639, NOW());

-- ── Test users (local only) ──────────────────────────────────────────────────
-- Log in at http://localhost:3000/login with either account; password for both: kancil-local-dev
--   admin@kancil.test    app_metadata.role = admin (can delete any ticker)
--   analyst@kancil.test  no role (can only delete tickers they added)
-- Token columns must be '' rather than NULL or Supabase Auth fails to load the user.
INSERT INTO auth.users (
  instance_id, id, aud, role, email, encrypted_password, email_confirmed_at,
  raw_app_meta_data, raw_user_meta_data, created_at, updated_at,
  confirmation_token, recovery_token, email_change_token_new, email_change
)
VALUES
  ('00000000-0000-0000-0000-000000000000', '11111111-1111-1111-1111-111111111111',
   'authenticated', 'authenticated', 'admin@kancil.test',
   extensions.crypt('kancil-local-dev', extensions.gen_salt('bf')), NOW(),
   '{"provider": "email", "providers": ["email"], "role": "admin"}', '{"full_name": "Test Admin"}',
   NOW(), NOW(), '', '', '', ''),
  ('00000000-0000-0000-0000-000000000000', '22222222-2222-2222-2222-222222222222',
   'authenticated', 'authenticated', 'analyst@kancil.test',
   extensions.crypt('kancil-local-dev', extensions.gen_salt('bf')), NOW(),
   '{"provider": "email", "providers": ["email"]}', '{"full_name": "Test Analyst"}',
   NOW(), NOW(), '', '', '', '');

INSERT INTO auth.identities (id, user_id, provider_id, provider, identity_data, last_sign_in_at, created_at, updated_at)
SELECT gen_random_uuid(), u.id, u.id::text, 'email',
       jsonb_build_object('sub', u.id::text, 'email', u.email, 'email_verified', true),
       NOW(), NOW(), NOW()
FROM auth.users u
WHERE u.email IN ('admin@kancil.test', 'analyst@kancil.test');

-- The analyst added NVDA, so ownership checks on /tickers have something to exercise
UPDATE public.tracked_tickers SET added_by = 'analyst@kancil.test' WHERE ticker = 'NVDA';
