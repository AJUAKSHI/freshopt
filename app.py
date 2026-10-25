import streamlit as st
import pandas as pd

from main import run_optimizer

# -----------------------------
# Compact UI
# -----------------------------

st.markdown("""
<style>
    /* Reduce section heading size */
    h3 {
        font-size: 20px !important;
    }

    /* Reduce metric label size */
    [data-testid="stMetricLabel"] {
        font-size: 14px !important;
    }

    /* Reduce metric value size */
    [data-testid="stMetricValue"] {
        font-size: 22px !important;
    }

    /* Reduce normal text slightly */
    .stMarkdown, .stText {
        font-size: 14px;
    }
</style>
""", unsafe_allow_html=True)

#---------------------
st.title("Freshness Optimizer")

st.write(
    "Freshness-aware query optimization using "
    "cache, incremental refresh, and full recomputation."
)


# -----------------------------
# User Input
# -----------------------------

st.subheader("Query & Freshness")

sql_query = st.text_input(
    "SQL Query",
    "SELECT SUM(amount) FROM sales;"
)

delta = st.number_input(
    "Freshness Limit (minutes)",
    min_value=1,
    value=10
)

scenario = st.selectbox(
    "Change Scenario",
    ["small", "large"]
)


# -----------------------------
# Run Optimizer
# -----------------------------

if st.button("Run Optimizer"):

    result = run_optimizer(
        sql_query=sql_query,
        delta=delta,
        scenario=scenario
    )

    st.success("Optimizer executed successfully!")


    # -----------------------------
    # Query Analysis
    # -----------------------------

    st.subheader("Query Analysis")

    analysis = result["analysis"]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Operation", analysis["operation"])

    with col2:
        st.metric("Target Column", analysis["target_column"])

    with col3:
        st.metric("Table", analysis["table"])


    # -----------------------------
    # Cache Information
    # -----------------------------

    st.subheader("Cache Information")

    cache = result["cache"]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Cache Exists", str(cache["exists"]))

    with col2:
        if cache["age_minutes"] is not None:
            st.metric(
                "Cache Age",
                f"{cache['age_minutes']:.2f} min"
            )
        else:
            st.metric("Cache Age", "N/A")

    with col3:
        st.metric("Cache Valid", str(cache["valid"]))


    # -----------------------------
    # Strategy Comparison
    # -----------------------------

    st.subheader("Strategy Comparison")

    costs = result["costs"]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.write("**CACHE**")
        st.write("Valid:", costs["cache"]["valid"])

        if costs["cache"]["estimated_cost"] is not None:
            st.write("Cost:", costs["cache"]["estimated_cost"])
        else:
            st.write("Cost: Not available")

    with col2:
        st.write("**INCREMENTAL**")
        st.write("Valid:", costs["incremental"]["valid"])

        if costs["incremental"]["estimated_cost"] is not None:
            st.write("Cost:", costs["incremental"]["estimated_cost"])
        else:
            st.write("Cost: Not available")

    with col3:
        st.write("**FULL**")
        st.write("Valid:", costs["full_recompute"]["valid"])

        if costs["full_recompute"]["estimated_cost"] is not None:
            st.write("Cost:", costs["full_recompute"]["estimated_cost"])
        else:
            st.write("Cost: Not available")


    # -----------------------------
    # Cost Chart
    # -----------------------------

    st.write("**Estimated Cost Comparison (valid strategies only)**")

    chart_data = {}

    if costs["cache"]["valid"]:
       chart_data["CACHE"] = costs["cache"]["estimated_cost"]

    if costs["incremental"]["valid"]:
       chart_data["INCREMENTAL"] = costs["incremental"]["estimated_cost"]

    if costs["full_recompute"]["valid"]:
       chart_data["FULL"] = costs["full_recompute"]["estimated_cost"]

    st.bar_chart(pd.DataFrame({"Cost": chart_data}))

    st.caption("Costs are in seconds (local compute-cost proxy). CACHE is tiny, so its bar can be too small to see.")
    st.table(pd.DataFrame({"Cost (s)": chart_data}))
    
    # -----------------------------
    # Decision
    # -----------------------------

    st.subheader("Decision")

    selected = result["selected_strategy"]

    st.success(f"Selected Strategy: {selected}")

    st.write("**Reason:**")
    st.info(result["reason"])


    # -----------------------------
    # Final Result
    # -----------------------------

    st.subheader("Final Result")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Query Result**")

        if isinstance(result["final_result"], dict):

            for region, value in result["final_result"].items():
                st.write(f"**{region}:** {value:.2f}")

        else:
            st.metric(
                "Query Result",
                f"{result['final_result']:.2f}"
            )

    with col2:
        st.metric(
            "Strategy Used",
            result["selected_strategy"]
        )


    # -----------------------------
    # Result Validation
    # -----------------------------

    st.subheader("Result Validation")

    validation = result["validation"]

    col1, col2, col3 = st.columns(3)

    with col1:
        if validation["valid"]:
            st.success("Freshness Requirement: PASSED")
        else:
            st.error("Freshness Requirement: FAILED")

    with col2:
        st.metric(
            "Final Data Age",
            f"{validation['final_age']:.2f} min"
        )

    with col3:
        st.metric(
            "Allowed Age",
            f"{validation['delta']:.2f} min"
        )

    # -----------------------------
    # Experiment History
    # -----------------------------

    st.subheader("Experiment History")

    import pandas as pd
    import os

    experiment_file = "results/experiments.csv"

    if os.path.exists(experiment_file):

        experiments = pd.read_csv(experiment_file)

        st.dataframe(
            experiments,
            use_container_width=True
        )

    else:

        st.info("No experiment history available yet.")