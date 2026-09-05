-- Phase 2 migration: ONLY business_listings + deal_scores (+ their indexes).
-- The other 4 tables in sql/schema.sql (broker_contacts, outreach_log,
-- due_diligence_tasks, source_history) belong to a Phase 3 migration.
--
-- Applied 2026-07-04 to Supabase project fdnwlcomuddzmluvbylg inside the
-- dedicated "radar" schema (free-tier project limit; isolated role radar_app).
-- Table names below are unqualified: set search_path (DATABASE_SCHEMA env var)
-- to choose the target schema at apply/connect time.

CREATE TABLE IF NOT EXISTS business_listings (
    id BIGSERIAL PRIMARY KEY,
    business_name TEXT NOT NULL,
    industry TEXT NOT NULL,
    location TEXT,
    asking_price NUMERIC,
    revenue NUMERIC,
    sde NUMERIC,
    ebitda NUMERIC,
    real_estate_included BOOLEAN DEFAULT FALSE,
    seller_financing BOOLEAN DEFAULT FALSE,
    sba_prequalified BOOLEAN DEFAULT FALSE,
    reason_for_sale TEXT,
    years_in_business INT,
    employees INT,
    owner_hours_per_week NUMERIC,
    recurring_revenue_pct NUMERIC,
    customer_concentration_pct NUMERIC,
    equipment_condition TEXT,
    lease_years_remaining NUMERIC,
    source TEXT,
    listing_url TEXT UNIQUE,
    notes TEXT,
    raw_json JSONB,
    first_seen_at TIMESTAMPTZ DEFAULT now(),
    last_seen_at TIMESTAMPTZ DEFAULT now(),
    status TEXT DEFAULT 'new'
);

CREATE TABLE IF NOT EXISTS deal_scores (
    id BIGSERIAL PRIMARY KEY,
    listing_id BIGINT REFERENCES business_listings(id) ON DELETE CASCADE,
    scored_at TIMESTAMPTZ DEFAULT now(),
    total_score NUMERIC NOT NULL,
    bucket TEXT NOT NULL,
    financial_score NUMERIC,
    industry_score NUMERIC,
    recurring_revenue_score NUMERIC,
    seller_motivation_score NUMERIC,
    owner_independence_score NUMERIC,
    financing_fit_score NUMERIC,
    growth_upside_score NUMERIC,
    risk_score NUMERIC,
    bonus_points NUMERIC,
    deal_killer_penalty NUMERIC,
    cash_flow_yield NUMERIC,
    payback_years NUMERIC,
    estimated_value_low NUMERIC,
    estimated_value_high NUMERIC,
    estimated_max_offer NUMERIC,
    red_flags TEXT[],
    next_action TEXT
);

CREATE INDEX IF NOT EXISTS idx_business_listings_industry ON business_listings(industry);
CREATE INDEX IF NOT EXISTS idx_business_listings_location ON business_listings(location);
CREATE INDEX IF NOT EXISTS idx_business_listings_seller_financing ON business_listings(seller_financing);
CREATE INDEX IF NOT EXISTS idx_deal_scores_total_score ON deal_scores(total_score DESC);
