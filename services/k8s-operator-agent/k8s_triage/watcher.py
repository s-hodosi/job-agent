"""
K8sWatcher — monitors a Kubernetes namespace for unhealthy pods and
collects diagnostic context (logs, events, status) for each one.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List

from kubernetes import client
from kubernetes.client.rest import ApiException

from k8s_triage.models import PodDiagnostic

logger = logging.getLogger(__name__)

# Reasons that indicate a pod is in trouble
_FAILURE_REASONS = {"CrashLoopBackOff", "Error", "OOMKilled", "RunContainerError"}


class K8sWatcher:
    """Watch a single namespace and triage failing pods.

    Parameters
    ----------
    v1 : client.CoreV1Api
        An already-initialised Kubernetes CoreV1 API client.
    namespace : str
        The namespace to monitor.
    log_tail_lines : int
        Number of most-recent log lines to retrieve per container.
    """

    def __init__(
        self,
        v1: client.CoreV1Api,
        namespace: str = "default",
        log_tail_lines: int = 50,
    ) -> None:
        self._v1 = v1
        self._namespace = namespace
        self._log_tail_lines = log_tail_lines

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------
    def detect_failing_pods(self) -> List[dict]:
        """Return a list of ``{"pod_name": ..., "error_type": ...}`` dicts
        for every pod whose containers are in a recognised failure state.
        """
        failing: list[dict] = []

        try:
            pods = self._v1.list_namespaced_pod(namespace=self._namespace)
        except ApiException as exc:
            logger.error("Failed to list pods in '%s': %s", self._namespace, exc)
            return failing

        for pod in pods.items:
            pod_name = pod.metadata.name

            # 1) Check pod-level phase
            if pod.status.phase == "Failed":
                failing.append({"pod_name": pod_name, "error_type": "PodFailed"})
                continue

            # 2) Inspect every container status
            all_statuses = (pod.status.container_statuses or []) + (
                pod.status.init_container_statuses or []
            )
            for cs in all_statuses:
                reason = self._extract_failure_reason(cs)
                if reason:
                    failing.append({"pod_name": pod_name, "error_type": reason})
                    break  # one match per pod is enough

        if failing:
            logger.info(
                "Detected %d failing pod(s) in '%s': %s",
                len(failing),
                self._namespace,
                ", ".join(f["pod_name"] for f in failing),
            )
        else:
            logger.info("No failing pods detected in '%s'.", self._namespace)

        return failing

    # ------------------------------------------------------------------
    # Context collection
    # ------------------------------------------------------------------
    def get_pod_logs(self, pod_name: str, container: str | None = None) -> str:
        """Retrieve the last *log_tail_lines* lines of logs for *pod_name*.

        If *container* is ``None`` the API uses the single/default container.
        """
        try:
            logs: str = self._v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=self._namespace,
                container=container or "",
                tail_lines=self._log_tail_lines,
                previous=True,  # get logs from the previous (crashed) instance
            )
            return logs
        except ApiException as exc:
            msg = f"Could not retrieve logs for {pod_name}: {exc.reason}"
            logger.warning(msg)
            # Fallback: try current container logs (pod may not have previous)
            try:
                logs = self._v1.read_namespaced_pod_log(
                    name=pod_name,
                    namespace=self._namespace,
                    container=container or "",
                    tail_lines=self._log_tail_lines,
                )
                return logs
            except ApiException:
                return msg

    def get_pod_events(self, pod_name: str) -> str:
        """Return formatted Kubernetes events related to *pod_name*."""
        try:
            events = self._v1.list_namespaced_event(
                namespace=self._namespace,
                field_selector=f"involvedObject.name={pod_name}",
            )
            if not events.items:
                return "No events found."

            lines: list[str] = []
            for ev in events.items:
                ts = ev.last_timestamp or ev.first_timestamp or "N/A"
                lines.append(
                    f"[{ts}] {ev.type}: {ev.reason} — {ev.message}"
                )
            return "\n".join(lines)

        except ApiException as exc:
            msg = f"Could not retrieve events for {pod_name}: {exc.reason}"
            logger.warning(msg)
            return msg

    def get_pod_status_detail(self, pod_name: str) -> str:
        """Return a ``kubectl describe``-style status summary for *pod_name*."""
        try:
            pod = self._v1.read_namespaced_pod_status(
                name=pod_name,
                namespace=self._namespace,
            )
        except ApiException as exc:
            msg = f"Could not read status for {pod_name}: {exc.reason}"
            logger.warning(msg)
            return msg

        lines: list[str] = []

        # Pod-level info
        lines.append(f"Pod:       {pod.metadata.name}")
        lines.append(f"Namespace: {pod.metadata.namespace}")
        lines.append(f"Node:      {pod.spec.node_name or 'N/A'}")
        lines.append(f"Phase:     {pod.status.phase}")
        lines.append("")

        # Conditions
        lines.append("Conditions:")
        for cond in pod.status.conditions or []:
            lines.append(
                f"  {cond.type}: {cond.status}"
                + (f" (reason={cond.reason})" if cond.reason else "")
            )
        lines.append("")

        # Container statuses
        lines.append("Container Statuses:")
        for cs in pod.status.container_statuses or []:
            lines.append(f"  {cs.name}:")
            lines.append(f"    Ready:          {cs.ready}")
            lines.append(f"    Restart Count:  {cs.restart_count}")
            state = cs.state
            if state.waiting:
                lines.append(f"    State:          Waiting ({state.waiting.reason})")
                if state.waiting.message:
                    lines.append(f"    Message:        {state.waiting.message}")
            elif state.terminated:
                lines.append(
                    f"    State:          Terminated ({state.terminated.reason})"
                )
                lines.append(f"    Exit Code:      {state.terminated.exit_code}")
            elif state.running:
                lines.append(f"    State:          Running (since {state.running.started_at})")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Orchestrator
    # ------------------------------------------------------------------
    def collect_diagnostics(self) -> List[PodDiagnostic]:
        """Run a full triage scan and return a list of :class:`PodDiagnostic`."""
        failing = self.detect_failing_pods()
        diagnostics: list[PodDiagnostic] = []

        for entry in failing:
            pod_name = entry["pod_name"]
            error_type = entry["error_type"]

            logger.info("Collecting diagnostics for pod '%s' …", pod_name)

            logs = self.get_pod_logs(pod_name)
            events = self.get_pod_events(pod_name)
            status_detail = self.get_pod_status_detail(pod_name)

            diag = PodDiagnostic(
                pod_name=pod_name,
                namespace=self._namespace,
                error_type=error_type,
                logs=logs,
                events=events,
                status_detail=status_detail,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            diagnostics.append(diag)

        return diagnostics

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_failure_reason(container_status) -> str | None:
        """Return a failure reason string if *container_status* reflects trouble."""
        state = container_status.state
        if state is None:
            return None

        # Waiting state (e.g. CrashLoopBackOff)
        if state.waiting and state.waiting.reason in _FAILURE_REASONS:
            return state.waiting.reason

        # Terminated state (e.g. Error, OOMKilled)
        if state.terminated and state.terminated.reason in _FAILURE_REASONS:
            return state.terminated.reason

        return None
