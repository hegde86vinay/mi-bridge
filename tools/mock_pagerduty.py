"""Mock PagerDuty tool — returns fabricated on-call and ownership data."""

from __future__ import annotations

import asyncio


async def get_oncall_roster(services: list[str]) -> dict:
    """Return current on-call engineer for each service."""
    await asyncio.sleep(0)

    _roster = {
        "inventory-service": {
            "team_name": "Inventory Platform",
            "oncall_engineer": "James Wu",
            "slack_handle": "@james.wu",
            "email": "james.wu@company.com",
            "phone": "+1-415-555-0142",
            "escalation_1": "Sarah Chen (Eng Manager)",
            "escalation_1_slack": "@sarah.chen",
        },
        "order-service": {
            "team_name": "Order Management",
            "oncall_engineer": "Anika Patel",
            "slack_handle": "@anika.patel",
            "email": "anika.patel@company.com",
            "phone": "+1-415-555-0219",
            "escalation_1": "Raj Gupta (Eng Manager)",
            "escalation_1_slack": "@raj.gupta",
        },
        "payment-service": {
            "team_name": "Payments & Billing",
            "oncall_engineer": "Marcus Johnson",
            "slack_handle": "@marcus.johnson",
            "email": "marcus.johnson@company.com",
            "phone": "+1-415-555-0388",
            "escalation_1": "Elena Rodriguez (VP Payments)",
            "escalation_1_slack": "@elena.rodriguez",
        },
        "api-gateway": {
            "team_name": "Platform Engineering",
            "oncall_engineer": "Lena Fischer",
            "slack_handle": "@lena.fischer",
            "email": "lena.fischer@company.com",
            "phone": "+1-415-555-0471",
            "escalation_1": "David Kim (Principal SRE)",
            "escalation_1_slack": "@david.kim",
        },
    }

    return {svc: _roster[svc] for svc in services if svc in _roster}


async def get_service_ownership(services: list[str]) -> dict:
    """Return team ownership metadata and runbook URLs per service."""
    await asyncio.sleep(0)

    _ownership = {
        "inventory-service": {
            "owning_team": "Inventory Platform",
            "slack_channel": "#inventory-platform-incidents",
            "runbook_url": "https://wiki.company.com/runbooks/inventory-service",
            "escalation_path": ["James Wu (on-call)", "Sarah Chen (EM)", "CTO bridge"],
            "slo_target_pct": 99.9,
            "slo_current_pct": 57.9,
            "repo": "github.com/company/inventory-service",
            "deployment_method": "Kubernetes rolling update via ArgoCD",
        },
        "order-service": {
            "owning_team": "Order Management",
            "slack_channel": "#order-mgmt-incidents",
            "runbook_url": "https://wiki.company.com/runbooks/order-service",
            "escalation_path": ["Anika Patel (on-call)", "Raj Gupta (EM)", "CTO bridge"],
            "slo_target_pct": 99.9,
            "slo_current_pct": 61.3,
            "repo": "github.com/company/order-service",
            "deployment_method": "Kubernetes rolling update via ArgoCD",
        },
        "payment-service": {
            "owning_team": "Payments & Billing",
            "slack_channel": "#payments-incidents",
            "runbook_url": "https://wiki.company.com/runbooks/payment-service",
            "escalation_path": ["Marcus Johnson (on-call)", "Elena Rodriguez (VP)", "CFO notification required for P1"],
            "slo_target_pct": 99.99,
            "slo_current_pct": 88.7,
            "repo": "github.com/company/payment-service",
            "deployment_method": "Kubernetes rolling update via ArgoCD",
        },
        "api-gateway": {
            "owning_team": "Platform Engineering",
            "slack_channel": "#platform-incidents",
            "runbook_url": "https://wiki.company.com/runbooks/api-gateway",
            "escalation_path": ["Lena Fischer (on-call)", "David Kim (Principal SRE)", "CTO bridge"],
            "slo_target_pct": 99.95,
            "slo_current_pct": 60.1,
            "repo": "github.com/company/api-gateway",
            "deployment_method": "Kubernetes rolling update via ArgoCD",
        },
    }

    return {svc: _ownership[svc] for svc in services if svc in _ownership}
