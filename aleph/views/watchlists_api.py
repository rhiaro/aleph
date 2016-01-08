from flask import Blueprint, request
from apikit import obj_or_404, jsonify, Pager, request_data

from aleph import authz
from aleph.model import Watchlist, db
from aleph.analyze import analyze_terms
from aleph.views.cache import etag_cache_keygen

blueprint = Blueprint('watchlists', __name__)


@blueprint.route('/api/1/watchlists', methods=['GET'])
def index():
    q = Watchlist.all(watchlist_ids=authz.watchlists(authz.READ))
    q = q.order_by(Watchlist.label.asc())
    return jsonify(Pager(q).to_dict())


@blueprint.route('/api/1/watchlists', methods=['POST', 'PUT'])
def create():
    authz.require(authz.logged_in())
    watchlist = Watchlist.create(request_data(), request.auth_role)
    db.session.commit()
    return view(watchlist.id)


@blueprint.route('/api/1/watchlists/<int:id>', methods=['GET'])
def view(id):
    authz.require(authz.watchlist_read(id))
    watchlist = obj_or_404(Watchlist.by_id(id))
    etag_cache_keygen(watchlist)
    return jsonify(watchlist)


@blueprint.route('/api/1/watchlists/<int:id>', methods=['POST', 'PUT'])
def update(id):
    authz.require(authz.watchlist_write(id))
    watchlist = obj_or_404(Watchlist.by_id(id))
    watchlist.update(request_data())
    db.session.add(watchlist)
    db.session.commit()
    return view(id)


@blueprint.route('/api/1/watchlists/<int:id>', methods=['DELETE'])
def delete(id):
    authz.require(authz.watchlist_write(id))
    watchlist = obj_or_404(Watchlist.by_id(id))
    terms = watchlist.terms
    watchlist.delete()
    db.session.commit()
    analyze_terms.delay(list(terms))
    return jsonify({'status': 'ok'})