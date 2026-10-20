"""
generate_dataset.py
--------------------
Generates a realistic, labeled synthetic dataset of job/internship postings
(real vs fraudulent) into data/raw/job_postings.csv.

v1.1.0 CHANGE: the previous version only generated 8 technical/data-role
titles (Data Engineer Intern, Data Analyst, etc.), across BOTH legit and
fake examples. That meant the trained model never saw a single legitimate
non-technical posting during training — every genuine example mentioned
Python/SQL/AWS/etc. by construction. A real Product Manager, Marketing
Manager, HR, Sales, Finance, Teacher, Healthcare, Operations, Support, or
Admin posting looks "unlike training data" to that model in a way that
skews toward the fraud class, independent of its actual content. This
version generates postings across many categories, each with
category-appropriate legitimate qualifications AND category-appropriate
scam patterns (scams target every job category in the real world, not
just tech — "Data Entry from home", "Customer Support work from home",
and "HR Assistant, no experience" are extremely common real scam
categories), so the model learns "fraud" as a property of the posting's
actual content/behavior, not its subject matter.

In production this pipeline would instead *ingest* a real source such as:
  - the Kaggle "Real / Fake Job Posting Prediction" dataset (~18k rows), or
  - a live scraper/API feed of postings.
That ingestion step is implemented in `ingest.py`, which reads any CSV
dropped into data/raw/ — this script just produces one such CSV so the
whole pipeline is runnable end-to-end without external downloads.

Run:
    python generate_dataset.py --n 6000
"""
import argparse
import random
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

REAL_COMPANIES = [
    "Infosys", "TCS", "Wipro", "Accenture", "Deloitte", "Google", "Microsoft",
    "Amazon", "Flipkart", "Zoho", "Freshworks", "Razorpay", "Swiggy", "Paytm",
    "Capgemini", "IBM", "Cognizant", "HCLTech", "JPMorgan Chase", "Goldman Sachs",
    "Unilever", "Nestle", "Pfizer", "Apollo Hospitals", "Byju's", "Nykaa",
    "HDFC Bank", "ICICI Bank", "Reliance Retail", "Tata Motors",
]
FAKE_COMPANIES = [
    "Global Career Hub", "Quick Earn Solutions", "WorkFromHome Elite",
    "Bright Future Careers", "Instant Job Portal", "Premium Remote Jobs",
    "EliteHire Consultancy", "MegaEarn Pvt Ltd", "NextGen Job Placements",
    "FastTrack Careers Inc",
]
LOCATIONS = ["Bangalore, India", "Hyderabad, India", "Pune, India", "Remote",
             "Chennai, India", "Delhi NCR, India", "Mumbai, India", "Warangal, India",
             "Kolkata, India", "Ahmedabad, India"]
FREE_EMAIL_DOMAINS = ["gmail.com", "yahoo.com", "rediffmail.com", "outlook.com"]

