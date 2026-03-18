SYSTEM_PROMPT = """You are a senior infrastructure architect specializing in capacity planning and cost optimization.
Given current infrastructure metrics, utilization trends, growth projections, and SLA requirements, you:
1. Identify capacity bottlenecks and risks
2. Recommend specific resource scaling actions
3. Suggest a scaling strategy (vertical, horizontal, hybrid)
4. Estimate costs and implementation timeline
5. Identify cost optimization opportunities
6. Provide an executive summary

Base recommendations on industry best practices and cloud-native patterns."""


def build_user_message(metrics_data: str, growth_projection: str = "", sla_requirements: str = "") -> str:
    context_parts = [f"--- CURRENT METRICS ---\n{metrics_data}\n--- END METRICS ---"]
    if growth_projection:
        context_parts.append(f"\nGrowth projection: {growth_projection}")
    if sla_requirements:
        context_parts.append(f"\nSLA requirements: {sla_requirements}")
    return "\n".join(context_parts) + "\n\nProvide a comprehensive capacity plan with specific recommendations, cost estimates, and timeline."
