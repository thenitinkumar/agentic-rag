"""
Generates a small, self-contained demo corpus so the pipeline is runnable
out of the box without any external dataset:

  - data/docs/*.md    : short "news style" articles about fictional tech
                        companies (unstructured source -> vector store)
  - data/company.db   : a SQLite table of the same companies' structured
                        financials (structured source -> text-to-SQL)

The two sources deliberately overlap on company name so that multi-hop
questions ("which company with >$500M revenue had a product recall?")
require combining both.
"""
import sqlite3
from pathlib import Path

from .config import DOCS_DIR, SQLITE_PATH, DATA_DIR

COMPANIES = [
    dict(name="Nimbusly", sector="Cloud Infrastructure", founded_year=2014,
         employees=4200, revenue_musd=680, headquarters="Austin, TX"),
    dict(name="Verdant Robotics Co", sector="Industrial Robotics", founded_year=2018,
         employees=950, revenue_musd=140, headquarters="Pittsburgh, PA"),
    dict(name="Solace Health AI", sector="Healthcare AI", founded_year=2019,
         employees=610, revenue_musd=95, headquarters="Boston, MA"),
    dict(name="Ferrotype Materials", sector="Advanced Materials", founded_year=2011,
         employees=2200, revenue_musd=410, headquarters="Cleveland, OH"),
    dict(name="Lucent Grid Systems", sector="Energy / Grid Tech", founded_year=2016,
         employees=1800, revenue_musd=530, headquarters="Denver, CO"),
    dict(name="Pallet Logistics", sector="Supply Chain Software", founded_year=2013,
         employees=1300, revenue_musd=310, headquarters="Chicago, IL"),
    dict(name="Aviform Aerospace", sector="Aerospace", founded_year=2009,
         employees=5100, revenue_musd=1250, headquarters="Seattle, WA"),
    dict(name="Cinderloop Media", sector="Consumer Media / Streaming", founded_year=2017,
         employees=870, revenue_musd=220, headquarters="Los Angeles, CA"),
]

ARTICLES = {
    "nimbusly_outage.md": """# Nimbusly Suffers Multi-Region Outage After Config Rollout

Nimbusly, the cloud infrastructure provider, experienced a six-hour outage
across its US-East and EU-West regions after a misconfigured routing
update was pushed to production without a canary rollout. Customer
dashboards were unreachable and several downstream SaaS companies that
depend on Nimbusly's object storage reported cascading failures.

The company's engineering lead said the incident review would focus on
why the change bypassed staged rollout checks, and that a postmortem
would be published within two weeks. This is the second major incident
for Nimbusly in the past year, following a similar but shorter outage
tied to a certificate expiry.
""",
    "nimbusly_funding.md": """# Nimbusly Raises Growth Round Amid Reliability Concerns

Despite recent outages, Nimbusly closed a growth-stage funding round led
by a group of infrastructure-focused investors. The round is intended to
fund expansion of its edge network and to hire a dedicated site
reliability engineering organization, following criticism from customers
about recent downtime.

Analysts noted the raise values the company well above its last round,
suggesting investors remain confident in its long-term positioning in
cloud infrastructure even as reliability questions linger.
""",
    "verdant_recall.md": """# Verdant Robotics Issues Recall on Warehouse Arm Line

Verdant Robotics Co initiated a voluntary recall of its second-generation
warehouse picking arms after several customers reported a gripper
mechanism that could unexpectedly release loads mid-cycle. No injuries
were reported, but the company is offering free replacement units and a
firmware patch.

The recall affects roughly 12% of deployed units. Verdant's leadership
emphasized that the issue was caught through its own internal quality
monitoring rather than a customer complaint, and that a root-cause report
would be shared with affected clients.
""",
    "solace_fda.md": """# Solace Health AI's Diagnostic Model Clears Regulatory Review

Solace Health AI announced that its imaging-triage model received
clearance following an extended regulatory review process. The model is
designed to flag high-priority radiology cases for earlier physician
review rather than to provide a standalone diagnosis.

Hospital partners piloting the tool reported meaningful reductions in
time-to-review for urgent cases during the pilot phase. The company said
it plans to expand pilots to additional hospital networks over the next
two quarters.
""",
    "ferrotype_supply.md": """# Ferrotype Materials Faces Supply Constraints on Key Alloy

Ferrotype Materials, a supplier of advanced alloys used in aerospace and
energy components, disclosed supply constraints tied to a shortage of a
specialty input material. The company said lead times for certain
products had roughly doubled and that it was working with alternate
suppliers to diversify its input sourcing.

Several aerospace manufacturers, including long-time customers, are
reportedly evaluating dual-sourcing strategies as a result.
""",
    "lucent_grid_expansion.md": """# Lucent Grid Systems Wins Multi-State Grid Modernization Contract

Lucent Grid Systems was selected to lead a multi-state grid modernization
initiative aimed at improving load balancing and reducing outage
frequency across aging regional infrastructure. The contract is one of
the largest in the company's history and is expected to be delivered in
phases over three years.

The company's stock-equivalent private valuation rose following the
announcement, with analysts citing the deal as validation of its
software-defined grid control platform.
""",
    "pallet_logistics_partnership.md": """# Pallet Logistics Partners With Regional Carriers on Real-Time Routing

Pallet Logistics announced a partnership with a group of regional freight
carriers to integrate real-time routing optimization into its supply
chain software platform. The partnership is aimed at reducing empty-mile
trips and improving delivery time predictability for mid-size shippers.

Company leadership framed the deal as part of a broader push to move
up-market from small shippers toward larger enterprise logistics
customers.
""",
    "aviform_delay.md": """# Aviform Aerospace Delays Next-Gen Engine Program

Aviform Aerospace confirmed a delay to its next-generation propulsion
program, citing additional certification testing requirements. The
company said the delay would push initial deliveries back by
approximately eight months but did not expect it to materially affect
near-term revenue given its backlog in existing product lines.

Aviform's leadership reiterated confidence in the program's long-term
trajectory and said testing setbacks were within the range anticipated
for a program of this complexity.
""",
    "cinderloop_content.md": """# Cinderloop Media Expands Original Content Slate

Cinderloop Media announced an expanded slate of original content aimed
at growing subscriber retention in a increasingly competitive streaming
market. The company said it would nearly double its original content
budget over the next fiscal year.

Executives pointed to recent subscriber growth as evidence the strategy
is working, though some analysts questioned whether content spending
increases can keep pace with larger, better-capitalized competitors.
""",
}


def write_docs() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    for filename, content in ARTICLES.items():
        (DOCS_DIR / filename).write_text(content.strip() + "\n", encoding="utf-8")


def build_sqlite() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if SQLITE_PATH.exists():
        SQLITE_PATH.unlink()
    conn = sqlite3.connect(SQLITE_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE companies (
            name TEXT PRIMARY KEY,
            sector TEXT,
            founded_year INTEGER,
            employees INTEGER,
            revenue_musd REAL,
            headquarters TEXT
        )
    """)
    cur.executemany(
        "INSERT INTO companies (name, sector, founded_year, employees, revenue_musd, headquarters) "
        "VALUES (:name, :sector, :founded_year, :employees, :revenue_musd, :headquarters)",
        COMPANIES,
    )
    conn.commit()
    conn.close()


def seed_all() -> None:
    write_docs()
    build_sqlite()
    print(f"Wrote {len(ARTICLES)} docs to {DOCS_DIR}")
    print(f"Built SQLite DB with {len(COMPANIES)} rows at {SQLITE_PATH}")


if __name__ == "__main__":
    seed_all()
