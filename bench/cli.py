"""
Command-line interface for the Solana Validator Block Ordering Benchmark.
"""

import sys
import argparse
from .solana_rpc import SolanaRpcClient
from .validator_catalog import ValidatorCatalog
from .experiment import ExperimentRunner

def main():
    parser = argparse.ArgumentParser(
        description="Solana Validator Block Ordering Micro-Benchmark (Superteam Ukraine Bounty)"
    )
    parser.add_argument(
        "--rpc-url",
        default="https://solana-rpc.publicnode.com",
        help="Solana Mainnet JSON-RPC endpoint (Default: https://solana-rpc.publicnode.com)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Execute in safe dry-run mode without broadcasting transactions (Default: True)"
    )
    parser.add_argument(
        "--live",
        dest="dry_run",
        action="store_false",
        help="Execute real transactions against leader schedule (Requires explicit flag)"
    )
    parser.add_argument(
        "--spend-cap",
        type=float,
        default=0.05,
        help="Strict upper spend limit in SOL (Default: 0.05 SOL)"
    )
    parser.add_argument(
        "--validators-count",
        type=int,
        default=6,
        help="Number of target validators to profile (Min: 6)"
    )
    parser.add_argument(
        "--blocks-per-validator",
        type=int,
        default=3,
        help="Number of confirmed blocks to inspect per validator (Default: 3)"
    )
    parser.add_argument(
        "--output-dir",
        default="data",
        help="Directory to save raw measurements and summary JSON"
    )

    args = parser.parse_args()

    print("\n[+] Initializing Solana RPC connection...")
    rpc = SolanaRpcClient(endpoint=args.rpc_url)

    print("[+] Discovering active mainnet validators...")
    catalog = ValidatorCatalog(rpc=rpc)
    catalog.refresh()

    print(f"[+] Selecting target cohort of {args.validators_count} validators across >= 3 client versions...")
    cohort = catalog.select_target_cohort(min_versions=3, target_count=args.validators_count)

    print("\nTarget Cohort Selection:")
    for idx, v in enumerate(cohort, 1):
        print(f"  {idx}. {v.pubkey} | Version: {v.version:<14} | Client: {v.client_name:<30} | Stake: {v.activated_stake_sol:,.0f} SOL")

    runner = ExperimentRunner(
        rpc=rpc,
        catalog=catalog,
        spend_cap_sol=args.spend_cap,
        dry_run=args.dry_run,
        output_dir=args.output_dir
    )

    runner.run_cohort_benchmark(
        target_validators=cohort,
        blocks_per_validator=args.blocks_per_validator
    )
    print("\n[✔] Benchmark finished successfully.\n")

if __name__ == "__main__":
    main()
