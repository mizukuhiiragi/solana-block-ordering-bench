"""
Validator discovery, classification, and leader window resolver.
"""

from typing import Dict, List, Any, Optional
from .models import ValidatorProfile
from .solana_rpc import SolanaRpcClient

# Reference mapping for prominent validator clients & signatures
KNOWN_CLIENT_MAPPINGS = {
    "4.3.2": "Agave / Jito-Solana v4.3.2 (Mainnet Production)",
    "4.3.0": "Agave v4.3.0",
    "2.3.8": "Firedancer / Frankendancer v2.3.8 Canary",
    "26.10.4": "Agave CalVer v26.10.4",
    "4.2.2": "Agave v4.2.2",
    "4.5.0-alpha.2": "Agave Next-Gen Alpha Canary"
}

class ValidatorCatalog:
    def __init__(self, rpc: SolanaRpcClient):
        self.rpc = rpc
        self.validators: Dict[str, ValidatorProfile] = {}
        self.leader_schedule_cache: Dict[str, List[int]] = {}

    def refresh(self) -> List[ValidatorProfile]:
        nodes = self.rpc.get_cluster_nodes()
        node_map = {n["pubkey"]: n for n in nodes if "pubkey" in n}

        vote_data = self.rpc.get_vote_accounts()
        current_votes = vote_data.get("current", [])

        profiles: List[ValidatorProfile] = []
        for vote in current_votes:
            node_pubkey = vote.get("nodePubkey")
            node_info = node_map.get(node_pubkey, {})
            version = node_info.get("version") or vote.get("version") or "unknown"

            # Determine client name
            client_name = KNOWN_CLIENT_MAPPINGS.get(version, f"Custom/Fork ({version})")
            if "Fd" in node_pubkey[:4] or "fire" in node_pubkey.lower():
                client_name = "Firedancer Early Canary"
            elif "jito" in node_pubkey.lower():
                client_name = f"Jito-Solana ({version})"

            stake_sol = float(vote.get("activatedStake", 0)) / 10**9
            profile = ValidatorProfile(
                pubkey=node_pubkey,
                vote_pubkey=vote.get("votePubkey", ""),
                client_name=client_name,
                version=str(version),
                activated_stake_sol=stake_sol,
                commission=int(vote.get("commission", 0)),
                tpu_ip=node_info.get("tpu")
            )
            profiles.append(profile)
            self.validators[node_pubkey] = profile

        profiles.sort(key=lambda p: p.activated_stake_sol, reverse=True)
        return profiles

    def select_target_cohort(self, min_versions: int = 3, target_count: int = 6) -> List[ValidatorProfile]:
        """
        Selects at least 6 validators spanning at least 3 distinct client software versions,
        satisfying the Superteam Ukraine bounty specifications.
        """
        if not self.validators:
            self.refresh()

        grouped: Dict[str, List[ValidatorProfile]] = {}
        for p in self.validators.values():
            if p.activated_stake_sol < 100_000:
                continue
            grouped.setdefault(p.version, []).append(p)

        selected: List[ValidatorProfile] = []
        # Sort versions by diversity
        sorted_versions = sorted(grouped.keys(), key=lambda v: len(grouped[v]), reverse=True)

        # Pick top validators from the first distinct versions
        for v in sorted_versions[:max(min_versions, 3)]:
            selected.extend(grouped[v][:2])  # pick 2 from each version

        # Ensure we have at least target_count
        for v in sorted_versions:
            for p in grouped[v]:
                if p not in selected:
                    selected.append(p)
                if len(selected) >= target_count:
                    break
            if len(selected) >= target_count:
                break

        return selected[:target_count]
