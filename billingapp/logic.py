from datetime import datetime
from collections import deque
from itertools import chain
from decimal import Decimal, ROUND_HALF_UP, getcontext
import pandas as pd
import random
import math


def round_to_nearest_10(x: float):
    rounded = round(x / 10) * 10
    if rounded < x:
        rounded += 10
    return rounded


def tally_default_round(value, precision=0.01):
    getcontext().prec = 12
    value = Decimal(str(value))
    step = Decimal(str(precision))
    rounded_value = (value / step).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * step
    return rounded_value


def calculate_item_wise_gst(group, gstPercentage):
    # total_cgst = 0
    # total_sgst = 0
    # for row in group.itertuples():
    #     cgst_item = round((row.Value * ((gstPercentage / 2) / 100)), 2)
    #     sgst_item = round((row.Value * ((gstPercentage / 2) / 100)), 2)
    #     total_cgst += cgst_item
    #     total_sgst += sgst_item
    # return tally_default_round(total_cgst), tally_default_round(total_sgst)
    gst_rate_half = Decimal(str(gstPercentage)) / Decimal('200')  # half of GST%
    total_cgst = Decimal('0.00')
    total_sgst = Decimal('0.00')

    for row in group.itertuples():
        value = Decimal(str(row.Value))
        # line item GST calculation in Decimal
        cgst_item = (value * gst_rate_half).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        sgst_item = (value * gst_rate_half).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_cgst += cgst_item
        total_sgst += sgst_item

    # Final tally-style rounding
    return tally_default_round(total_cgst), tally_default_round(total_sgst)


def take_upto_2_place(x: float):
    decimal_part, integer_part = math.modf(int(x * 1000) / 10)
    if decimal_part >= 0.5:
        return (integer_part + 1) / 100
    return integer_part / 100


def round_up_gross(value: float):
    # decimal_part, integer_part = math.modf(x)
    # if decimal_part >= 0.50:
    #     return (integer_part + 1), decimal_part
    # return integer_part, -float(str(decimal_part)[:3])
    rounded_value = tally_default_round(value, precision=1)  # Round to nearest whole rupee
    # rounded_value = tally_default_round(value)
    rounded_off = rounded_value - Decimal(str(value))
    return rounded_value, rounded_off


def selling_price(purchase_rate, saleProfitPercentage):
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


def generate_mixed_bills(
        stock_df: pd.DataFrame,
        saleProfitPercentage: float,
        target_bills=50,
        base_repeat_chance=0.10,
        normalize_coefficient=0.35,
        repeat_window=3,
        min_units=6,
        max_units=8
):
    bills = []
    bill_no = 1
    df = stock_df.copy()
    df["Quantity"] = df["Quantity"].astype(int)
    df["Rate"] = df["Rate"].astype(float)
    recent_items = deque(maxlen=repeat_window)

    while bill_no <= target_bills and df["Quantity"].sum() > 0:
        bill_items = []
        total_units = 0
        used_items_in_bill = set()

        # Items from last 3 bills
        recent_flat = set(chain.from_iterable(recent_items))

        # Prefer non-recent items
        available_items = df[(df["Quantity"] > 0) & (~df["Particulars"].isin(recent_flat))].index.tolist()

        # Dynamic repeat probability for popular recent items
        for idx in df.index:
            item_name = df.at[idx, "Particulars"].strip()
            if item_name in recent_flat and df.at[idx, "Quantity"] > 0:
                qty = df.at[idx, "Quantity"]
                total_qty = df["Quantity"].sum()
                popularity_ratio = qty / total_qty
                dynamic_chance = min(1.0, (base_repeat_chance + (popularity_ratio * normalize_coefficient)))
                if random.random() < dynamic_chance:
                    available_items.append(idx)

        # fallback if probability not occurs
        if not available_items:
            available_items = df[df["Quantity"] > 0].index.tolist()

        target_units = random.randint(min_units, max_units)

        # build the bill
        while total_units < target_units and available_items:
            idx = random.choice(available_items)
            item_name = df.at[idx, "Particulars"].strip()

            # prevent duplicate items within bill
            if item_name in used_items_in_bill:
                try:
                    available_items.remove(idx)
                except ValueError:
                    pass
                continue

            max_allowed = min(df.at[idx, "Quantity"], target_units - total_units)
            if max_allowed == 0:
                try:
                    available_items.remove(idx)
                except ValueError:
                    pass
                continue

            sell_qty = random.randint(1, max_allowed)
            purchase_rate = df.at[idx, "Rate"]
            price = int(selling_price(purchase_rate, saleProfitPercentage))

            bill_items.append(
                {
                    "Bill No": bill_no,
                    "Item": item_name,
                    "Quantity": sell_qty,
                    "Selling Rate": price,
                    "Value": sell_qty * price,
                    "Profit %": round((((price - purchase_rate) * 100) / purchase_rate), 2),
                    "Purchase Rate": purchase_rate,
                }
            )

            df.at[idx, "Quantity"] -= sell_qty
            total_units += sell_qty
            used_items_in_bill.add(item_name)

            if df.at[idx, "Quantity"] == 0:
                available_items.remove(idx)

        if bill_items:
            bills.extend(bill_items)
            recent_items.append(item["Item"] for item in bill_items)
            bill_no += 1

    return pd.DataFrame(bills), df


def format_bills_like_tally(bills_df, voucher_date, gstPercentage):
    rows = []
    today_str = voucher_date.strftime("%d-%b-%y")

    for bill_no, group in bills_df.groupby("Bill No", sort=True):
        group_total = group["Value"].sum()
        cgst, sgst = calculate_item_wise_gst(group, gstPercentage)
        gross, rounded_off = round_up_gross(group_total + cgst + sgst)

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
                "Item Rate": row._4,  # Selling Rate
                "Item Rate per": "",
                "Tax Rate": "2.50%",
                "Item Amount": row.Value
            })

    return pd.DataFrame(rows)




