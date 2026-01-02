#!/bin/bash
# Basic usage example for roots

# Initialize
roots init

# Remember things with different confidence levels
roots remember "MACD crossovers are most reliable in trending markets. In ranging markets, they generate false signals." \
    --tags indicators,momentum,trend --confidence 0.8

roots remember "Volume spikes on breakouts confirm the move. Look for 2x average volume minimum." \
    --tags volume,breakouts --confidence 0.75

roots remember "Overfitting in backtests: More parameters != better strategy. Simple strategies that work across markets are more robust." \
    --tags backtesting,overfitting --confidence 0.95

# Search for relevant knowledge
echo "Searching for 'momentum indicators':"
roots recall "momentum indicators"

# List by tag
echo -e "\nMemories tagged 'indicators':"
roots recall --tag indicators

# Show stats
echo -e "\nStatistics:"
roots stats

# Sync to markdown for browsing
roots sync
echo -e "\nSynced to .roots/memories/"
