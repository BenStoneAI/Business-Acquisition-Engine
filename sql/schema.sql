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

CREATE TABLE IF NOT EXISTS broker_contacts (
    id BIGSERIAL PRIMARY KEY,
    source TEXT,
    broker_name TEXT,
    brokerage TEXT,
    email TEXT,
    phone TEXT,
    website TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS outreach_log (
    id BIGSERIAL PRIMARY KEY,
    listing_id BIGINT REFERENCES business_listings(id) ON DELETE CASCADE,
    broker_contact_id BIGINT REFERENCES broker_contacts(id),
    outreach_type TEXT,
    subject TEXT,
    body TEXT,
    sent_at TIMESTAMPTZ,
    response_received_at TIMESTAMPTZ,
    next_follow_up_at TIMESTAMPTZ,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS due_diligence_tasks (
    id BIGSERIAL PRIMARY KEY,
    listing_id BIGINT REFERENCES business_listings(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    task TEXT NOT NULL,
    status TEXT DEFAULT 'open',
    owner TEXT,
    due_date DATE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS source_history (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    run_started_at TIMESTAMPTZ DEFAULT now(),
    run_finished_at TIMESTAMPTZ,
    listings_found INT DEFAULT 0,
    new_listings INT DEFAULT 0,
    errors TEXT
);

CREATE INDEX IF NOT EXISTS idx_business_listings_industry ON business_listings(industry);
CREATE INDEX IF NOT EXISTS idx_business_listings_location ON business_listings(location);
CREATE INDEX IF NOT EXISTS idx_business_listings_seller_financing ON business_listings(seller_financing);
CREATE INDEX IF NOT EXISTS idx_deal_scores_total_score ON deal_scores(total_score DESC);
