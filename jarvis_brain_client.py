"""
JarvisBrain Client SDK
Ultra-lightweight portable client for seamless integration with JARVIS, JarvisDefender, and JarvisGameDesigner.
Zero heavy dependencies (works with standard library urllib with optional httpx support).
"""

import json
import logging
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error
import urllib.parse

logger = logging.getLogger("JarvisBrainClient")


class JarvisBrainClient:
    """Portable client for interacting with JarvisBrain microservice (127.0.0.1:8765)."""

    def __init__(self, base_url: str = "http://127.0.0.1:8765", timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, endpoint: str, method: str = "GET", data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform HTTP request with resilient offline fallback handling."""
        url = f"{self.base_url}{endpoint}"
        headers = {"Content-Type": "application/json"}
        req_data = json.dumps(data).encode("utf-8") if data is not None else None

        req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.URLError as e:
            logger.warning(f"JarvisBrain connection failed: {e}")
            return {
                "success": False,
                "offline": True,
                "error": f"Brain unreachable at {self.base_url}: {e}",
                "answer": "JarvisBrain servisi şu an çevrimdışı.",
            }
        except Exception as e:
            logger.error(f"Unexpected error calling JarvisBrain: {e}")
            return {
                "success": False,
                "offline": True,
                "error": str(e),
                "answer": f"JarvisBrain iletişim hatası: {e}",
            }

    def ping(self) -> bool:
        """Check if JarvisBrain is active and running."""
        res = self._request("/health")
        return res.get("status") == "online"

    def query(
        self,
        text: str,
        bypass_cache: bool = False,
        force_web: bool = False,
        intent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Query JarvisBrain intelligence core.
        Executes Fast-Path (L1) -> Rules & Facts (L2) -> Subsystem Hub -> Live Web Grounding (L3).
        """
        payload = {
            "query": text,
            "bypass_cache": bypass_cache,
            "force_web": force_web,
            "intent": intent,
        }
        res = self._request("/api/v1/query", method="POST", data=payload)
        return res

    def remember(
        self,
        subject: str,
        content: str,
        category: str = "general",
        tags: str = "",
    ) -> Dict[str, Any]:
        """Save a new distilled knowledge fact into persistent memory."""
        payload = {
            "subject": subject,
            "content": content,
            "category": category,
            "tags": tags,
        }
        return self._request("/api/v1/remember", method="POST", data=payload)

    def learn_rule(
        self,
        condition_pattern: str,
        action_payload: str,
        action_type: str = "respond",
        priority: int = 10,
        category: str = "general",
    ) -> Dict[str, Any]:
        """
        Teach JarvisBrain an Action Rule ('Şu olduysa bunu yap').
        """
        payload = {
            "condition_pattern": condition_pattern,
            "action_type": action_type,
            "action_payload": action_payload,
            "priority": priority,
            "category": category,
        }
        return self._request("/api/v1/rules", method="POST", data=payload)

    def get_matching_rules(self, condition_text: str) -> List[Dict[str, Any]]:
        """Find which action rules match a specific scenario or condition."""
        payload = {"condition": condition_text}
        res = self._request("/api/v1/rules/match", method="POST", data=payload)
        return res.get("rules", [])

    def get_stats(self) -> Dict[str, Any]:
        """Get system memory, storage quota, and active rule stats."""
        return self._request("/api/v1/memory/stats")

    def set_quota(self, quota_gb: float) -> Dict[str, Any]:
        """Update dynamic memory quota (GB)."""
        payload = {"max_quota_gb": quota_gb}
        return self._request("/api/v1/memory/quota", method="POST", data=payload)

    def get_facts(self, category: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Fetch distilled knowledge facts from memory."""
        endpoint = f"/api/v1/facts?limit={limit}&offset={offset}"
        if category:
            endpoint += f"&category={urllib.parse.quote(category)}"
        res = self._request(endpoint, method="GET")
        return res.get("facts", [])

    def delete_fact(self, fact_id: str) -> bool:
        """Delete a knowledge fact from memory."""
        res = self._request(f"/api/v1/facts/{fact_id}", method="DELETE")
        return bool(res.get("success", False))

    def get_rules(self, category: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List active action rules."""
        endpoint = f"/api/v1/rules?limit={limit}&offset={offset}"
        if category:
            endpoint += f"&category={urllib.parse.quote(category)}"
        res = self._request(endpoint, method="GET")
        return res.get("rules", [])

    def delete_rule(self, rule_id: str) -> bool:
        """Delete an action rule."""
        res = self._request(f"/api/v1/rules/{rule_id}", method="DELETE")
        return bool(res.get("success", False))

    def get_hub_status(self) -> Dict[str, Any]:
        """Fetch status of all interconnected subsystems (Defender, GameDesigner, Core)."""
        return self._request("/api/v1/hub/status", method="GET")

    def prune_memory(self) -> Dict[str, Any]:
        """Trigger LRU cleanup of stale knowledge and vacuum DB."""
        return self._request("/api/v1/memory/prune", method="POST")


# Standalone usage example:
if __name__ == "__main__":
    client = JarvisBrainClient()
    print("Testing JarvisBrain connection...")
    if client.ping():
        print("JarvisBrain is ONLINE!")
        print("Query test:", client.query("Sistem durumu nasıl?"))
    else:
        print("JarvisBrain is offline. Start the service first with py main.py")
