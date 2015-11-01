from flask import session, Blueprint, redirect, request
from flask.ext.login import login_user, logout_user, current_user
from werkzeug.exceptions import BadRequest
from apikit import jsonify

from aleph import authz
from aleph.providers import PROVIDERS, Stub
from aleph.core import db, url_for
from aleph.model import User


blueprint = Blueprint('sessions', __name__)


@blueprint.route('/api/1/sessions')
def status():
    oauth_providers = {}
    for name, provider in PROVIDERS.items():
        if not isinstance(provider, Stub):
            oauth_providers[name] = url_for('.login', provider=name)

    return jsonify({
        'logged_in': authz.logged_in(),
        'api_key': current_user.api_key if authz.logged_in() else None,
        'user': current_user if authz.logged_in() else None,
        'permissions': {},
        'logins': oauth_providers,
        'logout': url_for('.logout')
    })


@blueprint.route('/api/1/sessions/logout')
def logout():
    logout_user()
    return redirect(request.args.get('next_url', url_for('ui')))


@blueprint.route('/api/1/sessions/login/<provider>')
def login(provider):
    if provider not in PROVIDERS:
        raise BadRequest('Unknown provider: %s' % provider)
    if current_user.is_authenticated():
        return redirect(url_for('ui'))
    session.clear()
    callback = url_for('.%s_authorized' % provider)
    session['next_url'] = request.args.get('next_url', url_for('ui'))
    return PROVIDERS[provider].authorize(callback=callback)


handler = PROVIDERS.get('twitter')


@blueprint.route('/api/1/sessions/callback/twitter')
@handler.authorized_handler
def twitter_authorized(resp):
    next_url = session.get('next_url', url_for('ui'))
    if resp is None or 'oauth_token' not in resp:
        return redirect(next_url)
    session['twitter_token'] = (resp['oauth_token'],
                                resp['oauth_token_secret'])
    provider = PROVIDERS.get('twitter')
    res = provider.get('users/show.json?user_id=%s' % resp.get('user_id'))
    data = {
        'display_name': res.data.get('name'),
        'twitter_id': res.data.get('id')
    }
    user = User.load(data)
    db.session.commit()
    login_user(user, remember=True)
    return redirect(next_url)


handler = PROVIDERS.get('facebook')


@blueprint.route('/api/1/sessions/callback/facebook')
@handler.authorized_handler
def facebook_authorized(resp):
    next_url = session.get('next_url', url_for('ui'))
    if resp is None or 'access_token' not in resp:
        return redirect(next_url)
    session['facebook_token'] = (resp.get('access_token'), '')
    profile = PROVIDERS.get('facebook').get('/me').data
    data = {
        'display_name': profile.get('name'),
        'email': profile.get('email'),
        'facebook_id': profile.get('id')
    }
    user = User.load(data)
    db.session.commit()
    login_user(user, remember=True)
    return redirect(next_url)


handler = PROVIDERS.get('github')


@blueprint.route('/api/1/sessions/callback/github')
@handler.authorized_handler
def github_authorized(resp):
    next_url = session.get('next_url', url_for('ui'))
    if resp is None or 'access_token' not in resp:
        return redirect(next_url)
    session['github_token'] = (resp.get('access_token'), '')
    profile = PROVIDERS.get('github').get('https://api.github.com/user').data
    data = {
        'display_name': profile.get('name'),
        'email': profile.get('email'),
        'github_id': profile.get('id')
    }
    user = User.load(data)
    db.session.commit()
    login_user(user, remember=True)
    return redirect(next_url)


handler = PROVIDERS.get('google')


@blueprint.route('/api/1/sessions/callback/google')
@handler.authorized_handler
def google_authorized(resp):
    next_url = session.get('next_url', url_for('ui'))
    if resp is None or 'access_token' not in resp:
        return redirect(next_url)
    session['google_token'] = (resp.get('access_token'), '')
    profile_url = 'https://www.googleapis.com/plus/v1/people/me'
    google = PROVIDERS.get('google')
    headers = {'Authorization': 'Bearer ' + google.get_request_token().key}
    profile = google.get(profile_url, headers=headers).data
    data = {
        'display_name': profile.get('displayName'),
        'email': profile.get('emails')[0]['value'],
        'google_id': profile.get('id')
    }
    user = User.load(data)
    db.session.commit()
    login_user(user, remember=True)
    return redirect(next_url)
