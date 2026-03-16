#!/usr/bin/env python3
"""
Self-Healing K8s Operator Agent — Triage Runner
================================================

Standalone entry point that executes the triage node and pretty-prints the
results.  Useful for local dev / manual testing with an active cluster.

Usage::

    # Using default kubeconfig
    python main.py

    # Specifying namespace
    K8S_NAMESPACE=production python main.py

    # In-cluster mode (when running inside a K8s pod)
    K8S_CONFIG_MODE=incluster python main.py
"""

from __future__ import annotations

import json
import logging
import sys

from k8s_triage.triage import triage_node


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )

    state = triage_node({})

    failing = state.get("failing_pods", [])
    if not failing:
        print("\n✅  No failing pods detected.\n")
    else:
        print(f"\n⚠️  Found {len(failing)} failing pod(s):\n")
        print(json.dumps(failing, indent=2, default=str))

    # Also dump the full report for debugging
    print("\n--- Full Triage Report ---\n")
    print(json.dumps(state.get("triage_report", {}), indent=2, default=str))

    sys.exit(1 if failing else 0)


if __name__ == "__main__":
    main()
