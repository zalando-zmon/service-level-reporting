from datetime import datetime

from app.extensions import db


class ProductGroup(db.Model):
    id = db.Column(db.Integer(), primary_key=True)

    name = db.Column(db.String(120), unique=True, nullable=False, index=True)
    department = db.Column(db.String(120), default='')

    products = db.relationship('Product', backref=db.backref('product_group', lazy='joined'), lazy='dynamic')

    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)

    username = db.Column(db.String(120), default='')
    created = db.Column(db.DateTime(), default=datetime.utcnow)
    updated = db.Column(db.DateTime(), onupdate=datetime.utcnow, default=datetime.utcnow)

    def get_owner(self):
        return self.name

    def __repr__(self):
        return '<Product group: {}>'.format(self.name)
