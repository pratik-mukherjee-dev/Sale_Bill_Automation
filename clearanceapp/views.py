from django.shortcuts import render
from django.http import FileResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from .forms import ClearanceUploadForm
from .logic import extract_clean_data, generate_clearance_bills, format_bills_like_tally
import tempfile
import os


@login_required
def clearance_upload(request):
    if request.method == 'POST':
        form = ClearanceUploadForm(request.POST, request.FILES)
        if form.is_valid():
            gst_percentage = form.cleaned_data['gst_percentage']

            if gst_percentage == 0:
                uploaded_file = form.cleaned_data.get('non_taxable_file')
                file_type = "non_taxable"
            else:
                uploaded_file = form.cleaned_data.get('taxable_file')
                file_type = "taxable"

            if not uploaded_file:
                return render(request, 'clearance_error.html', {
                    'form_errors': f"Please upload {file_type} file."
                })

            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as temp_input:
                for chunk in uploaded_file.chunks():
                    temp_input.write(chunk)
                temp_input_path = temp_input.name

            sale_profit_percentage = form.cleaned_data['sale_profit_percentage']
            min_amount = form.cleaned_data['min_amount']
            max_amount = form.cleaned_data['max_amount']
            voucher_date = form.cleaned_data['voucher_date']

            try:
                stock_df = extract_clean_data(temp_input_path)

                bills_df, remaining_stocks_df = generate_clearance_bills(
                    stock_df=stock_df,
                    saleProfitPercentage=sale_profit_percentage,
                    min_amount=min_amount,
                    max_amount=max_amount,
                    gst_percentage=gst_percentage,
                )

                if bills_df.empty:
                    os.unlink(temp_input_path)
                    return render(request, 'clearance_error.html', {
                        'form_errors': 'No bills could be generated with the given constraints. '
                                       'Try adjusting min/max amount range.'
                    })

                formatted_df = format_bills_like_tally(
                    bills_df,
                    voucher_date,
                    gst_percentage
                )

            except Exception as e:
                os.unlink(temp_input_path)
                return render(request, 'clearance_error.html', {
                    'form_errors': str(e)
                })

            output_dir = tempfile.mkdtemp()

            bills_path = os.path.join(output_dir, 'ClearanceScattered.xlsx')
            tally_bills_path = os.path.join(output_dir, 'ClearanceTallyBills.xlsx')
            remained_stocks_path = os.path.join(output_dir, 'ClearanceRemained.xlsx')

            bills_df.to_excel(bills_path, index=False)
            formatted_df.to_excel(tally_bills_path, index=False)
            remaining_stocks_df.to_excel(remained_stocks_path, index=False)

            request.session['clearance_bills_path'] = bills_path
            request.session['clearance_tally_path'] = tally_bills_path
            request.session['clearance_remained_path'] = remained_stocks_path

            total_bills = bills_df['Bill No'].nunique()
            request.session['clearance_total_bills'] = total_bills

            os.unlink(temp_input_path)

            return render(request, 'clearance_result.html', {
                'total_bills': total_bills,
                'remaining_items': len(remaining_stocks_df),
            })

    else:
        form = ClearanceUploadForm()

    return render(request, 'clearance_upload.html', {'form': form})


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


@login_required
def clearance_download_bills(request):
    return _serve_and_cleanup(request, 'clearance_bills_path')


@login_required
def clearance_download_tally(request):
    return _serve_and_cleanup(request, 'clearance_tally_path')


@login_required
def clearance_download_remain(request):
    return _serve_and_cleanup(request, 'clearance_remained_path')
