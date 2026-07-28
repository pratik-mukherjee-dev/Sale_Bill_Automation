from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, getcontext
import pandas as pd
import random
import math


def tally_default_round(value, precision=0.01):
    getcontext().prec = 12
    value = Decimal(str(value))
    step = Decimal(str(precision))
    rounded_value = (value / step).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * step
    return rounded_value


def calculate_item_wise_gst(group, gstPercentage):
    gst_rate_half = Decimal(str(gstPercentage)) / Decimal('200')
    total_cgst = Decimal('0.00')
    total_sgst = Decimal('0.00')

    for row in group.itertuples():
        value = Decimal(str(row.Value))
        cgst_item = (value * gst_rate_half).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        sgst_item = (value * gst_rate_half).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_cgst += cgst_item
        total_sgst += sgst_item

    return tally_default_round(total_cgst), tally_default_round(total_sgst)


def round_up_gross(value: float):
    rounded_value = tally_default_round(value, precision=1)
    rounded_off = rounded_value - Decimal(str(value))
    return rounded_value, rounded_off


def selling_price(purchase_rate, saleProfitPercentage):
    if saleProfitPercentage == 0:
        return purchase_rate  # exact rate from Excel, decimals preserved
    base = purchase_rate * ((100 + saleProfitPercentage) / 100)
    return round(base, 2)


def extract_clean_data(filepath):
    df_raw = pd.read_excel(filepath, sheet_name=0, header=None)
    header_row = None
    for i, row in df_raw.iterrows():
        if ("Quantity" in row.values) and ("Rate" in row.values) and ("Value" in row.values):
            header_row = i
            break

    if header_row is None:
        raise ValueError("Could not find header row with Quantity, Rate, Value")

    stock_df = df_raw.iloc[header_row + 1:, [0, 1, 2, 3]].copy()
    stock_df.columns = ["Particulars", "Quantity", "Rate", "Value"]

    stock_df = stock_df.dropna(subset=["Particulars", "Quantity", "Rate"], how="any")

    stock_df["Particulars"] = stock_df["Particulars"].astype(str)
    stock_df["Quantity"] = stock_df["Quantity"].astype(int)
    stock_df["Rate"] = stock_df["Rate"].astype(float)
    stock_df.reset_index(drop=True, inplace=True)
    return stock_df


def generate_clearance_bills(
        stock_df: pd.DataFrame,
        saleProfitPercentage: float,
        min_amount: float,
        max_amount: float,
        gst_percentage: float = 0,
):
    """
    Generate bills until every stock item's quantity reaches zero,
    or no more valid bills can be formed within the amount constraints.

    min_amount and max_amount refer to the FINAL bill value (including GST).
    """
    bills = []
    bill_no = 1
    df = stock_df.copy()
    df["Quantity"] = df["Quantity"].astype(int)
    df["Rate"] = df["Rate"].astype(float)

    # precompute selling rates
    df["SellingRate"] = df["Rate"].apply(
        lambda r: selling_price(r, saleProfitPercentage)
    )

    # GST multiplier to estimate final bill value from base value
    gst_multiplier = 1 + (gst_percentage / 100)

    max_stall_rounds = 50
    stall_count = 0

    while df["Quantity"].sum() > 0:
        bill_items = []
        bill_total = 0.0  # base value (before GST)
        used_items_in_bill = set()

        # effective max base value so that base * gst_multiplier <= max_amount
        effective_max_base = max_amount / gst_multiplier
        effective_min_base = min_amount / gst_multiplier

        available = df[df["Quantity"] > 0].index.tolist()
        random.shuffle(available)

        if not available:
            break

        for idx in available:
            item_name = df.at[idx, "Particulars"].strip()

            if item_name in used_items_in_bill:
                continue

            sell_rate = df.at[idx, "SellingRate"]
            stock_qty = df.at[idx, "Quantity"]

            if sell_rate <= 0 or stock_qty <= 0:
                continue

            remaining_budget = effective_max_base - bill_total
            if remaining_budget < sell_rate:
                continue

            max_by_budget = int(remaining_budget / sell_rate)
            max_allowed = min(stock_qty, max_by_budget)

            if max_allowed <= 0:
                continue

            sell_qty = random.randint(1, max_allowed)
            line_value = round(sell_qty * sell_rate, 2)

            bill_items.append({
                "Bill No": bill_no,
                "Item": item_name,
                "Quantity": sell_qty,
                "Selling Rate": sell_rate,
                "Value": line_value,
                "Profit %": round(
                    (((sell_rate - df.at[idx, "Rate"]) * 100) / df.at[idx, "Rate"]), 2
                ) if df.at[idx, "Rate"] != 0 else 0,
                "Purchase Rate": df.at[idx, "Rate"],
            })

            bill_total += line_value
            used_items_in_bill.add(item_name)

            df.at[idx, "Quantity"] -= sell_qty

            if bill_total >= effective_max_base:
                break

        # validate bill meets minimum (GST-inclusive check)
        if bill_items and bill_total >= effective_min_base:
            bills.extend(bill_items)
            bill_no += 1
            stall_count = 0
        elif bill_items:
            for item in bill_items:
                match = df[df["Particulars"].str.strip() == item["Item"]]
                if not match.empty:
                    df.at[match.index[0], "Quantity"] += item["Quantity"]
            stall_count += 1
        else:
            stall_count += 1

        if stall_count >= max_stall_rounds:
            break

    remaining_df = df[["Particulars", "Quantity", "Rate"]].copy()
    remaining_df = remaining_df[remaining_df["Quantity"] > 0].reset_index(drop=True)

    return pd.DataFrame(bills), remaining_df


