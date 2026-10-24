"""
Solana JSON-RPC client with robust retries, rate-limiting, and block parsing.
"""

import json
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List

class SolanaRpcClient:
    def __init__(self, endpoint: str = "https://solana-rpc.publicnode.com", timeout: int = 15, max_retries: int = 4):
        self.endpoint = endpoint
        self.timeout = timeout
        self.max_retries = max_retries
        self._request_id = 0

    def call(self, method: str, params: Optional[List[Any]] = None) -> Any:
        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or []
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "SolanaBlockOrderingBench/1.0"
        }

        delay = 0.5
        for attempt in range(self.max_retries):
            try:
                req = urllib.request.Request(self.endpoint, data=data, headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    if "error" in res:
                        err = res["error"]
                        raise RuntimeError(f"RPC Error {err.get('code')}: {err.get('message')}")
                    return res.get("result")
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, RuntimeError) as e:
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(delay)
                delay *= 2

    def get_slot(self) -> int:
        return int(self.call("getSlot", [{"commitment": "confirmed"}]))

    def get_epoch_info(self) -> Dict[str, Any]:
        return self.call("getEpochInfo", [{"commitment": "confirmed"}])

    def get_cluster_nodes(self) -> List[Dict[str, Any]]:
        return self.call("getClusterNodes")

    def get_vote_accounts(self) -> Dict[str, Any]:
        return self.call("getVoteAccounts", [{"commitment": "confirmed"}])

    def get_leader_schedule(self, slot: Optional[int] = None) -> Dict[str, List[int]]:
        params = []
        if slot is not None:
            params.append(slot)
        return self.call("getLeaderSchedule", params)

    def get_block(self, slot: int, detail: str = "full") -> Optional[Dict[str, Any]]:
        config: Dict[str, Any] = {
            "encoding": "json",
            "transactionDetails": detail,
            "rewards": True,
            "maxSupportedTransactionVersion": 1
        }
        try:
            time.sleep(0.15)  # friendly pacing to respect public RPC
            return self.call("getBlock", [slot, config])
        except Exception:
            return None

