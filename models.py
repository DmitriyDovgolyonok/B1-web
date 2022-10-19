from sqlalchemy import UniqueConstraint

from app import db

"""
Models for DB
"""
class AccountData(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    active = db.Column(db.Numeric(30, 10), nullable=False)
    passive = db.Column(db.Numeric(30, 10), nullable=False)

    def repr(self):
        return '<AccountData %r>' % self.name


class FileInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    file_name = db.Column(db.String(255), nullable=False)
    date_created = db.Column(db.DateTime, nullable=False)
    bank_name = db.Column(db.String(80), nullable=False)
    pub_date = db.Column(db.DateTime, nullable=False)

    __table_args__ = (UniqueConstraint('bank_name', 'pub_date', name='_bank_name_pub_date_uc'),)

    def repr(self):
        return '<FileInfo %r>' % self.name


class BankAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    account_id = db.Column(db.Integer, nullable=False)

    file_info_id = db.Column(db.Integer, db.ForeignKey(FileInfo.id), nullable=False)

    opening_balance_id = db.Column(db.Integer, db.ForeignKey(AccountData.id, ondelete='cascade'), nullable=False)
    opening_balance = db.relationship(AccountData, backref="opening_balances", foreign_keys=[opening_balance_id],
                                      lazy='joined')

    turnover_id = db.Column(db.Integer, db.ForeignKey(AccountData.id, ondelete='cascade'), nullable=False)
    turnover = db.relationship(AccountData, backref="turnovers", foreign_keys=[turnover_id], lazy='joined')

    def repr(self):
        return '<BankAccount %r>' % self.title
