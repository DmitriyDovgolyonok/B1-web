import csv
from io import StringIO

from flask import request, redirect, render_template, make_response

from filters import app
from mappings import file_result_mapper, file_class_mapper
from utils import validated_file_with_flush, save_xls_with_flush, get_file_list, generate_file_table
"""
Request handlers
"""

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        file = validated_file_with_flush()

        if not file:
            return redirect(request.url)

        status = save_xls_with_flush(file)

        if not status:
            return redirect(request.url)

    return render_template('upload.html')


@app.route('/files/', methods=['GET'])
def file_list():
    files = get_file_list()
    return render_template('file_list.html', files=files)


@app.route('/files/<int:file_id>/', methods=['GET'])
def file_detail(file_id):
    file, table = generate_file_table(file_id)
    return render_template('file_detail.html', file=file, table=table, mapper=file_result_mapper | file_class_mapper)


@app.route('/download/<int:file_id>/')
def download(file_id):
    si = StringIO()
    cw = csv.writer(si)
    file, table = generate_file_table(file_id)
    formatted_table = [[f"{elem}" if isinstance(elem, str) else round(elem, 2) for elem in row] for row in table]
    cw.writerows(formatted_table)
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=File{file_id}_export.csv"
    output.headers["Content-type"] = "text/csv"
    return output
