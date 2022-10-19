import re
from datetime import datetime
from typing import Generator

import xlrd
from flask import request, flash
from werkzeug.datastructures import FileStorage
from xlrd.sheet import Sheet

from app import ALLOWED_EXTENSIONS, db
from mappings import file_class_mapper, file_result_mapper
from models import FileInfo, AccountData, BankAccount


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def validated_file_with_flush() -> FileStorage or None:
    if 'file' not in request.files:
        flash('No file part', 'error')
        return None

    file = request.files['file']
    if file.filename == '':
        flash('No selected file', 'error')
        return None

    if not file or not allowed_file(file.filename):
        flash('Incorrect type', 'error')
        return None

    return file


def produce_data_row_generator(sheet: Sheet, row_index_list: list) -> Generator:
    return ([sheet.cell(i, row).value for row in row_index_list] for i in range(8, sheet.nrows)
            if re.match(r'^(\d){4}$', str(sheet.cell(i, 0).value)))


def parse_xls(file: FileStorage) -> tuple[Generator, Generator, str, datetime]:
    workbook = xlrd.open_workbook(file_contents=file.read())
    sheet = workbook.sheet_by_name(workbook.sheet_names()[0])

    bank_name = sheet.cell(0, 0).value
    pub_date = xlrd.xldate_as_datetime(sheet.cell(5, 0).value, 0)

    return produce_data_row_generator(sheet, [0]), produce_data_row_generator(
        sheet, list(range(1, 5))), bank_name, pub_date


def save_account_data(row_data_generator):
    account_data_to_create = []
    for data in row_data_generator:
        opening_balance = AccountData(active=data[0], passive=data[1])
        turnover = AccountData(active=data[2], passive=data[3])
        account_data_to_create += [opening_balance, turnover]
    db.session.bulk_save_objects(account_data_to_create, return_defaults=True)
    return account_data_to_create


def save_bank_account(account_id_generator, account_data_to_create, file_info):
    bank_accounts_to_create = []
    for index, data in enumerate(account_id_generator):
        bank_account = BankAccount(account_id=data[0], file_info_id=file_info.id,
                                   opening_balance_id=account_data_to_create[index * 2].id,
                                   turnover_id=account_data_to_create[index * 2 + 1].id, )
        bank_accounts_to_create.append(bank_account)
    db.session.bulk_save_objects(bank_accounts_to_create)


def save_file_info(file, bank_name, pub_date):
    file_info = FileInfo(file_name=file.filename, date_created=datetime.utcnow(), bank_name=bank_name,
                         pub_date=pub_date)

    db.session.add(file_info)
    db.session.flush()
    return file_info


def clear_existing_file_data(bank_name, pub_date):
    file_info = FileInfo.query.filter_by(bank_name=bank_name, pub_date=pub_date).first()
    if not file_info:
        return

    bank_account_ids = []
    for bank_account in BankAccount.query.all():
        bank_account_ids += [bank_account.opening_balance_id, bank_account.turnover_id]

    db.session.query(AccountData).filter(AccountData.id.in_(bank_account_ids)).delete()
    db.session.query(BankAccount).filter(BankAccount.id.in_(bank_account_ids)).delete()
    db.session.delete(file_info)
    db.session.flush()


def save_xls_import(file: FileStorage) -> bool:
    try:
        account_id_generator, row_data_generator, bank_name, pub_date = parse_xls(file)
        clear_existing_file_data(bank_name, pub_date)

        file_info = save_file_info(file, bank_name, pub_date)
        account_data_to_create = save_account_data(row_data_generator)
        save_bank_account(account_id_generator, account_data_to_create, file_info)

        db.session.commit()
        return True
    except Exception:
        return False


def save_xls_with_flush(file: FileStorage) -> bool:
    if not save_xls_import(file):
        flash('Incorrect format', 'error')
        return False
    return True


def get_file_list():
    files = FileInfo.query.all()
    return files


def add_table_row(account, table):
    inc_active = account.opening_balance.active
    inc_passive = account.opening_balance.passive
    tu_active = account.turnover.active
    tu_passive = account.turnover.passive
    out_active = 0
    if inc_active:
        out_active = inc_active + tu_active - tu_passive
    out_passive = 0
    if inc_passive:
        out_passive = inc_passive - tu_active + tu_passive
    table.append([account.account_id, inc_active, inc_passive, tu_active, tu_passive, out_active, out_passive])


def add_group_result_row(table, group_sums, row_aggregation_count, prev_group_index):
    group_sum_row = [sum(x) for x in zip(*table[-row_aggregation_count:])]
    group_sums.append(group_sum_row)
    table.append(group_sum_row)
    table[-1][0] = prev_group_index


def add_group_row(account, table, row_aggregation_count, group_sums):
    prev_group_index = table[-1][0] // 100
    cur_group_index = account.account_id // 100
    if row_aggregation_count and prev_group_index != cur_group_index:
        add_group_result_row(table, group_sums, row_aggregation_count, prev_group_index)
        return True
    return False


def add_class_result_row(table, group_sums, class_sums):
    class_sum_row = [sum(x) for x in zip(*group_sums)]
    class_sums.append(class_sum_row[1:])
    table.append(class_sum_row)
    table[-1][0] = file_result_mapper['class_result']
    group_sums.clear()


def add_table_result_row(table, class_sums):
    table.append([sum(x) for x in zip(*class_sums)])
    table[-1].insert(0, file_result_mapper['table_result'])


def add_class_row(account, table, row_aggregation_count, group_sums, class_sums):
    prev_class_index = table[-1][0] // 10
    cur_class_index = account.account_id // 1000
    if not row_aggregation_count and prev_class_index != cur_class_index:
        if group_sums:
            add_class_result_row(table, group_sums, class_sums)
        table.append([file_class_mapper[account.account_id // 1000]])


def generate_file_table(file_id):
    file = FileInfo.query.filter_by(id=file_id).first_or_404()
    accounts = BankAccount.query.filter_by(file_info_id=file_id).all()

    group_sums = []
    class_sums = []
    table = []
    row_aggregation_count = 0
    for account in accounts:
        if not table:
            table.append([file_class_mapper[account.account_id // 1000]])
        else:
            if add_group_row(account, table, row_aggregation_count, group_sums):
                row_aggregation_count = 0

            add_class_row(account, table, row_aggregation_count, group_sums, class_sums)

        add_table_row(account, table)
        row_aggregation_count += 1

    add_group_result_row(table, group_sums, row_aggregation_count, table[-1][0] // 100)
    add_class_result_row(table, group_sums, class_sums)
    add_table_result_row(table, class_sums)

    return file, table
