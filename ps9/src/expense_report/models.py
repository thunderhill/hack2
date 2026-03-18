from pydantic import BaseModel, Field


class ExpenseItem(BaseModel):
    date: str = Field(description="Date of expense")
    category: str = Field(description="Category: flights | hotel | meals | transport | conference | other")
    description: str = Field(description="Description of the expense")
    amount: float = Field(description="Amount in original currency")
    currency: str = Field(description="Currency code e.g. USD, INR, EUR")
    amount_usd: float = Field(description="Amount converted to USD")
    receipt_present: bool = Field(description="Whether receipt was mentioned/provided")
    policy_status: str = Field(description="Policy status: within_policy | exceeds_limit | needs_approval | non_reimbursable")
    notes: str = Field(description="Any notes about this expense item")


class CategorySummary(BaseModel):
    category: str
    total_usd: float
    item_count: int


class ExpenseSummary(BaseModel):
    employee_name: str = Field(description="Employee name extracted from input or 'Not specified'")
    trip_purpose: str = Field(description="Purpose of the trip")
    trip_dates: str = Field(description="Trip date range")
    destination: str = Field(description="Travel destination")
    total_claimed: float = Field(description="Total amount claimed in USD")
    total_approved: float = Field(description="Total amount recommended for approval in USD")
    total_rejected: float = Field(description="Total amount recommended for rejection in USD")
    items: list[ExpenseItem] = Field(description="Itemized expense list")
    category_breakdown: list[CategorySummary] = Field(description="Summary by expense category")
    policy_violations: list[str] = Field(description="List of policy violations found")
    missing_receipts: list[str] = Field(description="Items missing receipts")
    approval_recommendation: str = Field(description="APPROVE_FULL | APPROVE_PARTIAL | REJECT | NEEDS_MORE_INFO")
    approval_notes: str = Field(description="Notes for the approver explaining the recommendation")
    reimbursement_breakdown: str = Field(description="Summary of what will and won't be reimbursed")
