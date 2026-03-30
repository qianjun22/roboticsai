"""
contract_generator.py — OCI Robot Cloud Design Partner Contract Generator

Generates standard design partner contracts and SLA documents for NVIDIA-referred
startups. Speeds up the sales process by producing Pilot, Growth, and Enterprise
agreements programmatically.

Contract Types:
  - Pilot Agreement     (3-month)
  - Growth Agreement    (12-month)
  - Enterprise Agreement (24-month)

SLA Commitments by Tier:
  Tier        Uptime    Response  Fine-tune Turnaround
  starter     99.5%     <4h       <48h
  growth      99.9%     <2h       <24h
  enterprise  99.95%    <1h       <8h

Pricing (all-in, includes GPU hours + support):
  starter:    $500/mo
  growth:     $2,000/mo
  enterprise: $8,000/mo

GPU rate: $4.20/hr (OCI standard)

Usage (CLI):
    python src/api/contract_generator.py \\
        --partner "ACME Robotics" \\
        --tier growth \\
        --output /tmp/acme_contract.md

    python src/api/contract_generator.py \\
        --partner "BotWorks" \\
        --tier enterprise \\
        --start-date 2026-04-01 \\
        --monthly-gpu-hours 2000 \\
        --output /tmp/botworks_contract.md

Usage (server):
    python src/api/contract_generator.py --serve
    # → FastAPI at http://localhost:8055
    # → HTML form at http://localhost:8055/
    # → POST /generate with JSON body → contract markdown

REST API:
    POST /generate
    {
        "partner_name": "ACME Robotics",
        "tier": "growth",
        "start_date": "2026-04-01",          # optional, defaults to today
        "monthly_gpu_hours": 500,             # optional, uses tier default
        "price_per_gpu_hour": 4.20,          # optional, default 4.20
        "support_tier": "slack",              # optional, uses tier default
        "contract_type": "Growth Agreement"  # optional, uses tier default
    }
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from typing import Optional

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

TIER_DEFAULTS = {
    "starter": {
        "contract_months": 3,
        "contract_type": "Pilot Agreement",
        "monthly_gpu_hours": 200,
        "monthly_base_price": 500,
        "uptime_sla": "99.5%",
        "response_time_sla": "<4 hours",
        "finetune_turnaround_sla": "<48 hours",
        "support_tier": "email",
    },
    "growth": {
        "contract_months": 12,
        "contract_type": "Growth Agreement",
        "monthly_gpu_hours": 500,
        "monthly_base_price": 2000,
        "uptime_sla": "99.9%",
        "response_time_sla": "<2 hours",
        "finetune_turnaround_sla": "<24 hours",
        "support_tier": "slack",
    },
    "enterprise": {
        "contract_months": 24,
        "contract_type": "Enterprise Agreement",
        "monthly_gpu_hours": 2000,
        "monthly_base_price": 8000,
        "uptime_sla": "99.95%",
        "response_time_sla": "<1 hour",
        "finetune_turnaround_sla": "<8 hours",
        "support_tier": "dedicated_csm",
    },
}

SUPPORT_TIER_LABELS = {
    "email": "Email Support (business hours, SLA response <4h)",
    "slack": "Dedicated Slack Channel (24×7 monitoring, SLA response <2h)",
    "dedicated_csm": "Dedicated Customer Success Manager + Slack + Phone (24×7, SLA response <1h)",
}


@dataclass
class ContractRequest:
    partner_name: str
    tier: str  # starter | growth | enterprise
    start_date: str = ""  # ISO YYYY-MM-DD; defaults to today
    monthly_gpu_hours: Optional[int] = None
    price_per_gpu_hour: float = 4.20
    support_tier: Optional[str] = None
    contract_type: Optional[str] = None

    def __post_init__(self):
        self.tier = self.tier.lower()
        if self.tier not in TIER_DEFAULTS:
            raise ValueError(f"tier must be one of: {list(TIER_DEFAULTS.keys())}")
        if not self.start_date:
            self.start_date = date.today().isoformat()
        defaults = TIER_DEFAULTS[self.tier]
        if self.monthly_gpu_hours is None:
            self.monthly_gpu_hours = defaults["monthly_gpu_hours"]
        if self.support_tier is None:
            self.support_tier = defaults["support_tier"]
        if self.contract_type is None:
            self.contract_type = defaults["contract_type"]


@dataclass
class ContractMetadata:
    partner_name: str
    tier: str
    contract_type: str
    start_date: str
    end_date: str
    contract_months: int
    monthly_gpu_hours: int
    price_per_gpu_hour: float
    monthly_base_price: int
    total_contract_value: float
    support_tier: str
    uptime_sla: str
    response_time_sla: str
    finetune_turnaround_sla: str
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    contract_id: str = ""

    def __post_init__(self):
        if not self.contract_id:
            slug = self.partner_name.lower().replace(" ", "-")[:20]
            self.contract_id = f"OCI-RC-{self.start_date[:7].replace('-','')}-{slug}"


# ---------------------------------------------------------------------------
# Generator logic
# ---------------------------------------------------------------------------

def _compute_end_date(start_iso: str, months: int) -> str:
    d = date.fromisoformat(start_iso)
    year = d.year + (d.month - 1 + months) // 12
    month = (d.month - 1 + months) % 12 + 1
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    end_day = min(d.day, last_day)
    return date(year, month, end_day).isoformat()


def generate_contract(req: ContractRequest) -> tuple[str, ContractMetadata]:
    """Return (markdown_text, metadata) for the given ContractRequest."""
    defaults = TIER_DEFAULTS[req.tier]
    contract_months = defaults["contract_months"]
    monthly_base_price = defaults["monthly_base_price"]
    uptime_sla = defaults["uptime_sla"]
    response_time_sla = defaults["response_time_sla"]
    finetune_turnaround_sla = defaults["finetune_turnaround_sla"]

    end_date = _compute_end_date(req.start_date, contract_months)
    gpu_cost_monthly = req.monthly_gpu_hours * req.price_per_gpu_hour
    total_monthly = monthly_base_price
    total_contract_value = total_monthly * contract_months
    support_label = SUPPORT_TIER_LABELS.get(req.support_tier, req.support_tier)

    meta = ContractMetadata(
        partner_name=req.partner_name,
        tier=req.tier,
        contract_type=req.contract_type,
        start_date=req.start_date,
        end_date=end_date,
        contract_months=contract_months,
        monthly_gpu_hours=req.monthly_gpu_hours,
        price_per_gpu_hour=req.price_per_gpu_hour,
        monthly_base_price=monthly_base_price,
        total_contract_value=total_contract_value,
        support_tier=req.support_tier,
        uptime_sla=uptime_sla,
        response_time_sla=response_time_sla,
        finetune_turnaround_sla=finetune_turnaround_sla,
    )

    md = f"""\
