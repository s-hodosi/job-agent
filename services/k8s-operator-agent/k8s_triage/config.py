"""
Kubernetes client configuration — driven entirely by environment variables.

Env vars
--------
K8S_CONFIG_MODE   : "kubeconfig" (default) or "incluster"
KUBECONFIG_PATH   : path to kubeconfig file (only used when mode is kubeconfig)
K8S_NAMESPACE     : namespace to monitor (default: "default")
K8S_LOG_TAIL_LINES: number of log lines to retrieve per pod (default: 50)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from kubernetes import client, config as k8s_config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — sourced from environment
# ---------------------------------------------------------------------------
CONFIG_MODE: str = os.getenv("K8S_CONFIG_MODE", "kubeconfig")
KUBECONFIG_PATH: str | None = os.getenv("KUBECONFIG_PATH")
NAMESPACE: str = os.getenv("K8S_NAMESPACE", "default")
LOG_TAIL_LINES: int = int(os.getenv("K8S_LOG_TAIL_LINES", "50"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class K8sClients:
    """Convenience container returned by :func:`get_k8s_clients`."""

    v1: client.CoreV1Api
    namespace: str
    log_tail_lines: int


def _load_config() -> None:
    """Load the Kubernetes configuration based on *K8S_CONFIG_MODE*."""
    if CONFIG_MODE == "incluster":
        logger.info("Loading in-cluster Kubernetes configuration.")
        k8s_config.load_incluster_config()
    else:
        kube_path = KUBECONFIG_PATH  # None → default location (~/.kube/config)
        logger.info(
            "Loading kubeconfig from %s",
            kube_path or "default location",
        )
        k8s_config.load_kube_config(config_file=kube_path)


def get_k8s_clients() -> K8sClients:
    """Initialise the K8s API client and return a :class:`K8sClients` bundle.

    This function is safe to call multiple times; each call creates a fresh
    API client instance.
    """
    _load_config()
    v1 = client.CoreV1Api()
    logger.info(
        "K8s client ready — namespace=%s, tail_lines=%d",
        NAMESPACE,
        LOG_TAIL_LINES,
    )
    return K8sClients(v1=v1, namespace=NAMESPACE, log_tail_lines=LOG_TAIL_LINES)
