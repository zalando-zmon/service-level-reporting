from flask import jsonify, make_response


def rate_limit_exceeded(e):
    return make_response(jsonify(title='Rate limit exceeded', detail='Rate limit exceeded. Too many requests'), 429)
