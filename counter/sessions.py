import logging
import uuid
import json
import sys
import flask
from flask import jsonify
from collections import OrderedDict
from flask.sessions import SessionInterface, SessionMixin
from werkzeug.datastructures import CallbackDict
import requests


class SessionStore:

    def __init__(self, logger=None):
        if logger is None:
            self.logger = logging.getLogger("__name__")
        else:
            self.logger = logger

    def set_key(self, key, value):
        self.logger.debug("set_key('%s', '%s')", key, value)
        data = { key: value }
        newHeaders = {'Content-type': 'application/json', 'Accept': 'text/plain'}
        try:
            response = requests.post(self.url, json=data, headers=newHeaders)
        except requests.exceptions.RequestException as e:
            return flask.json.jsonify({
                'url': self.url,
                'exception': type(e).__name__,
            }), 503
        return response.content

    
    def get_key(self, key):
        try:
            response = requests.get(self.url +key)
        except requests.exceptions.RequestException as e:
            return flask.json.jsonify({
                'url': self.url,
                'exception': type(e).__name__,
            }), 503
        return response.json().get(key)

    
    def delete_key(self, key):
        self.logger.debug("delete_key('%s')", key)
        try:
            url = self.url +key
            response = requests.delete(url)
        except requests.exceptions.RequestException as e:
            return flask.json.jsonify({
                'url': self.url,
                'exception': type(e).__name__,
            }), 503
        return response
    
def remove_item(d, k, v):
    if k in d:
        if d[k].casefold() == v.casefold():
            del d[k]
    return dict(d)


class KeyValueSessionStore(SessionStore):

    def __init__(self, url, logger=None):
        super().__init__(logger)
        self.url = url + '/'


class ServerSideSession(CallbackDict, SessionMixin):

    def __init__(self, initial=None, sid=None):

        def on_update(self):
            self.modified = True

        CallbackDict.__init__(self, initial, on_update)
        self.sid = sid
        self.modified = False


class ServerSideSessionInterface(SessionInterface):

    def __init__(self, session_store):
        self.session_store = session_store

    def _update_session(self, app, session, response):
        self.session_store.set_key(session.sid, dict(session))
        response.set_cookie(
            app.session_cookie_name,
            session.sid,
            expires=self.get_expiration_time(app, session),
            httponly=self.get_cookie_httponly(app),
            domain=self.get_cookie_domain(app),
            path=self.get_cookie_path(app),
            secure=self.get_cookie_secure(app)
        )

    def _delete_session(self, app, response, sid):
        response.delete_cookie(
            app.session_cookie_name,
            domain=self.get_cookie_domain(app),
            path=self.get_cookie_path(app)
        )
        self.session_store.delete_key(sid)

    def open_session(self, app, request):
        sid = request.cookies.get(app.session_cookie_name)
        if not sid:
            # Create a session object with a new session id
            sid = str(uuid.uuid4())
            return ServerSideSession(sid=sid)

        data = self.session_store.get_key(sid)
        if data:
            # Create a session object with existing data
            app.logger.debug(data)
            return ServerSideSession(data, sid=sid)

        # create an empty session object
        return ServerSideSession(sid=sid)

    def save_session(self, app, session, response):

        if not session:
            if session.modified:
                self._delete_session(app, response, session.sid)
            return

        if self.should_set_cookie(app, session):
            self._update_session(app, session, response)
