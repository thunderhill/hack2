SYSTEM_PROMPT = """You are a senior quality engineer with expertise in manufacturing quality control and ISO 9001 standards.
Given inspection data including defect descriptions, measurements, and observations, you:
1. Classify and catalog all defects by type and severity
2. Determine overall pass/fail status
3. Calculate a quality score
4. Identify root causes
5. Recommend corrective and preventive actions
6. Provide disposition recommendation

Apply rigorous quality engineering standards in your analysis."""


def build_user_message(inspection_data: str, product_type: str = "") -> str:
    product_context = f"\nProduct type: {product_type}" if product_type else ""
    return f"""Generate a quality inspection report for the following inspection data:{product_context}

--- INSPECTION DATA ---
{inspection_data}
--- END DATA ---

Provide a complete quality inspection report with defect classification, quality score, root cause analysis, and recommendations."""
