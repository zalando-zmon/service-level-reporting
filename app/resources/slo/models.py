from datetime import datetime

from app.extensions import db


class Objective(db.Model):
    id = db.Column(db.Integer(), primary_key=True)

    title = db.Column(db.Text(), nullable=False)
    description = db.Column(db.Text(), default='')

    product_id = db.Column(db.Integer(), db.ForeignKey('product.id', ondelete='CASCADE'))

    targets = db.relationship(
        'Target', backref=db.backref('objective', lazy='joined'), passive_deletes=True)

    username = db.Column(db.String(120), default='')
    created = db.Column(db.DateTime(), default=datetime.utcnow)
    updated = db.Column(db.DateTime(), onupdate=datetime.utcnow, default=datetime.utcnow)

    def get_owner(self):
        return self.product.product_group.name

    def __repr__(self):
        return '<SLO {} | {}>'.format(self.product.name, self.title)
