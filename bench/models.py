"""
Data models for Solana validator block ordering benchmark.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

@dataclass
class ValidatorProfile:
    pubkey: str
    vote_pubkey: str
    client_name: str  # Agave, Jito-Solana, Firedancer, etc.
    version: str
    activated_stake_sol: float
    commission: int
    tpu_ip: Optional[str] = None

@dataclass
class MeasuredTxRecord:
    signature: str
    slot: int
    block_index: int
    validator_pubkey: str
    client_version: str
    compute_unit_limit: int
    compute_unit_price_microlamports: int
    base_fee_lamports: int
    priority_fee_lamports: int
    total_fee_lamports: int
    accounts_written: List[str] = field(default_factory=list)
    accounts_read: List[str] = field(default_factory=list)
    success: bool = True
    sent_timestamp_ms: Optional[int] = None
    landed_timestamp_ms: Optional[int] = None
    is_synthetic_probe: bool = False

@dataclass
class BlockOrderingStats:
    slot: int
    blockhash: str
    leader_pubkey: str
    client_version: str
    total_transactions: int
    measured_sample_size: int
    # Statistical measures for priority fee ordering
    fee_spearman_corr: float  # Rank correlation between fee-per-CU and block index
    fee_inversion_rate: float # Percentage of adjacent pairs violating fee order
    disjoint_write_lock_ratio: float # Proportion of txs with zero account conflicts
    estimated_banking_threads: int
    notes: List[str] = field(default_factory=list)
