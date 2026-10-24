"""
Unit tests for the Solana Validator Block Ordering Benchmark.
"""

import unittest
from bench.models import ValidatorProfile, MeasuredTxRecord
from bench.analyzer import BlockOrderAnalyzer
from bench.experiment import ExperimentRunner, SpendCapExceededError

class TestOrderingBench(unittest.TestCase):
    def test_spearman_perfect_correlation(self):
        # Monotonically increasing fees matching earlier block indices
        fees = [100.0, 50.0, 20.0, 10.0, 0.0]
        reverse_indices = [-0.0, -1.0, -2.0, -3.0, -4.0] # index 0 is first, index 4 is last
        corr = BlockOrderAnalyzer.compute_spearman_rank_correlation(fees, reverse_indices)
        self.assertAlmostEqual(corr, 1.0, places=4)

    def test_spearman_perfect_inversion(self):
        # Higher fee txs placed at the very end
        fees = [0.0, 10.0, 20.0, 50.0, 100.0]
        reverse_indices = [-0.0, -1.0, -2.0, -3.0, -4.0]
        corr = BlockOrderAnalyzer.compute_spearman_rank_correlation(fees, reverse_indices)
        self.assertAlmostEqual(corr, -1.0, places=4)

    def test_spearman_flat_zero(self):
        # All transactions pay the exact same base fee (zero priority fee)
        fees = [0.0, 0.0, 0.0, 0.0]
        reverse_indices = [-0.0, -1.0, -2.0, -3.0]
        corr = BlockOrderAnalyzer.compute_spearman_rank_correlation(fees, reverse_indices)
        self.assertEqual(corr, 0.0)

    def test_spend_cap_enforcement(self):
        # Ensure runner strictly forbids spending above spend_cap_sol
        runner = ExperimentRunner(rpc=None, catalog=None, spend_cap_sol=0.01, dry_run=True)
        # Attempting to spend 0.02 SOL (20_000_000 lamports) should throw
        with self.assertRaises(SpendCapExceededError):
            runner.check_spend_cap(20_000_000)

        # Spending within cap should pass
        runner.check_spend_cap(5_000_000) # 0.005 SOL
        runner.total_spent_lamports += 5_000_000

        # Further spend pushing over cap should throw
        with self.assertRaises(SpendCapExceededError):
            runner.check_spend_cap(6_000_000)

    def test_block_analysis_metrics(self):
        records = [
            MeasuredTxRecord(
                signature="sig1",
                slot=100,
                block_index=0,
                validator_pubkey="Val1",
                client_version="4.3.2",
                compute_unit_limit=200000,
                compute_unit_price_microlamports=100000,
                base_fee_lamports=5000,
                priority_fee_lamports=20000,
                total_fee_lamports=25000,
                accounts_written=["accA"],
                accounts_read=[]
            ),
            MeasuredTxRecord(
                signature="sig2",
                slot=100,
                block_index=1,
                validator_pubkey="Val1",
                client_version="4.3.2",
                compute_unit_limit=200000,
                compute_unit_price_microlamports=10000,
                base_fee_lamports=5000,
                priority_fee_lamports=2000,
                total_fee_lamports=7000,
                accounts_written=["accB"],
                accounts_read=[]
            )
        ]
        stats = BlockOrderAnalyzer.analyze_block(records, 100, "hash123", "Val1", "4.3.2")
        self.assertEqual(stats.total_transactions, 2)
        self.assertGreater(stats.fee_spearman_corr, 0.9)
        self.assertEqual(stats.fee_inversion_rate, 0.0)
        self.assertEqual(stats.disjoint_write_lock_ratio, 1.0)

if __name__ == "__main__":
    unittest.main()
