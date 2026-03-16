"""
LangGraph-compatible triage node.

This module exposes a single function, :func:`triage_node`, whose signature
``(state: dict) -> dict`` is compatible with ``StateGraph.add_node()``.

Usage inside a LangGraph graph::

    from langgraph.graph import StateGraph
    from k8s_triage.triage import triage_node

    graph = StateGraph(dict)
    graph.add_node("triage", triage_node)
"""

from __future__ import annotations

import logging

from k8s_triage.config import get_k8s_clients
from k8s_triage.models import TriageReport
from k8s_triage.watcher import K8sWatcher

logger = logging.getLogger(__name__)


def triage_node(state: dict) -> dict:
    """Scan the configured namespace and return triage results.

    Parameters
    ----------
    state : dict
        The current LangGraph state dict.  This node does not require any
        particular keys to be present — it will add its own.

    Returns
    -------
    dict
        An updated copy of *state* with the following keys added/replaced:

        * ``triage_report`` — a serialised :class:`TriageReport`.
        * ``failing_pods``  — the compact ``[{pod_name, error_type, context_data}]``
          list for easy downstream consumption.
    """
    logger.info("Triage node invoked — scanning for failing pods …")

    clients = get_k8s_clients()
    watcher = K8sWatcher(
        v1=clients.v1,
        namespace=clients.namespace,
        log_tail_lines=clients.log_tail_lines,
    )

    diagnostics = watcher.collect_diagnostics()
    report = TriageReport(
        failing_pods=diagnostics,
        scanned_namespace=clients.namespace,
    )

    logger.info(
        "Triage complete — %d failing pod(s) found.", len(diagnostics)
    )

    return {
        **state,
        "triage_report": report.model_dump(),
        "failing_pods": report.to_context_dicts(),
    }