# ---------------------------------------------------------------------
# Job categories: each has role titles, category-appropriate skills to
# mention in LEGIT postings, and a category-appropriate FAKE template
# (scam postings imitate the category they're targeting, not just tech).
# ---------------------------------------------------------------------
CATEGORIES = {
    "technical": {
        "roles": [
            "Data Engineer Intern", "Data Analyst", "Machine Learning Intern",
            "Backend Developer", "Data Scientist", "Software Engineer Intern",
            "Software Engineer", "DevOps Intern", "Full Stack Developer",
            "Cloud Engineer", "QA Engineer", "Site Reliability Engineer",
        ],
        "skills": ["Python", "SQL", "Pandas", "Spark", "Airflow", "AWS", "Docker",
                    "Kubernetes", "React", "Java", "Machine Learning", "ETL", "Kafka",
                    "PostgreSQL", "Git", "Linux"],
        "seniority_extra": ["intern", "entry-level", "senior", "lead"],
    },
    "product": {
        "roles": ["Product Manager", "Associate Product Manager", "Senior Product Manager",
                   "Product Manager, Platform Operations", "Technical Program Manager"],
        "skills": ["product roadmapping", "stakeholder management", "A/B testing",
                    "market research", "user research", "cross-functional leadership",
                    "OKRs", "product analytics", "prioritization frameworks"],
        "seniority_extra": ["associate", "senior", "lead", "group"],
    },
    "marketing": {
        "roles": ["Marketing Manager", "Digital Marketing Executive", "Content Marketing Specialist",
                   "Brand Manager", "Marketing Intern", "Growth Marketing Manager"],
        "skills": ["SEO", "SEM", "content strategy", "Google Analytics",
                    "social media marketing", "brand management", "campaign management",
                    "email marketing"],
        "seniority_extra": ["intern", "associate", "senior"],
    },
    "hr": {
        "roles": ["HR Manager", "HR Recruiter", "Talent Acquisition Specialist",
                   "HR Business Partner", "HR Intern", "People Operations Manager"],
        "skills": ["recruitment", "talent acquisition", "HRIS", "employee relations",
                    "onboarding", "performance management", "payroll"],
        "seniority_extra": ["intern", "associate", "senior"],
    },
    "sales": {
        "roles": ["Sales Executive", "Business Development Manager", "Account Manager",
                   "Inside Sales Representative", "Sales Intern", "Regional Sales Manager"],
        "skills": ["Salesforce", "lead generation", "account management",
                    "negotiation", "quota attainment", "B2B sales", "CRM"],
        "seniority_extra": ["intern", "associate", "senior", "regional"],
    },
    "finance": {
        "roles": ["Financial Analyst", "Accountant", "Finance Manager",
                   "Accounts Payable Associate", "Finance Intern", "Investment Analyst"],
        "skills": ["financial modeling", "GAAP", "bookkeeping", "accounts payable",
                    "budgeting", "forecasting", "Excel", "variance analysis"],
        "seniority_extra": ["intern", "associate", "senior"],
    },
    "design": {
        "roles": ["UX Designer", "UI Designer", "Product Designer", "Graphic Designer",
                   "Design Intern"],
        "skills": ["Figma", "wireframing", "user research", "prototyping",
                    "design systems", "Adobe Creative Suite"],
        "seniority_extra": ["intern", "associate", "senior", "lead"],
    },
    "healthcare": {
        "roles": ["Registered Nurse", "Clinical Coordinator", "Healthcare Administrator",
                   "Medical Assistant", "Patient Care Coordinator"],
        "skills": ["patient care", "clinical procedures", "EMR systems",
                    "care coordination", "medical terminology", "compliance"],
        "seniority_extra": ["junior", "senior", "lead"],
    },
    "operations": {
        "roles": ["Operations Manager", "Operations Analyst", "Supply Chain Coordinator",
                   "Logistics Manager", "Operations Intern"],
        "skills": ["process optimization", "vendor management", "logistics",
                    "supply chain management", "inventory management", "Excel"],
        "seniority_extra": ["intern", "associate", "senior"],
    },
    "support": {
        "roles": ["Customer Support Executive", "Customer Success Manager",
                   "Technical Support Specialist", "Support Intern"],
        "skills": ["ticketing systems", "SLAs", "customer satisfaction",
                    "conflict resolution", "CRM tools"],
        "seniority_extra": ["intern", "associate", "senior"],
    },
    "admin": {
        "roles": ["Administrative Assistant", "Office Manager", "Executive Assistant",
                   "Front Desk Coordinator"],
        "skills": ["scheduling", "office management", "correspondence",
                    "calendar management", "MS Office"],
        "seniority_extra": ["junior", "senior"],
    },
    "teaching": {
        "roles": ["Teacher", "Assistant Teacher", "Curriculum Coordinator",
                   "Online Tutor", "Teaching Intern"],
        "skills": ["curriculum design", "classroom management", "lesson planning",
                    "student assessment", "B.Ed"],
        "seniority_extra": ["assistant", "senior", "lead"],
    },
}

WORK_MODES = ["Remote", "On-site", "Hybrid"]

URGENT_PHRASES = [
    "Immediate joining required!!!", "Apply now, limited seats!!!",
    "Hiring urgently, don't miss this chance!", "Only 2 seats left, act fast!",
    "Join today and start earning immediately!", "Seats filling fast, apply now!",
]
PROMO_PHRASES = [
    "Earn up to Rs. 90,000 per week working from home!",
    "No experience needed, guaranteed placement!",
    "100% job guarantee, pay a small registration fee to start.",
    "Work just 2 hours a day and earn lakhs per month!",
    "Selected candidates will be given a laptop after registration fee payment.",
    "Guaranteed income from day one, no interview required!",
    "Instant hiring, pay a small activation fee to begin training.",
]
INFORMAL_CONTACT_PHRASES = [
    "Message us on WhatsApp to apply.",
    "Send your details on Telegram to confirm your seat.",
    "Contact our recruiter directly on WhatsApp for instant confirmation.",
    "Ping us on WhatsApp with your resume.",
]
LEGIT_SNIPPETS = [
    "We are looking for a motivated {role} to join our growing team.",
    "As a {role}, you will collaborate with cross-functional teams to deliver high-quality outcomes.",
    "The ideal candidate has hands-on experience with {skill} and strong fundamentals in the field.",
    "This is a {duration} role with a competitive stipend/salary, based on performance and experience.",
    "You will work closely with senior stakeholders on high-impact initiatives.",
    "Minimum qualifications: a relevant degree and demonstrated experience in {skill}.",
    "Preferred qualifications: familiarity with {skill} and excellent communication skills.",
    "Responsibilities include planning, execution, and cross-team coordination on key projects.",
]


def _make_email(company: str, is_fake: bool) -> str:
    if is_fake and random.random() < 0.75:
        return f"hr.hiring{random.randint(100,999)}@{random.choice(FREE_EMAIL_DOMAINS)}"
    slug = company.lower().replace(" ", "").replace(".", "").replace("'", "")[:12]
    return f"careers@{slug}.com"


