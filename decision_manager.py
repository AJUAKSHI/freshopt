def select_strategy(strategies):
    """
    Select the cheapest strategy that satisfies
    the freshness requirement.

    Parameters:
        strategies: dictionary containing strategy information

    Returns:
        selected_strategy: name of the selected strategy
        reason: explanation for the selection
    """
    valid_strategies= {}

    #Keep only strategies that keep the freshness
    for strategy, details in strategies.items():
        if details["valid"]:
            valid_strategies[strategy] = details["cost"]

    #chek if any valid strategy exists
    if not valid_strategies:
        return None, "No strategy satisfies the freshness requirement"
    
    #select the strategy with the lowest cost
    selected_strategy = min(
        valid_strategies,
        key=valid_strategies.get
    )

    reason =(
        "Selected the cheapest strategy "
        "among the strategies that satisfy freshness."
    )

    return selected_strategy, reason

if __name__ == "__main__":

    strategies = {
        "CACHE": {
            "valid": False,
            "cost": 0.1
        },

        "INCREMENTAL": {
            "valid": True,
            "cost": 5.0
        },

        "FULL": {
            "valid": True,
            "cost": 3.0
        }
    }

    selected_strategy, reason = select_strategy(strategies)

    print("Selected Strategy:", selected_strategy)
    print("Reason:", reason)