from app.extensions import db


class Authorization:
    """Default ALLOW ALL authorization"""

    def read(self, obj: db.Model, **kwargs):
        return

    def create(self, obj: db.Model, **kwargs):
        return

    def update(self, obj: db.Model, **kwargs):
        return

    def delete(self, obj: db.Model, **kwargs):
        return
