-- =============================================================================
-- Local development seed data
-- Runs after all migrations on `supabase db reset`. Never applied to production.
-- Keep it small: just enough for every page to render with real-looking data.
-- =============================================================================

INSERT INTO public.tracked_tickers (ticker, status, sentiment_ready, name, sector, region, country)
VALUES
  ('AAPL', 'held',     TRUE, 'Apple Inc.',         'Technology', 'North America', 'United States'),
  ('NVDA', 'tracking', TRUE, 'NVIDIA Corporation', 'Technology', 'North America', 'United States'),
  ('ASML', 'tracking', TRUE, 'ASML Holding N.V.',  'Technology', 'Europe',        'Netherlands');

INSERT INTO public.articles (id, timestamp, title, body, author, source, url)
OVERRIDING SYSTEM VALUE
VALUES
  (1, NOW() - INTERVAL '1 day',  'Apple beats revenue estimates on services growth', 'Seed article body.', 'Seed', 'reuters',  'https://example.com/seed/1'),
  (2, NOW() - INTERVAL '2 days', 'NVIDIA guidance tops expectations',                 'Seed article body.', 'Seed', 'cnbc',     'https://example.com/seed/2'),
  (3, NOW() - INTERVAL '3 days', 'Export curbs weigh on chip equipment makers',       'Seed article body.', 'Seed', 'ft',       'https://example.com/seed/3'),
  (4, NOW() - INTERVAL '5 days', 'Apple faces antitrust scrutiny in the EU',          'Seed article body.', 'Seed', 'bloomberg','https://example.com/seed/4');

SELECT setval(pg_get_serial_sequence('public.articles', 'id'), (SELECT MAX(id) FROM public.articles));

INSERT INTO public.sentiments (article_id, affected, score, confidence)
VALUES
  (1, 'AAPL',  0.72, 0.91),
  (2, 'NVDA',  0.65, 0.88),
  (3, 'ASML', -0.48, 0.79),
  (3, 'NVDA', -0.21, 0.62),
  (4, 'AAPL', -0.35, 0.74);

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
