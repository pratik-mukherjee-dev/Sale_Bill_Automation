from django import forms


class UploadAndTuneForm(forms.Form):
    sale_profit_percentage = forms.FloatField(
        label="Sales Profit %",
        initial=1.5,
        min_value=0
    )

    gst_percentage = forms.FloatField(
        label="GST % (total)",
        initial=5,
        min_value=0,
        widget=forms.NumberInput(attrs={"id": "id_gst_percentage"})
    )

    target_bills = forms.IntegerField(
        label="Number of bills",
        initial=100,
        min_value=1
    )

    base_repeat_chance = forms.FloatField(
        label="Base repeat chance (0–1)",
        initial=0.3,
        min_value=0,
        max_value=1
    )

    normalize_coefficient = forms.FloatField(
        label="Randomization force (0–1)",
        initial=0.35,
        min_value=0,
        max_value=1
    )

    repeat_window = forms.IntegerField(
        label="Repeat window",
        initial=5,
        min_value=1
    )

    min_units = forms.IntegerField(
        label="Min units per bill",
        initial=6,
        min_value=1
    )

    max_units = forms.IntegerField(
        label="Max units per bill",
        initial=10,
        min_value=1
    )

    voucher_date = forms.DateField(
        label="Voucher Date",
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
