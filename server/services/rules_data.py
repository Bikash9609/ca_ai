"""
Initial GST rules data for population
"""

from datetime import date
from typing import List, Dict, Any


INITIAL_RULES: List[Dict[str, Any]] = [
    {
        "rule_id": "itc_36_4",
        "name": "Rule 36(4) - ITC Blocking for Vendor Not in GSTR-2B",
        "rule_text": "Input tax credit shall not be available in respect of invoices or debit notes, the details of which have not been furnished by the supplier in FORM GSTR-1 or using the invoice furnishing facility, and the details of which have not been communicated to the recipient in FORM GSTR-2B. This rule applies when the vendor has not filed GSTR-1 or the invoice is not reflected in the recipient's GSTR-2B.",
        "citation": "CGST Rules, 2017 - Rule 36(4)",
        "circular_number": None,
        "effective_from": date(2021, 1, 1),
        "effective_to": None,
        "category": "itc",
        "version": "1.0.0",
        "rule_logic": {
            "condition_type": "vendor_not_in_gstr2b",
            "condition_logic": {
                "field": "vendor_gstin",
                "operator": "not_in",
                "source": "gstr2b_vendors"
            },
            "action_type": "block_itc",
            "action_percentage": 100.0,
            "action_amount_formula": "invoice_tax_amount",
            "priority": 1
        }
    },
    {
        "rule_id": "itc_42",
        "name": "Rule 42 - ITC Reversal for Partially Exempt Supplies",
        "rule_text": "Where the goods or services or both are used by the registered person partly for effecting taxable supplies including zero-rated supplies and partly for effecting exempt supplies, the amount of credit shall be restricted to so much of the input tax as is attributable to the said taxable supplies including zero-rated supplies. The reversal amount is calculated based on the ratio of exempt supplies to total supplies.",
        "citation": "CGST Rules, 2017 - Rule 42",
        "circular_number": None,
        "effective_from": date(2017, 7, 1),
        "effective_to": None,
        "category": "itc",
        "version": "1.0.0",
        "rule_logic": {
            "condition_type": "partial_exempt_supplies",
            "condition_logic": {
                "exempt_supply_ratio": "exempt_supplies / total_supplies"
            },
            "action_type": "reverse_itc",
            "action_percentage": None,
            "action_amount_formula": "itc_amount * (exempt_supplies / total_supplies)",
            "priority": 2
        }
    },
    {
        "rule_id": "section_17_5",
        "name": "Section 17(5) - Blocked Input Tax Credits",
        "rule_text": "Notwithstanding anything contained in sub-section (1) of section 16 and sub-section (1) of section 18, input tax credit shall not be available in respect of the following: (a) motor vehicles and other conveyances except when they are used for specified purposes; (b) food and beverages, outdoor catering, beauty treatment, health services, cosmetic and plastic surgery; (c) membership of a club, health and fitness centre; (d) rent-a-cab, life insurance and health insurance; (e) travel benefits extended to employees on vacation such as leave or home travel concession; (f) works contract services when supplied for construction of immovable property; (g) goods or services received by a taxable person for construction of immovable property on his own account; (h) goods or services on which tax has been paid under composition scheme; (i) goods or services used for personal consumption; (j) goods lost, stolen, destroyed, written off or disposed of by way of gift or free samples.",
        "citation": "CGST Act, 2017 - Section 17(5)",
        "circular_number": None,
        "effective_from": date(2017, 7, 1),
        "effective_to": None,
        "category": "blocked_credits",
        "version": "1.0.0",
        "rule_logic": {
            "condition_type": "blocked_category",
            "condition_logic": {
                "blocked_categories": [
                    "motor_vehicles",
                    "food_beverages",
                    "club_membership",
                    "rent_a_cab",
                    "life_insurance",
                    "health_insurance",
                    "works_contract_construction",
                    "construction_own_account",
                    "composition_scheme",
                    "personal_consumption",
                    "lost_stolen_destroyed"
                ]
            },
            "action_type": "block_itc",
            "action_percentage": 100.0,
            "action_amount_formula": "invoice_tax_amount",
            "priority": 0
        }
    },
    {
        "rule_id": "filing_gstr1_due_date",
        "name": "GSTR-1 Filing Due Date",
        "rule_text": "GSTR-1 must be filed by the 11th day of the month following the tax period for taxpayers with annual turnover up to Rs. 5 crores (who have opted for quarterly filing, the due date is 13th of the month following the quarter). For taxpayers with annual turnover above Rs. 5 crores, GSTR-1 must be filed by the 11th day of the month following the tax period. Late filing attracts interest and late fee.",
        "citation": "CGST Rules, 2017",
        "circular_number": None,
        "effective_from": date(2017, 7, 1),
        "effective_to": None,
        "category": "filing",
        "version": "1.0.0",
        "rule_logic": None
    },
    {
        "rule_id": "filing_gstr3b_due_date",
        "name": "GSTR-3B Filing Due Date",
        "rule_text": "GSTR-3B must be filed by the 20th day of the month following the tax period. This is a summary return that includes details of outward supplies, inward supplies, input tax credit availed, and tax payable. Late filing attracts interest at 18% per annum and late fee of Rs. 50 per day (Rs. 20 for nil returns) subject to maximum of Rs. 5,000.",
        "citation": "CGST Rules, 2017",
        "circular_number": None,
        "effective_from": date(2017, 7, 1),
        "effective_to": None,
        "category": "filing",
        "version": "1.0.0",
        "rule_logic": None
    },
    {
        "rule_id": "itc_amount_mismatch",
        "name": "ITC Amount Mismatch - GSTR-2B vs Purchase Invoices",
        "rule_text": "When the ITC amount in GSTR-2B does not match the ITC amount in purchase invoices, the difference must be reconciled. If the GSTR-2B amount is less than the invoice amount, the excess ITC cannot be claimed unless the supplier files GSTR-1 and the invoice appears in GSTR-2B. The recipient should communicate with the supplier to ensure proper filing.",
        "citation": "CGST Rules, 2017 - Rule 36(4)",
        "circular_number": None,
        "effective_from": date(2021, 1, 1),
        "effective_to": None,
        "category": "itc",
        "version": "1.0.0",
        "rule_logic": {
            "condition_type": "amount_mismatch",
            "condition_logic": {
                "comparison": "gstr2b_amount < invoice_amount"
            },
            "action_type": "block_itc",
            "action_percentage": None,
            "action_amount_formula": "invoice_amount - gstr2b_amount",
            "priority": 1
        }
    }
]
