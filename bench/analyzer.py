"""
Statistical Analyzer for Transaction Ordering within Solana Blocks.
Evaluates priority fee ordering rules, multi-threaded banking stage interleaving,
and account lock serialization.
"""

import math
from typing import List, Dict, Any, Tuple
from .models import MeasuredTxRecord, BlockOrderingStats

class BlockOrderAnalyzer:
    @staticmethod
    def parse_block_transactions(block: Dict[str, Any], slot: int, leader_pubkey: str, client_version: str) -> List[MeasuredTxRecord]:
        txs = block.get("transactions", [])
        records: List[MeasuredTxRecord] = []

        for idx, item in enumerate(txs):
            tx_obj = item.get("transaction", {})
            meta = item.get("meta", {})
            if not tx_obj or not meta:
                continue

            # Extract signature
            signatures = tx_obj.get("signatures", [])
            sig = signatures[0] if signatures else f"slot-{slot}-idx-{idx}"

            # Message parsing
            msg = tx_obj.get("message", {})
            account_keys = msg.get("accountKeys", [])

            # Compute units & fees
            cu_consumed = meta.get("computeUnitsConsumed", 0)
            fee = meta.get("fee", 5000)

            # In modern Solana (v2.x / v4.x), base fee is 5000 lamports per signature
            num_sigs = len(signatures) or 1
            base_fee = 5000 * num_sigs
            priority_fee = max(0, fee - base_fee)

            # Extract ComputeBudget instructions to determine requested unit price
            cu_price_microlamports = 0
            cu_limit = 200_000 # default
            instructions = msg.get("instructions", [])
            for ix in instructions:
                # Instruction parsing for ComputeBudgetProgram (ComputeBudget111111111111111111111111111111)
                # If parsed json format or raw data:
                if isinstance(ix, dict):
                    prog_id = ix.get("programId")
                    if prog_id == "ComputeBudget111111111111111111111111111111":
                        parsed = ix.get("parsed")
                        if isinstance(parsed, dict):
                            ptype = parsed.get("type")
                            info = parsed.get("info", {})
                            if ptype == "setComputeUnitPrice":
                                cu_price_microlamports = int(info.get("microLamports", 0))
                            elif ptype == "setComputeUnitLimit":
                                cu_limit = int(info.get("units", 200_000))

            if cu_price_microlamports == 0 and priority_fee > 0 and cu_consumed > 0:
                # Approximate effective microlamports per CU: (priority_fee * 10^6) / cu_consumed
                cu_price_microlamports = int((priority_fee * 1_000_000) / cu_consumed)

            # Accounts
            header = msg.get("header", {})
            num_req_signed = header.get("numRequiredSignatures", 1)
            num_ro_signed = header.get("numReadonlySignedAccounts", 0)
            num_ro_unsigned = header.get("numReadonlyUnsignedAccounts", 0)

            writable_accounts: List[str] = []
            readable_accounts: List[str] = []

            for i, acc in enumerate(account_keys):
                acc_str = acc if isinstance(acc, str) else acc.get("pubkey", "")
                is_signer = i < num_req_signed
                is_readonly = (i >= num_req_signed - num_ro_signed and is_signer) or (i >= len(account_keys) - num_ro_unsigned)
                if not is_readonly:
                    writable_accounts.append(acc_str)
                else:
                    readable_accounts.append(acc_str)

            record = MeasuredTxRecord(
                signature=sig,
                slot=slot,
                block_index=idx,
                validator_pubkey=leader_pubkey,
                client_version=client_version,
                compute_unit_limit=cu_limit,
                compute_unit_price_microlamports=cu_price_microlamports,
                base_fee_lamports=base_fee,
                priority_fee_lamports=priority_fee,
                total_fee_lamports=fee,
                accounts_written=writable_accounts,
                accounts_read=readable_accounts,
                success=(meta.get("err") is None)
            )
            records.append(record)

        return records

    @staticmethod
    def compute_spearman_rank_correlation(x: List[float], y: List[float]) -> float:
        n = len(x)
        if n < 2:
            return 0.0

        # If all values in x or y are identical (variance is zero), correlation is 0.0
        if len(set(x)) == 1 or len(set(y)) == 1:
            return 0.0

        def rank_with_ties(arr: List[float]) -> List[float]:
            # Sort by value
            indexed = sorted(enumerate(arr), key=lambda item: item[1])
            ranks = [0.0] * n
            
            i = 0
            while i < n:
                j = i
                # Find group of ties
                while j < n - 1 and indexed[j + 1][1] == indexed[j][1]:
                    j += 1
                # Average rank for ties (1-based)
                avg_rank = (i + 1 + j + 1) / 2.0
                for k in range(i, j + 1):
                    orig_idx = indexed[k][0]
                    ranks[orig_idx] = avg_rank
                i = j + 1
            return ranks

        rx = rank_with_ties(x)
        ry = rank_with_ties(y)

        mean_rx = sum(rx) / n
        mean_ry = sum(ry) / n

        num = sum((rx[i] - mean_rx) * (ry[i] - mean_ry) for i in range(n))
        den_x = math.sqrt(sum((rx[i] - mean_rx) ** 2 for i in range(n)))
        den_y = math.sqrt(sum((ry[i] - mean_ry) ** 2 for i in range(n)))

        if den_x == 0 or den_y == 0:
            return 0.0
        return num / (den_x * den_y)


    @staticmethod
    def analyze_block(records: List[MeasuredTxRecord], slot: int, blockhash: str, leader: str, client_ver: str) -> BlockOrderingStats:
        n = len(records)
        if n == 0:
            return BlockOrderingStats(
                slot=slot,
                blockhash=blockhash,
                leader_pubkey=leader,
                client_version=client_ver,
                total_transactions=0,
                measured_sample_size=0,
                fee_spearman_corr=0.0,
                fee_inversion_rate=0.0,
                disjoint_write_lock_ratio=1.0,
                estimated_banking_threads=4,
                notes=["Empty block"]
            )

        # Expected rule: Higher fee-per-CU should land at smaller block indices (earlier).
        # We calculate rank correlation between fee_microlamports and reverse index (-index).
        fees = [float(r.compute_unit_price_microlamports) for r in records]
        # Earlier index = higher execution priority rank
        reverse_indices = [-float(r.block_index) for r in records]

        corr = BlockOrderAnalyzer.compute_spearman_rank_correlation(fees, reverse_indices)

        # Calculate fee inversion rate among transactions that had non-zero fees
        non_zero_fee_txs = [r for r in records if r.compute_unit_price_microlamports > 0]
        inversions = 0
        comparisons = 0

        # Sample sliding window to observe local thread schedulers
        for i in range(len(non_zero_fee_txs) - 1):
            t1 = non_zero_fee_txs[i]
            t2 = non_zero_fee_txs[i + 1]
            # t1 arrived earlier in block than t2
            comparisons += 1
            # If t2 paid significantly more (>= 1.5x) than t1, it's an inversion
            if t2.compute_unit_price_microlamports > t1.compute_unit_price_microlamports * 1.5:
                inversions += 1

        inversion_rate = (inversions / comparisons) if comparisons > 0 else 0.0

        # Write-lock conflict analysis: check how many txs share writable accounts
        active_locks = set()
        disjoint_count = 0
        for r in records:
            w_set = set(r.accounts_written)
            if not (w_set & active_locks):
                disjoint_count += 1
            active_locks.update(w_set)

        disjoint_ratio = disjoint_count / n if n > 0 else 1.0

        notes = []
        if corr > 0.6:
            notes.append("Strong fee-priority ordering detected (centralized scheduler active)")
        elif corr > 0.2:
            notes.append("Moderate fee ordering with multi-threaded banking stage interleaving")
        else:
            notes.append("Weak/Flat fee correlation (mempool saturation, FIFO burst or high conflict rate)")

        return BlockOrderingStats(
            slot=slot,
            blockhash=blockhash,
            leader_pubkey=leader,
            client_version=client_ver,
            total_transactions=n,
            measured_sample_size=len(records),
            fee_spearman_corr=round(corr, 4),
            fee_inversion_rate=round(inversion_rate, 4),
            disjoint_write_lock_ratio=round(disjoint_ratio, 4),
            estimated_banking_threads=6,
            notes=notes
        )
