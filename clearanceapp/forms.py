from django import forms
from datetime import date


class ClearanceUploadForm(forms.Form):
    sale_profit_percentage = forms.FloatField(
        label="Sale Profit %",
        initial=0,
        min_value=0,
        help_text="0 = use exact rate from Excel (even decimals)"
    )

    gst_percentage = forms.FloatField(
        label="GST % (total)",
        initial=5,
        min_value=0,
        widget=forms.NumberInput(attrs={"id": "id_gst_percentage"})
    )

    min_amount = forms.FloatField(
        label="Min Amount per Bill (₹)",
        initial=40000,
        min_value=0
    )

    max_amount = forms.FloatField(
        label="Max Amount per Bill (₹)",
        initial=50000,
        min_value=0
    )

    voucher_date = forms.DateField(
        label="Voucher Date",
        initial=date.today,
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    taxable_file = forms.FileField(
        label="Taxable Stock Excel (.xlsx)",
        required=False
    )

    non_taxable_file = forms.FileField(
        label="Non-Taxable Stock Excel (.xlsx)",
        required=False
    )

    def clean(self):
        cleaned_data = super().clean()
        min_amt = cleaned_data.get('min_amount', 0)
        max_amt = cleaned_data.get('max_amount', 0)
        if min_amt > max_amt:
            raise forms.ValidationError(
                "Min amount per bill cannot be greater than max amount."
            )
        return cleaned_data
