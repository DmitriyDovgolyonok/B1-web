import decimal

from app import app
"""
custom filter to determine whether a value is stirng or numeric data
"""

@app.template_filter()
def table_cell(value):
    if isinstance(value, (decimal.Decimal, float)):
        return round(value, 2) # rounding it down to 2 digits
    return value