def format_bills_like_tally(bills_df, voucher_date, gstPercentage):
    rows = []
    today_str = voucher_date.strftime("%d-%b-%y")

    for bill_no, group in bills_df.groupby("Bill No", sort=True):
        group_total = group["Value"].sum()
        cgst, sgst = calculate_item_wise_gst(group, gstPercentage)
        gross, rounded_off = round_up_gross(float(group_total) + float(cgst) + float(sgst))

        voucher_type = "Sales"
        if gstPercentage == 0:
            voucher_type = "Exempt Sale"

        for i, row in enumerate(group.itertuples()):
            rows.append({
                "Voucher Date": today_str if i == 0 else "",
                "Voucher Type Name": voucher_type if i == 0 else "",
                "Change Mode": "Item Invoice" if i == 0 else "",
                "Voucher Number": bill_no if i == 0 else "",
                "Rounded Amount": rounded_off if i == 0 else "",
                "Buyer/Supplier - Country": "India" if i == 0 else "",
                "Buyer/Supplier - State": "West Bengal" if i == 0 else "",
                "Buyer/Supplier - Place of Supply": "West Bengal" if i == 0 else "",
                "Ledger Name-Cash": "0Cash" if i == 0 else "",
                "Cash Amount Dr/Cr": "dr" if i == 0 else "",
                "Ledger Name-Sales": "Sales" if i == 0 else "",
                "Buyer/Supplier - Registration Type": "Unregistered/Consumer" if i == 0 else "",
                "Sales Amount Dr/Cr": "Cr" if i == 0 else "",
                "Ledger Name-Cgst": "C-Gst" if i == 0 else "",
                "Ledger Amount - Cgst": cgst if i == 0 else "",
                "Cgst Amount Dr/Cr": "cr" if i == 0 else "",
                "Ledger Name-Sgst": "S-Gst" if i == 0 else "",
                "Ledger Amount - Sgst": sgst if i == 0 else "",
                "Sgst Amount Dr/Cr": "cr" if i == 0 else "",
                "Rounded off": "Rounded off" if i == 0 else "",
                "Ledger Amount - Sales": group_total if i == 0 else "",
                "Ledger Amount - Cash": gross if i == 0 else "",
                "Item Name": row.Item,
                "Billed Quantity": row.Quantity,
                "Item Rate": row._4,
                "Item Rate per": "",
                "Tax Rate": f"{gstPercentage / 2:.2f}%" if gstPercentage else "",
                "Item Amount": row.Value
            })

    return pd.DataFrame(rows)
