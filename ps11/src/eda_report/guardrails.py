import pandas as pd
from eda_report.models import GuardrailResult

_PII_PATTERNS = {"email", "phone", "ssn", "passport", "dob", "address", "mobile", "national_id"}

def validate_dataframe(df: pd.DataFrame, file_size_mb: float) -> GuardrailResult:
    errors: list[str] = []
    warnings: list[str] = []
    truncated = False

    if file_size_mb > 50:
        errors.append(f"File size {file_size_mb:.1f}MB exceeds 50MB limit. Please reduce file size.")
        return GuardrailResult(ok=False, errors=errors, warnings=warnings, truncated=False, df=df)

    if df.shape[1] > 100:
        warnings.append(f"Dataset has {df.shape[1]} columns (>100). Analysis may be slow.")

    if df.shape[0] > 10_000:
        df = df.head(10_000)
        truncated = True
        warnings.append("Dataset truncated to 10,000 rows for performance.")

    col_lower = {c.lower() for c in df.columns}
    pii_found = col_lower & _PII_PATTERNS
    for pii in sorted(pii_found):
        warnings.append(f"Possible PII column detected: '{pii}'. Ensure data is anonymized.")

    return GuardrailResult(ok=True, errors=errors, warnings=warnings, truncated=truncated, df=df)
