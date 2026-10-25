def validate_result(final_data_age, delta, selected_strategy):
    """
    Validate whether the final result satisfies
    the user's freshness requirement.

    Parameters:
        final_data_age: age of the final result in minutes
        delta: maximum allowed data age in minutes
        selected_strategy: strategy used to produce the result

    Returns:
        Dictionary containing validation information
    """
    is_valid = final_data_age <=delta

    return{
        "valid": is_valid,
        "final_age": final_data_age,
        "delta": delta,
        "selected_strategy": selected_strategy
    }

if __name__ == "__main__":

    result = validate_result(
        final_data_age=8,
        delta=5,
        selected_strategy="CASHE"
    )

    print("Result Validation")
    print("-----------------")
    print("Valid:", result["valid"])
    print("Final Data Age:", result["final_age"], "minutes")
    print("Freshness Limit:", result["delta"], "minutes")
    print("Selected Strategy:", result["selected_strategy"])