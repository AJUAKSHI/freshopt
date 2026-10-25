import re

def analyze_query(sql_query: str) -> dict:
    """
    Parses a basic SQL query string into a structured dictionary.
    """
    # Clean up trailing semicolons or extra spaces
    cleaned_query = sql_query.strip().rstrip(';')
    
    # Default output template
    analysis = {
        "raw_query": sql_query,
        "query_type": "SCAN",
        "operation": None,
        "target_column": None,
        "table": None,
        "where_clause": None,
        "group_by": None
    }
    
    upper_query = cleaned_query.upper()
    
    # 1. Check for Aggregations (SUM, COUNT, AVG)
    if "SUM" in upper_query:
        analysis["query_type"] = "AGGREGATION"
        analysis["operation"] = "SUM"
    elif "COUNT" in upper_query:
        analysis["query_type"] = "AGGREGATION"
        analysis["operation"] = "COUNT"
    elif "AVG" in upper_query:
        analysis["query_type"] = "AGGREGATION"
        analysis["operation"] = "AVG"

    # 2. Extract column inside aggregate function, e.g., SUM(amount) -> 'amount'
    col_match = re.search(r'(?:SUM|COUNT|AVG)\((.*?)\)', cleaned_query, re.IGNORECASE)
    if col_match:
        analysis["target_column"] = col_match.group(1).strip()

    # 3. Extract Table Name after FROM, e.g., FROM sales -> 'sales'
    table_match = re.search(r'FROM\s+(\w+)', cleaned_query, re.IGNORECASE)
    if table_match:
        analysis["table"] = table_match.group(1).strip()

    # 4. Extract WHERE clause (if present)
    where_match = re.search(r'WHERE\s+(.*?)(?:GROUP BY|$)', cleaned_query, re.IGNORECASE)
    if where_match:
        analysis["where_clause"] = where_match.group(1).strip()

    # 5. Extract GROUP BY clause (if present)
    group_match = re.search(r'GROUP BY\s+(.*)', cleaned_query, re.IGNORECASE)
    if group_match:
        analysis["group_by"] = group_match.group(1).strip()

    return analysis


# --- LOCAL TEST BLOCK ---
# This block only runs if you execute this file directly.
if __name__ == "__main__":
    test_query_1 = "SELECT SUM(amount) FROM sales;"
    test_query_2 = "SELECT region, SUM(amount) FROM sales WHERE region = 'South' GROUP BY region;"
    
    print("Test 1 Result:", analyze_query(test_query_1))
    print("\nTest 2 Result:", analyze_query(test_query_2))