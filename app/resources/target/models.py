from datetime import datetime

from app.extensions import db


class Target(db.Model):
    id = db.Column(db.Integer(), primary_key=True)

    target_from = db.Column(db.Float(), nullable=True)
    target_to = db.Column(db.Float(), nullable=True)

    indicator_id = db.Column(db.Integer(), db.ForeignKey('indicator.id'), nullable=False)
    objective_id = db.Column(db.Integer(), db.ForeignKey('objective.id'), nullable=False)

    username = db.Column(db.String(120), default='')
    created = db.Column(db.DateTime(), default=datetime.utcnow)
    updated = db.Column(db.DateTime(), onupdate=datetime.utcnow, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('indicator_id', 'objective_id', name='target_indicator_id_objective_id_key'),
    )

    def get_owner(self):
        return self.objective.product.product_group.name

    def __repr__(self):
        return '<Target {} | {} - {}>'.format(self.objective.product.name, self.target_from, self.target_to)