# OCI Robot Cloud — {req.contract_type}

**Contract ID:** {meta.contract_id}
**Generated:** {meta.generated_at[:10]}
**Status:** DRAFT — Pending Signature

---

## Parties

**Service Provider:**
Oracle America, Inc. (OCI Robot Cloud Team)
500 Oracle Parkway, Redwood City, CA 94065
Contact: Jun Qian, Senior Director — OCI Robot Cloud
Email: jun.q.qian@oracle.com

**Design Partner ("Partner"):**
{req.partner_name}

---

## Agreement Term

| Field | Value |
|-------|-------|
| Contract Type | {req.contract_type} |
| Term | {contract_months} months |
| Start Date | {req.start_date} |
| End Date | {end_date} |
| Tier | {req.tier.capitalize()} |

---

## Scope of Services

Oracle grants Partner access to the OCI Robot Cloud platform, including:

1. **Robot Foundation Model Inference** — GR00T N1.5/N1.6 and OpenVLA-OFT inference endpoints via REST API
2. **Fine-Tuning Service** — Managed fine-tuning pipelines on OCI A100 GPU clusters using Partner-provided or co-generated datasets
3. **Synthetic Data Generation (SDG)** — Isaac Sim–based domain-randomized trajectory generation
4. **Closed-Loop Evaluation** — Automated policy evaluation with configurable task suites
5. **SDK & Tooling** — `oci-robot-cloud` Python SDK, CLI, and documentation portal
6. **Oracle Government Cloud Compliance** — FedRAMP-aligned infrastructure; data residency in Oracle US-Ashburn-1 or US-Phoenix-1 regions

---

## Pricing & GPU Allocation

| Line Item | Details | Monthly Cost |
|-----------|---------|-------------|
| Platform Base Fee ({req.tier.capitalize()} Tier) | All included services | ${monthly_base_price:,.0f} |
| Included GPU Hours | {req.monthly_gpu_hours} hrs/mo @ ${req.price_per_gpu_hour:.2f}/hr OCI rate | Included |
| Overage Rate | Beyond {req.monthly_gpu_hours} hrs/mo | ${req.price_per_gpu_hour:.2f}/GPU-hr |
| Support | {support_label} | Included |
| **Total Monthly** | | **${total_monthly:,.0f}** |