def _make_description(is_fake: bool, role: str, skills_pool: list[str], work_mode: str) -> str:
    parts = [f"Work mode: {work_mode}."]
    if is_fake:
        parts.append(random.choice(URGENT_PHRASES))
        parts.append(f"We are hiring {role}s across India, no interview required.")
        parts.append(random.choice(PROMO_PHRASES))
        if random.random() < 0.6:
            parts.append(random.choice(PROMO_PHRASES))
        if random.random() < 0.5:
            parts.append(random.choice(INFORMAL_CONTACT_PHRASES))
        parts.append("Send your Aadhar card and registration fee to confirm your seat.")
    else:
        duration = random.choice(["6-month", "full-time", "1-year", "permanent"])
        parts.append(random.choice(LEGIT_SNIPPETS).format(role=role, skill=random.choice(skills_pool), duration=duration))
        parts.append(random.choice(LEGIT_SNIPPETS).format(role=role, skill=random.choice(skills_pool), duration=duration))
        skills = ", ".join(random.sample(skills_pool, k=min(random.randint(3, 6), len(skills_pool))))
        parts.append(f"Key skills/qualifications: {skills}.")
        parts.append("Please apply through our official careers portal with your updated resume.")
    return " ".join(parts)


def generate(n: int, fraud_ratio: float = 0.28, seed: int = 42, label_noise: float = 0.06) -> pd.DataFrame:
    """
    label_noise: fraction of rows where the *label* is flipped relative to
    the pattern used to generate the text (simulates real-world annotation
    noise / genuinely ambiguous postings) so the resulting classifier isn't
    trivially, unrealistically perfect — a 100% accuracy synthetic dataset
    reads as data leakage rather than a real result.
    """
    random.seed(seed)
    np.random.seed(seed)
    rows = []
    n_fake = int(n * fraud_ratio)
    generation_labels = [1] * n_fake + [0] * (n - n_fake)
    random.shuffle(generation_labels)

    category_names = list(CATEGORIES.keys())

    for gen_label in generation_labels:
        is_fake_pattern = bool(gen_label)
        category = random.choice(category_names)
        cat_info = CATEGORIES[category]
        role = random.choice(cat_info["roles"])
        skills_pool = cat_info["skills"]
        work_mode = random.choice(WORK_MODES)

        company = random.choice(FAKE_COMPANIES if is_fake_pattern and random.random() < 0.8 else REAL_COMPANIES)

        # Scam postings frequently omit a real, specific employer name —
        # legitimate detailed postings almost always name the company.
        # This is what makes `company_name_missing` a genuinely learnable,
        # honest signal (as opposed to the old, unfixable website-based one).
        company_name_for_row = company
        if is_fake_pattern and random.random() < 0.35:
            company_name_for_row = ""

        location = random.choice(LOCATIONS) if work_mode != "Remote" else "Remote"

        if is_fake_pattern:
            salary_min = random.choice([0, 15000, 40000])
            salary_max = salary_min + random.choice([50000, 80000, 150000])
        else:
            base = random.choice([15000, 25000, 35000, 60000, 90000, 120000])
            salary_min = base
            salary_max = base + random.choice([5000, 10000, 20000, 40000])

        description = _make_description(is_fake_pattern, role, skills_pool, work_mode)
        # occasionally blend in a couple of "off-pattern" sentences so legit
        # posts sometimes contain mild hype language and scam posts sometimes
        # read fairly normally — real postings are messier than a clean rule.
        if random.random() < 0.15:
            filler = (random.choice(URGENT_PHRASES) if not is_fake_pattern
                      else random.choice(LEGIT_SNIPPETS).format(role=role, skill=random.choice(skills_pool), duration="full-time"))
            description += " " + filler

        final_label = gen_label
        if random.random() < label_noise:
            final_label = 1 - gen_label

        rows.append({
            "job_id": str(uuid.uuid4()),
            "title": role,
            "category": category,
            "company_name": company_name_for_row,
            "location": location,
            "employment_type": random.choice(["Internship", "Full-time", "Contract"]),
            "salary_min": salary_min,
            "salary_max": salary_max,
            "contact_email": _make_email(company, is_fake_pattern),
            "description": description,
            "has_company_website": (not is_fake_pattern) or random.random() < 0.1,
            "posted_days_ago": random.randint(0, 60),
            "fraudulent": final_label,
        })

    return pd.DataFrame(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=6000)
    parser.add_argument("--out", type=str, default=str(RAW_DIR / "job_postings.csv"))
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    df = generate(args.n)
    df.to_csv(args.out, index=False)
    print(f"Wrote {len(df)} rows -> {args.out}")
    print(df["fraudulent"].value_counts())
    print("\nCategory distribution:\n", df["category"].value_counts())
