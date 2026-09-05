Tier 1 (Run Every Time Before Release)

These are mandatory.

1. /spec-superstar ⭐⭐⭐⭐⭐

Purpose:

Verify every requirement in the acquisition spec exists.
Find missing workflows.
Find contradictory logic.
Ensure no gaps between the spec and implementation.

Output:

Missing features
Incorrect implementations
Unreachable states
Missing edge cases
2. /enhanced-thinking ⭐⭐⭐⭐⭐

Purpose:

Stress test the reasoning.

It should ask things like:

"What assumptions are we making?"

"What if the listing disappears?"

"What if seller financing wording is ambiguous?"

"What if the URL changes?"

It usually finds things humans miss.

3. /build-simplicity-auditor ⭐⭐⭐⭐⭐

This one has probably saved you more complexity than anything else.

It should verify:

every feature earns its place
no duplicate logic
no unnecessary agents
minimum clicks
minimum user decisions

For this engine the goal should literally be

One click from "interesting listing" to "ready to send."

4. /brutal-truth ⭐⭐⭐⭐⭐

Purpose:

Pretend your biggest competitor built this.

Destroy it.

Find:

weaknesses
bad UX
assumptions
scaling issues
maintenance problems

Never ship until this passes.

Tier 2 (Acquisition Specific)
5. Acquisition Auditor (new)

I would build this specifically.

It checks:

Listing discovery

↓

Deduplication

↓

Qualification

↓

Scoring

↓

Watchlist

↓

Change tracking

↓

Seller financing verification

↓

Outreach generation

↓

Due diligence generation

↓

LOI generation

↓

CRM update

↓

Email generation

↓

Calendar

↓

Done

It literally walks every acquisition workflow.

6. Deep Research

Not just Google.

Research:

PE playbooks
ETA (Entrepreneur Through Acquisition)
SBA acquisition checklists
Search Fund models
Harvard search fund studies
Codie Sanchez
Walker Deibel
Main Street Hold Co.
SMB Twitter
Axial
IBBA

Then compare our engine against best practices.

7. FOSS Scrubber

This engine shouldn't pay for things it doesn't need.

Research open-source replacements for:

CRM

Search

Email

OCR

Vector DB

Browser automation

Workflow engine

Document generation

PDF parsing

ETL

Queue

Monitoring

Logging

Everything.

Tier 3 (Simulation)

This is where most systems fail.

8. Massive Simulation Skill

Generate:

100 fake businesses

then

500

then

1,000

Mix:

seller financing

partial financing

retiring owners

bad listings

duplicate listings

fake URLs

sold listings

price drops

removed listings

Then verify the engine classifies every one correctly.

9. Browser Automation Tester

Your Conduit-Halo browser should:

Open listing

Read page

Expand hidden text

Find financing

Capture screenshots

Save PDF

Extract broker

Extract email

Find business website

Search Secretary of State

Search BBB

Search Google Reviews

Search LinkedIn

Generate outreach

Move to next listing

This should run automatically.

10. Agent Orchestration Audit

Verify every agent.

Discovery Agent

↓

Qualification Agent

↓

Finance Agent

↓

Scoring Agent

↓

Risk Agent

↓

Due Diligence Agent

↓

Outreach Agent

↓

Negotiation Agent

↓

CRM Agent

↓

Report Agent

Nothing skipped.

Nothing duplicated.

Tier 4 (End-to-End)

These are my favorite.

11. Human Replacement Test

Ask:

Can this replace a first-year acquisition analyst?

If not,

why?

Fix it.

Repeat.

12. Partner Test

Pretend you're buying a business with another partner.

Could they understand everything?

Could they click one button?

Would they trust it?

13. Buyer Journey Test

Simulate:

Day 1

Find listing.

↓

Day 3

Email seller.

↓

Day 7

Receive NDA.

↓

Day 9

Receive CIM.

↓

Day 11

Review financials.

↓

Day 14

LOI.

↓

Day 30

Due diligence.

↓

Day 45

Close.

The engine should assist every step.

Tier 5 (The One I Would Build Specifically)

This is the biggest one.

Acquisition Operating System Audit

This doesn't just test software.

It tests the entire acquisition process.

It verifies:

✓ Discovery

✓ Qualification

✓ Valuation

✓ Financing

✓ Negotiation

✓ Due diligence

✓ Legal

✓ CPA review

✓ Risk

✓ Closing

✓ Integration

✓ 100-day plan

✓ KPI dashboard

✓ Exit planning

Basically:

Could Blackstone use this?

The Single Most Valuable New Skill

If I could build one new skill for this engine, it would be:

/eta-acquisition-super-auditor

It would combine:

/spec-superstar
/enhanced-thinking
/brutal-truth
/build-simplicity-auditor
/deep-research
massive simulation
browser automation validation
workflow validation
acquisition playbook validation
UX validation
security review
financial-model review
due-diligence completeness
legal-document completeness
seller-financing verification
end-to-end acquisition lifecycle testing

It wouldn't stop after checking that the code works. It would verify that the system can reliably support the full lifecycle of acquiring a real small business—from sourcing and qualification through negotiation, diligence, closing, and post-acquisition integration—while identifying missing capabilities, unnecessary complexity, and opportunities to improve automation. That is the skill I would run before considering this engine production-ready.