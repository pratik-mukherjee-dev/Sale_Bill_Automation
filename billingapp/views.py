from django.shortcuts import render
from django.http import FileResponse, HttpResponse
from .forms import UploadAndTuneForm
from .logic import extract_clean_data, generate_mixed_bills, format_bills_like_tally
from datetime import datetime
import pandas as pd
import tempfile
import os


def upload_file(request):
    if request.method == 'POST':
        form = UploadAndTuneForm(request.POST, request.FILES)
        if form.is_valid():
            gst_percentage = form.cleaned_data['gst_percentage']
            # Select correct file based on GST
            if gst_percentage == 0:
                uploaded_file = form.cleaned_data.get('non_taxable_file')
                file_type = "non_taxable"
            else:
                uploaded_file = form.cleaned_data.get('taxable_file')
                file_type = "taxable"

            if not uploaded_file:
                return render(request, 'error.html', {
                    'form_errors': f"Please upload {file_type} file."
                })

            # Save temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as temp_input:

                for chunk in uploaded_file.chunks():
                    temp_input.write(chunk)

                temp_input_path = temp_input.name

            # Extract parameters
            sale_profit_percentage = form.cleaned_data['sale_profit_percentage']
            target_bills = form.cleaned_data['target_bills']
            base_repeat_chance = form.cleaned_data['base_repeat_chance']
            normalize_coefficient = form.cleaned_data['normalize_coefficient']
            repeat_window = form.cleaned_data['repeat_window']
            min_units = form.cleaned_data['min_units']
            max_units = form.cleaned_data['max_units']
            voucher_date = form.cleaned_data['voucher_date']

            try:

                stock_df = extract_clean_data(temp_input_path)

                bills_df, remaining_stocks_df = generate_mixed_bills(
                    stock_df=stock_df,
                    saleProfitPercentage=sale_profit_percentage,
                    target_bills=target_bills,
                    base_repeat_chance=base_repeat_chance,
                    normalize_coefficient=normalize_coefficient,
                    repeat_window=repeat_window,
                    min_units=min_units,
                    max_units=max_units,
                )

                formatted_df = format_bills_like_tally(
                    bills_df,
                    voucher_date,
                    gst_percentage
                )

            except Exception as e:

                os.unlink(temp_input_path)

                return render(request, 'error.html', {
                    'form_errors': str(e)
                })

            output_dir = tempfile.mkdtemp()

            bills_path = os.path.join(output_dir, 'ScatteredStocks.xlsx')
            tally_bills_path = os.path.join(output_dir, 'TallyBills.xlsx')
            remained_stocks_path = os.path.join(output_dir, 'RemainedStocks.xlsx')

            bills_df.to_excel(bills_path, index=False)
            formatted_df.to_excel(tally_bills_path, index=False)
            remaining_stocks_df.to_excel(remained_stocks_path, index=False)

            request.session['bills_path'] = bills_path
            request.session['tally_bills_path'] = tally_bills_path
            request.session['remained_stocks_path'] = remained_stocks_path

            os.unlink(temp_input_path)

            return render(request, 'result.html')

    else:

        form = UploadAndTuneForm()

    return render(request, 'upload.html', {'form': form})


def _serve_and_cleanup(request, session_key):
    file_path = request.session.get(session_key)
    if not file_path or not os.path.exists(file_path):
        return HttpResponse("File not found or session expired.", status=404)

    response = FileResponse(
        open(file_path, 'rb'),
        as_attachment=True,
        filename=os.path.basename(file_path)
    )

    parent_dir = os.path.dirname(file_path)

    original_close = response.close

    def patched_close():
        original_close()
        try:
            os.unlink(file_path)
            if os.path.isdir(parent_dir) and not os.listdir(parent_dir):
                os.rmdir(parent_dir)
        except OSError:
            pass

    response.close = patched_close
    return response


def download_bills(request):
    return _serve_and_cleanup(request, 'bills_path')


def download_tally(request):
    return _serve_and_cleanup(request, 'tally_bills_path')


def download_remain(request):
    return _serve_and_cleanup(request, 'remained_stocks_path')
