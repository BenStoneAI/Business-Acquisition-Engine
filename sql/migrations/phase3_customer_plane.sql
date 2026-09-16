-- Customer plane for Acquisition Radar (RD-02 / H-A10).
-- Shared listing pool is read-only from customer APIs.
-- Operator CLI keeps DATABASE_URL on the original Supabase project.

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
    financing_status TEXT,
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
    max_offer_sde_multiple NUMERIC,
    max_offer_dscr NUMERIC,
    max_offer_coc NUMERIC,
    max_offer_payback NUMERIC,
    max_offer_binding TEXT,
    red_flags TEXT[],
    next_action TEXT
);

CREATE TABLE IF NOT EXISTS pool_runs (
    id BIGSERIAL PRIMARY KEY,
    ran_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    listing_count INT NOT NULL DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS tenants (
    tenant_id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    setup_completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS tenant_criteria (
    tenant_id UUID PRIMARY KEY REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    states TEXT[] NOT NULL DEFAULT '{}',
    metros TEXT[] NOT NULL DEFAULT '{}',
    industries TEXT[] NOT NULL DEFAULT '{}',
    asking_min NUMERIC,
    asking_max NUMERIC,
    sde_min NUMERIC,
    sde_max NUMERIC,
    financing_floor TEXT NOT NULL DEFAULT 'full',
    score_threshold NUMERIC NOT NULL DEFAULT 80,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tenant_matches (
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    listing_id BIGINT NOT NULL REFERENCES business_listings(id) ON DELETE CASCADE,
    matched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    first_seen_score NUMERIC,
    last_score NUMERIC,
    hidden BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (tenant_id, listing_id)
);

CREATE TABLE IF NOT EXISTS tenant_watchlist (
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    listing_id BIGINT NOT NULL REFERENCES business_listings(id) ON DELETE CASCADE,
    notes TEXT,
    priority TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, listing_id)
);

CREATE TABLE IF NOT EXISTS tenant_deals (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    listing_id BIGINT NOT NULL REFERENCES business_listings(id) ON DELETE CASCADE,
    stage TEXT NOT NULL DEFAULT 'contacted',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, listing_id)
);

CREATE TABLE IF NOT EXISTS tenant_deal_stage_history (
    id BIGSERIAL PRIMARY KEY,
    deal_id UUID NOT NULL REFERENCES tenant_deals(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tenant_packets (
    deal_id UUID PRIMARY KEY REFERENCES tenant_deals(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    markdown TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tenant_rescores (
    id BIGSERIAL PRIMARY KEY,
    deal_id UUID NOT NULL REFERENCES tenant_deals(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    verified_sde NUMERIC,
    verified_revenue NUMERIC,
    verified_asking NUMERIC,
    total_score NUMERIC,
    estimated_max_offer NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tenant_alert_prefs (
    tenant_id UUID PRIMARY KEY REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    email_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    telegram_chat_id TEXT,
    digest BOOLEAN NOT NULL DEFAULT FALSE,
    threshold NUMERIC NOT NULL DEFAULT 80,
    price_drop_alerts BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS tenant_alert_log (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    channel TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tenant_settings (
    tenant_id UUID PRIMARY KEY REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    buyer_name TEXT,
    buyer_entity TEXT,
    credibility_blurb TEXT,
    target_close_timeline TEXT
);

CREATE INDEX IF NOT EXISTS idx_tenant_matches_tenant ON tenant_matches(tenant_id);
CREATE INDEX IF NOT EXISTS idx_deal_scores_listing ON deal_scores(listing_id, scored_at DESC);
