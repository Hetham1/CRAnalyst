"""Static reference metrics for major L1/L2 networks."""

from __future__ import annotations

REFERENCE_METRICS = {
    "bitcoin": {
        "transaction_speed_tps": 7,
        "finality": "10 min",
        "developer_activity_score": 310,
        "consensus": "Proof of Work",
        "avg_fee_usd": 4.2,
        "category": "store-of-value",
        "narrative": "Settlement layer for hard-money flows.",
    },
    "ethereum": {
        "transaction_speed_tps": 30,
        "finality": "5 min",
        "developer_activity_score": 480,
        "consensus": "Proof of Stake",
        "avg_fee_usd": 1.2,
        "category": "smart-contracts",
        "narrative": "Largest programmable money ecosystem.",
    },
    "solana": {
        "transaction_speed_tps": 4000,
        "finality": "400 ms",
        "developer_activity_score": 260,
        "consensus": "Proof of History",
        "avg_fee_usd": 0.00025,
        "category": "high-throughput",
        "narrative": "Blazing-fast execution for consumer apps.",
    },
    "cardano": {
        "transaction_speed_tps": 250,
        "finality": "10 min",
        "developer_activity_score": 140,
        "consensus": "Proof of Stake",
        "avg_fee_usd": 0.2,
        "category": "smart-contracts",
        "narrative": "Research driven L1 with peer-reviewed roadmap.",
    },
    "polygon-pos": {
        "transaction_speed_tps": 65,
        "finality": "2 min",
        "developer_activity_score": 220,
        "consensus": "Proof of Stake",
        "avg_fee_usd": 0.01,
        "category": "layer2",
        "narrative": "Ethereum scaling with growing DeFi + gaming apps.",
    },
    "avalanche": {
        "transaction_speed_tps": 4500,
        "finality": "2 sec",
        "developer_activity_score": 210,
        "consensus": "Snowman",
        "avg_fee_usd": 0.03,
        "category": "smart-contracts",
        "narrative": "Subnet architecture for app-specific chains.",
    },
    "toncoin": {
        "transaction_speed_tps": 1000,
        "finality": "6 sec",
        "developer_activity_score": 160,
        "consensus": "Proof of Stake",
        "avg_fee_usd": 0.005,
        "category": "social",
        "narrative": "Telegram-native chain with consumer distribution.",
    },
}


def get_reference(asset: str) -> dict:
    return REFERENCE_METRICS.get(asset.lower())
