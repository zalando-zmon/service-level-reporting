from datetime import datetime

from app.extensions import db


class Product(db.Model):
    id = db.Column(db.Integer(), primary_key=True)

    name = db.Column(db.String(120), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), nullable=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)

    product_group_id = db.Column(db.Integer(), db.ForeignKey('product_group.id'), nullable=False)

    objectives = db.relationship(
        'Objective', backref=db.backref('product', lazy='joined'), lazy='dynamic', cascade='all, delete')
    indicators = db.relationship(
        'Indicator', backref=db.backref('product', lazy='joined'), lazy='dynamic', cascade='all, delete')

    username = db.Column(db.String(120), default='')
    created = db.Column(db.DateTime(), default=datetime.utcnow)
    updated = db.Column(db.DateTime(), onupdate=datetime.utcnow, default=datetime.utcnow)

    def get_owner(self):
        return self.product_group.name

    def __repr__(self):
        return '<Product {}>'.format(self.name)