**Total Contract Value ({contract_months} months):** ${total_contract_value:,.0f}

GPU overage invoiced monthly in arrears based on actual usage from OCI billing telemetry.
All prices in USD. Invoices due Net-30.

---

## Service Level Agreement (SLA)

### Platform Uptime

| Metric | Commitment |
|--------|-----------|
| Monthly Uptime SLA | {uptime_sla} |
| Measurement Window | Calendar month |
| Exclusions | Scheduled maintenance (≥72h advance notice), Force majeure |

**SLA Credits:** Uptime below commitment triggers service credits:

| Uptime Achieved | Credit |
|----------------|--------|
| 99.0% – {uptime_sla[:-1]}% | 10% of monthly fee |
| 95.0% – 99.0% | 25% of monthly fee |
| < 95.0% | 50% of monthly fee |

Credits applied to next invoice; not redeemable for cash.

### Support Response Times

| Severity | Description | Response SLA |
|----------|-------------|-------------|
| P1 — Critical | Inference API down, all requests failing | {response_time_sla} |
| P2 — High | Fine-tune jobs failing, >50% error rate | {response_time_sla} |
| P3 — Medium | Performance degradation, partial failures | 1 business day |
| P4 — Low | Feature requests, documentation, billing questions | 3 business days |

### Fine-Tuning Service SLA

| Metric | Commitment |
|--------|-----------|
| Job Start Latency | < 15 minutes from submission |
| Standard Fine-Tune Turnaround | {finetune_turnaround_sla} (up to 1,000 demonstrations, ≤2,000 steps) |
| Large Dataset Turnaround | Mutually agreed upon at job submission |
| Model Delivery | Via OCI Object Storage pre-authenticated URL + SDK auto-download |

---

## Data & Intellectual Property

1. **Partner Data Ownership.** All training datasets, demonstrations, and proprietary robot configurations provided by Partner remain the sole property of Partner. Oracle acquires no IP rights to Partner's data.
2. **Model Outputs.** Fine-tuned model weights produced from Partner's data are owned by Partner. Oracle retains a non-exclusive license to use anonymized training metrics for platform improvement.
3. **Oracle Platform.** The OCI Robot Cloud infrastructure, base model weights (GR00T, OpenVLA), and Oracle-developed tooling remain Oracle's intellectual property.
4. **Data Isolation.** Partner data is stored in isolated OCI Object Storage buckets with tenant-specific encryption keys. No cross-tenant data access.
5. **Data Retention.** Oracle retains Partner data for 90 days post-contract unless Partner requests earlier deletion. Partner may export all data at any time during the term.
6. **No Training on Partner Data.** Oracle will not use Partner's proprietary data to train or improve Oracle's base models without explicit written consent.

---

## Design Partner Program Obligations

In exchange for the Design Partner pricing and early access, Partner agrees to:

1. **Feedback Cadence.** Participate in bi-weekly 30-minute syncs with the OCI Robot Cloud product team for the first 3 months; monthly thereafter.
2. **Case Study.** Provide a publishable case study or quote within 6 months of go-live (subject to Partner's legal review and approval).
3. **NVIDIA Co-Marketing.** If Partner was referred by NVIDIA, participate in at least one joint NVIDIA-Oracle co-marketing activity (blog post, webinar, or conference presentation) per year.
4. **Usage Minimums.** Use at least 50% of contracted GPU hours per month on average over any rolling 3-month period. Persistent under-utilization may result in tier downgrade with 30 days notice.

---

## Termination

1. **Convenience.** Either party may terminate this Agreement with **30 days written notice** to the other party.
2. **For Cause.** Either party may terminate immediately upon material breach if the breach is not cured within 15 days of written notice.
3. **Effect of Termination.** Upon termination: (a) Partner access to the platform is revoked; (b) Oracle will make Partner data available for download for 30 days; (c) fees for the current billing period are non-refundable; (d) pre-paid fees for future periods are refunded pro-rata.

---

## Oracle Government Cloud Compliance

This service is operated on Oracle Cloud Infrastructure with the following compliance posture:

- **FedRAMP Moderate** authorization (US Government regions)
- **SOC 2 Type II** certified
- **ISO 27001** certified
- **GDPR** compliant data processing (EU Standard Contractual Clauses available on request)
- **Data Residency:** US-Ashburn-1 (primary) and US-Phoenix-1 (DR) unless Partner specifies otherwise
- **Encryption:** AES-256 at rest; TLS 1.3 in transit; Customer-Managed Keys (CMK) available on Enterprise tier

---

## General Terms

1. **Governing Law.** This Agreement is governed by the laws of the State of California, without regard to conflict of law principles. Disputes subject to binding arbitration in San Francisco, CA under AAA Commercial Rules.
2. **Limitation of Liability.** Oracle's aggregate liability shall not exceed the total fees paid by Partner in the 3 months preceding the claim.
3. **Warranty Disclaimer.** Services provided "AS IS" with SLA credits as sole remedy for uptime failures.
4. **Entire Agreement.** This document constitutes the entire agreement between the parties and supersedes all prior negotiations.
5. **Amendments.** Must be in writing and signed by both parties.
6. **Notices.** Written notices via email to designated contacts are binding.

---

## Signatures

By signing below, both parties agree to the terms of this {req.contract_type}.

**Oracle America, Inc.**

Signature: ___________________________
Name: Jun Qian
Title: Senior Director, OCI Robot Cloud
Date: ___________________________

**{req.partner_name}**

Signature: ___________________________
Name: ___________________________
Title: ___________________________
Date: ___________________________

---

*This document was generated by OCI Robot Cloud Contract Generator v1.0.*
*Contract ID: {meta.contract_id} | Generated: {meta.generated_at[:10]}*
"""

    return md, meta


# ---------------------------------------------------------------------------
# Sample contracts (3 of the 5 design partners)
# ---------------------------------------------------------------------------

SAMPLE_CONTRACTS = [
    ContractRequest(
        partner_name="Figure AI",
        tier="enterprise",
        start_date="2026-04-01",
        monthly_gpu_hours=2500,
    ),
    ContractRequest(
        partner_name="Physical Intelligence (Pi)",
        tier="growth",
        start_date="2026-04-01",
        monthly_gpu_hours=600,
    ),
    ContractRequest(
        partner_name="Apptronik",
        tier="starter",
        start_date="2026-04-15",
        monthly_gpu_hours=200,
    ),
]


def generate_sample_contracts(output_dir: str = "/tmp") -> list[dict]:
    """Generate all sample design partner contracts and return metadata list."""
    import os
    results = []
    for req in SAMPLE_CONTRACTS:
        md, meta = generate_contract(req)
        slug = req.partner_name.lower().replace(" ", "-").replace("(", "").replace(")", "")
        md_path = os.path.join(output_dir, f"{slug}_contract.md")
        json_path = os.path.join(output_dir, f"{slug}_contract.json")
        with open(md_path, "w") as f:
            f.write(md)
        with open(json_path, "w") as f:
            json.dump(asdict(meta), f, indent=2)
        results.append({"partner": req.partner_name, "md": md_path, "json": json_path, "meta": asdict(meta)})
        print(f"[sample] {req.partner_name} → {md_path}")
    return results


# ---------------------------------------------------------------------------
# FastAPI service
# ---------------------------------------------------------------------------

HTML_FORM = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OCI Robot Cloud — Contract Generator</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: #0d1117;
    color: #e6edf3;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 40px 20px;
  }
  .header {
    text-align: center;
    margin-bottom: 36px;
  }
  .header h1 {
    font-size: 1.8rem;
    font-weight: 700;
    color: #58a6ff;
    letter-spacing: -0.5px;
  }
  .header p {
    color: #8b949e;
    margin-top: 8px;
    font-size: 0.9rem;
  }
  .card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 32px;
    width: 100%;
    max-width: 680px;
  }
  .section-title {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #8b949e;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid #30363d;
  }
  .field-group {
    margin-bottom: 20px;
  }
  label {
    display: block;
    font-size: 0.85rem;
    color: #c9d1d9;
    margin-bottom: 6px;
    font-weight: 500;
  }
  input, select {
    width: 100%;
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    color: #e6edf3;
    padding: 10px 12px;
    font-size: 0.9rem;
    outline: none;
    transition: border-color 0.15s;
  }
  input:focus, select:focus {
    border-color: #58a6ff;
    box-shadow: 0 0 0 3px rgba(88,166,255,0.12);
  }
  select option { background: #161b22; }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .tier-cards {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-bottom: 20px;
  }
  .tier-card {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 14px;
    cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
    text-align: center;
  }
  .tier-card:hover { border-color: #58a6ff; }
  .tier-card.selected {
    border-color: #58a6ff;
    background: rgba(88,166,255,0.08);
  }
  .tier-card .name { font-weight: 600; font-size: 0.9rem; color: #e6edf3; }
  .tier-card .price { font-size: 1.1rem; color: #58a6ff; font-weight: 700; margin: 4px 0; }
  .tier-card .detail { font-size: 0.72rem; color: #8b949e; line-height: 1.4; }
  .btn {
    width: 100%;
    background: #238636;
    border: 1px solid #2ea043;
    color: #fff;
    padding: 12px;
    border-radius: 8px;
    font-size: 0.95rem;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.15s;
    margin-top: 8px;
  }
  .btn:hover { background: #2ea043; }
  .btn-secondary {
    background: #21262d;
    border-color: #30363d;
    color: #c9d1d9;
    margin-top: 8px;
  }
  .btn-secondary:hover { background: #30363d; }
  .output-area {
    margin-top: 28px;
    display: none;
  }
  .output-area.visible { display: block; }
  .output-tabs {
    display: flex;
    gap: 4px;
    margin-bottom: 12px;
  }
  .tab {
    padding: 6px 14px;
    border-radius: 6px 6px 0 0;
    font-size: 0.82rem;
    cursor: pointer;
    background: #0d1117;
    border: 1px solid #30363d;
    border-bottom: none;
    color: #8b949e;
  }
  .tab.active { background: #1c2128; color: #e6edf3; border-color: #444c56; }
  .output-box {
    background: #1c2128;
    border: 1px solid #444c56;
    border-radius: 0 8px 8px 8px;
    padding: 20px;
    overflow: auto;
    max-height: 540px;
    font-size: 0.82rem;
    white-space: pre-wrap;
    line-height: 1.6;
    color: #c9d1d9;
    display: none;
  }
  .output-box.visible { display: block; }
  .meta-table { border-collapse: collapse; width: 100%; font-size: 0.82rem; }
  .meta-table td { padding: 6px 10px; border-bottom: 1px solid #30363d; }
  .meta-table td:first-child { color: #8b949e; width: 40%; }
  .meta-table td:last-child { color: #e6edf3; font-weight: 500; }
  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
  }
  .badge-green { background: rgba(46,164,79,0.2); color: #3fb950; }
  .badge-blue { background: rgba(88,166,255,0.15); color: #58a6ff; }
  .badge-gold { background: rgba(210,153,34,0.2); color: #d29922; }
  .spinner { display: none; text-align: center; padding: 20px; color: #8b949e; font-size: 0.85rem; }
  .spinner.visible { display: block; }
  .error-msg { color: #f85149; font-size: 0.85rem; padding: 10px; background: rgba(248,81,73,0.1); border-radius: 6px; display: none; margin-top: 12px; }
  .error-msg.visible { display: block; }
  .samples-section { margin-top: 28px; }
  .sample-chip {
    display: inline-block;
    margin: 4px;
    padding: 5px 12px;
    background: #21262d;
    border: 1px solid #30363d;
    border-radius: 20px;
    font-size: 0.78rem;
    color: #c9d1d9;
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
  }
  .sample-chip:hover { background: #30363d; border-color: #58a6ff; color: #58a6ff; }
  .footer { margin-top: 40px; color: #484f58; font-size: 0.75rem; text-align: center; }
</style>
</head>
<body>

<div class="header">
  <h1>OCI Robot Cloud</h1>
  <p>Design Partner Contract Generator &nbsp;·&nbsp; NVIDIA-Referred Startup Program</p>
</div>

<div class="card">
  <div class="section-title">Contract Details</div>

  <div class="field-group">
    <label>Partner / Company Name *</label>
    <input type="text" id="partner_name" placeholder="e.g. ACME Robotics" />
  </div>

  <div class="section-title" style="margin-top: 20px;">Select Tier</div>
  <div class="tier-cards">
    <div class="tier-card" data-tier="starter" onclick="selectTier('starter')">
      <div class="name">Starter</div>
      <div class="price">$500<span style="font-size:0.7rem;color:#8b949e">/mo</span></div>
      <div class="detail">3-month Pilot<br>200 GPU hrs/mo<br>99.5% uptime<br>Email support</div>
    </div>
    <div class="tier-card selected" data-tier="growth" onclick="selectTier('growth')">
      <div class="name">Growth</div>
      <div class="price">$2,000<span style="font-size:0.7rem;color:#8b949e">/mo</span></div>
      <div class="detail">12-month Growth<br>500 GPU hrs/mo<br>99.9% uptime<br>Slack support</div>
    </div>
    <div class="tier-card" data-tier="enterprise" onclick="selectTier('enterprise')">
      <div class="name">Enterprise</div>
      <div class="price">$8,000<span style="font-size:0.7rem;color:#8b949e">/mo</span></div>
      <div class="detail">24-month Enterprise<br>2000 GPU hrs/mo<br>99.95% uptime<br>Dedicated CSM</div>
    </div>
  </div>
  <input type="hidden" id="tier" value="growth" />

  <div class="grid-2">
    <div class="field-group">
      <label>Start Date</label>
      <input type="date" id="start_date" />
    </div>
    <div class="field-group">
      <label>Monthly GPU Hours (override)</label>
      <input type="number" id="monthly_gpu_hours" placeholder="Leave blank for tier default" min="1" />
    </div>
  </div>

  <div class="grid-2">
    <div class="field-group">
      <label>Price per GPU Hour (USD)</label>
      <input type="number" id="price_per_gpu_hour" value="4.20" step="0.01" min="0.01" />
    </div>
    <div class="field-group">
      <label>Support Tier (override)</label>
      <select id="support_tier">
        <option value="">— Use tier default —</option>
        <option value="email">Email</option>
        <option value="slack">Slack Channel</option>
        <option value="dedicated_csm">Dedicated CSM</option>
      </select>
    </div>
  </div>

  <button class="btn" onclick="generateContract()">Generate Contract</button>

  <div class="spinner" id="spinner">Generating contract...</div>
  <div class="error-msg" id="error-msg"></div>

  <div class="samples-section">
    <div class="section-title" style="margin-top: 0;">Quick Fill — Design Partners</div>
    <div>
      <span class="sample-chip" onclick="fillSample('Figure AI','enterprise')">Figure AI (Enterprise)</span>
      <span class="sample-chip" onclick="fillSample('Physical Intelligence (Pi)','growth')">Pi (Growth)</span>
      <span class="sample-chip" onclick="fillSample('Apptronik','starter')">Apptronik (Starter)</span>
      <span class="sample-chip" onclick="fillSample('Skild AI','growth')">Skild AI (Growth)</span>
      <span class="sample-chip" onclick="fillSample('Neura Robotics','enterprise')">Neura Robotics (Enterprise)</span>
    </div>
  </div>
</div>

<div class="card output-area" id="output-area">
  <div class="output-tabs">
    <div class="tab active" id="tab-preview" onclick="switchTab('preview')">Preview</div>
    <div class="tab" id="tab-meta" onclick="switchTab('meta')">Metadata</div>
    <div class="tab" id="tab-raw" onclick="switchTab('raw')">Raw Markdown</div>
  </div>
  <div class="output-box visible" id="box-preview"></div>
  <div class="output-box" id="box-meta"></div>
  <div class="output-box" id="box-raw"></div>
  <button class="btn btn-secondary" onclick="downloadMd()">Download .md</button>
</div>

<div class="footer">OCI Robot Cloud Contract Generator v1.0 &nbsp;·&nbsp; Port 8055 &nbsp;·&nbsp; Oracle Confidential</div>

<script>
let lastMarkdown = '';
let lastMeta = {};

function selectTier(tier) {
  document.querySelectorAll('.tier-card').forEach(c => c.classList.remove('selected'));
  document.querySelector('[data-tier="' + tier + '"]').classList.add('selected');
  document.getElementById('tier').value = tier;
}

function fillSample(name, tier) {
  document.getElementById('partner_name').value = name;
  selectTier(tier);
  document.getElementById('monthly_gpu_hours').value = '';
  document.getElementById('support_tier').value = '';
  const today = new Date().toISOString().slice(0, 10);
  document.getElementById('start_date').value = today;
}

function switchTab(tab) {
  ['preview','meta','raw'].forEach(t => {
    document.getElementById('tab-'+t).classList.toggle('active', t === tab);
    document.getElementById('box-'+t).classList.toggle('visible', t === tab);
  });
}

async function generateContract() {
  const partner = document.getElementById('partner_name').value.trim();
  if (!partner) { showError('Partner name is required.'); return; }

  clearError();
  showSpinner(true);
  hideOutput();

  const body = {
    partner_name: partner,
    tier: document.getElementById('tier').value,
    start_date: document.getElementById('start_date').value || undefined,
    price_per_gpu_hour: parseFloat(document.getElementById('price_per_gpu_hour').value) || 4.20,
  };
  const gpuHours = document.getElementById('monthly_gpu_hours').value;
  if (gpuHours) body.monthly_gpu_hours = parseInt(gpuHours);
  const supportTier = document.getElementById('support_tier').value;
  if (supportTier) body.support_tier = supportTier;

  try {
    const resp = await fetch('/generate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || 'Server error');
    }
    const data = await resp.json();
    lastMarkdown = data.markdown;
    lastMeta = data.metadata;
    renderOutput(data);
  } catch(e) {
    showError(e.message);
  } finally {
    showSpinner(false);
  }
}

function renderOutput(data) {
  // Preview — simple markdown-to-html
  let html = data.markdown
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/^# (.+)$/gm, '<h2 style="color:#58a6ff;font-size:1.2rem;margin:16px 0 8px">$1</h2>')
    .replace(/^## (.+)$/gm, '<h3 style="color:#c9d1d9;font-size:1rem;margin:14px 0 6px">$1</h3>')
    .replace(/^### (.+)$/gm, '<h4 style="color:#8b949e;font-size:0.9rem;margin:10px 0 4px">$1</h4>')
    .replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>')
    .replace(/^---$/gm, '<hr style="border:none;border-top:1px solid #30363d;margin:12px 0">')
    .replace(/^\\| (.+) \\|$/gm, m => '<div style="font-family:monospace;font-size:0.78rem;color:#8b949e;padding:2px 0">' + m + '</div>');
  document.getElementById('box-preview').innerHTML = html;

  // Raw markdown
  document.getElementById('box-raw').textContent = data.markdown;

  // Metadata table
  const m = data.metadata;
  const tierBadge = {starter:'badge-green',growth:'badge-blue',enterprise:'badge-gold'}[m.tier] || 'badge-blue';
  document.getElementById('box-meta').innerHTML = `
    <table class="meta-table">
      <tr><td>Contract ID</td><td><code style="color:#58a6ff">${m.contract_id}</code></td></tr>
      <tr><td>Partner</td><td>${m.partner_name}</td></tr>
      <tr><td>Tier</td><td><span class="badge ${tierBadge}">${m.tier}</span></td></tr>
      <tr><td>Contract Type</td><td>${m.contract_type}</td></tr>
      <tr><td>Term</td><td>${m.start_date} → ${m.end_date} (${m.contract_months} months)</td></tr>
      <tr><td>GPU Hours/mo</td><td>${m.monthly_gpu_hours.toLocaleString()} hrs @ $${m.price_per_gpu_hour.toFixed(2)}/hr</td></tr>
      <tr><td>Monthly Base Price</td><td>$${m.monthly_base_price.toLocaleString()}</td></tr>
      <tr><td>Total Contract Value</td><td style="color:#3fb950;font-weight:700">$${m.total_contract_value.toLocaleString()}</td></tr>
      <tr><td>Support Tier</td><td>${m.support_tier}</td></tr>
      <tr><td>Uptime SLA</td><td>${m.uptime_sla}</td></tr>
      <tr><td>Response Time SLA</td><td>${m.response_time_sla}</td></tr>
      <tr><td>Fine-tune Turnaround</td><td>${m.finetune_turnaround_sla}</td></tr>
      <tr><td>Generated At</td><td>${m.generated_at}</td></tr>
    </table>`;

  document.getElementById('output-area').classList.add('visible');
  switchTab('preview');
}

function downloadMd() {
  if (!lastMarkdown) return;
  const slug = (lastMeta.partner_name || 'contract').toLowerCase().replace(/[^a-z0-9]+/g,'-');
  const blob = new Blob([lastMarkdown], {type:'text/markdown'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = slug + '_contract.md';
  a.click();
}

function showError(msg) {
  const el = document.getElementById('error-msg');
  el.textContent = msg;
  el.classList.add('visible');
}
function clearError() { document.getElementById('error-msg').classList.remove('visible'); }
function showSpinner(v) { document.getElementById('spinner').classList.toggle('visible', v); }
function hideOutput() { document.getElementById('output-area').classList.remove('visible'); }

// Set default start date to today
document.getElementById('start_date').value = new Date().toISOString().slice(0,10);
</script>
</body>
</html>
"""


def create_app():
    try:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse, JSONResponse
        from pydantic import BaseModel
    except ImportError:
        print("ERROR: fastapi not installed. Run: pip install fastapi uvicorn", file=sys.stderr)
        sys.exit(1)

    app = FastAPI(
        title="OCI Robot Cloud Contract Generator",
        description="Generate design partner contracts and SLA documents",
        version="1.0.0",
    )

    class GenerateRequest(BaseModel):
        partner_name: str
        tier: str
        start_date: Optional[str] = None
        monthly_gpu_hours: Optional[int] = None
        price_per_gpu_hour: float = 4.20
        support_tier: Optional[str] = None
        contract_type: Optional[str] = None

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTML_FORM

    @app.post("/generate")
    async def generate(req: GenerateRequest):
        try:
            cr = ContractRequest(
                partner_name=req.partner_name,
                tier=req.tier,
                start_date=req.start_date or "",
                monthly_gpu_hours=req.monthly_gpu_hours,
                price_per_gpu_hour=req.price_per_gpu_hour,
                support_tier=req.support_tier,
                contract_type=req.contract_type,
            )
        except ValueError as e:
            return JSONResponse(status_code=422, content={"detail": str(e)})

        markdown, meta = generate_contract(cr)
        return {"markdown": markdown, "metadata": asdict(meta)}

    @app.get("/samples")
    async def samples():
        """Return metadata for all 3 seeded sample contracts (no file I/O)."""
        results = []
        for req in SAMPLE_CONTRACTS:
            _, meta = generate_contract(req)
            results.append(asdict(meta))
        return results

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "contract-generator", "port": 8055}

    return app


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="OCI Robot Cloud — Design Partner Contract Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--partner", "-p", help="Partner/company name")
    parser.add_argument(
        "--tier", "-t",
        choices=["starter", "growth", "enterprise"],
        default="growth",
        help="Contract tier (default: growth)",
    )
    parser.add_argument("--start-date", default="", help="Start date YYYY-MM-DD (default: today)")
    parser.add_argument("--monthly-gpu-hours", type=int, default=None, help="Override monthly GPU hours")
    parser.add_argument("--price-per-gpu-hour", type=float, default=4.20, help="GPU price (default: $4.20)")
    parser.add_argument("--support-tier", choices=["email", "slack", "dedicated_csm"], default=None)
    parser.add_argument("--output", "-o", help="Output path for markdown (default: stdout)")
    parser.add_argument("--json-output", help="Output path for JSON metadata")
    parser.add_argument("--samples", action="store_true", help="Generate all 3 sample contracts to /tmp/")
    parser.add_argument("--serve", action="store_true", help="Start FastAPI server on port 8055")
    parser.add_argument("--port", type=int, default=8055, help="Server port (default: 8055)")

    args = parser.parse_args()

    if args.serve:
        try:
            import uvicorn
        except ImportError:
            print("ERROR: uvicorn not installed. Run: pip install fastapi uvicorn", file=sys.stderr)
            sys.exit(1)
        print(f"Starting OCI Robot Cloud Contract Generator on http://localhost:{args.port}")
        app = create_app()
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=args.port)
        return

    if args.samples:
        results = generate_sample_contracts("/tmp")
        print(f"\nGenerated {len(results)} sample contracts:")
        for r in results:
            print(f"  {r['partner']:30s}  total value: ${r['meta']['total_contract_value']:>10,.0f}  →  {r['md']}")
        return

    if not args.partner:
        parser.error("--partner is required (or use --serve / --samples)")

    req = ContractRequest(
        partner_name=args.partner,
        tier=args.tier,
        start_date=args.start_date,
        monthly_gpu_hours=args.monthly_gpu_hours,
        price_per_gpu_hour=args.price_per_gpu_hour,
        support_tier=args.support_tier,
    )
    markdown, meta = generate_contract(req)

    if args.output:
        with open(args.output, "w") as f:
            f.write(markdown)
        print(f"Contract written to: {args.output}")
    else:
        print(markdown)

    if args.json_output:
        with open(args.json_output, "w") as f:
            json.dump(asdict(meta), f, indent=2)
        print(f"Metadata written to: {args.json_output}")
    else:
        print("\n--- Contract Metadata ---", file=sys.stderr)
        print(json.dumps(asdict(meta), indent=2), file=sys.stderr)


if __name__ == "__main__":
    main()
