import dataclasses
from datetime import datetime

from sqlalchemy import false

from app.extensions import db


class Indicator(db.Model):
    id = db.Column(db.Integer(), primary_key=True)

    name = db.Column(db.String(120), nullable=False, index=True)
    source = db.Column(db.JSON(), nullable=False)
    unit = db.Column(db.String(20), nullable=False, default='')
    aggregation = db.Column(db.String(80), default='average')
    is_deleted = db.Column(
        db.Boolean(), default=False, index=True, server_default=false()
    )

    product_id = db.Column(
        db.Integer(), db.ForeignKey('product.id'), nullable=False, index=True
    )

    slug = db.Column(db.String(120), nullable=False, index=True)

    targets = db.relationship(
        'Target', backref=db.backref('indicator', lazy='joined'), lazy='dynamic'
    )
    values = db.relationship(
        'IndicatorValue', backref='indicator', lazy='dynamic', passive_deletes=True
    )

    username = db.Column(db.String(120), default='')
    created = db.Column(db.DateTime(), default=datetime.utcnow)
    updated = db.Column(
        db.DateTime(), onupdate=datetime.utcnow, default=datetime.utcnow
    )

    __table_args__ = (
        db.UniqueConstraint(
            'name', 'product_id', 'is_deleted', name='indicator_name_product_id_key'
        ),
    )

    def get_owner(self):
        return self.product.product_group.name

    def __repr__(self):
        return '<SLI {} | {} | {}>'.format(self.product.name, self.name, self.source)
