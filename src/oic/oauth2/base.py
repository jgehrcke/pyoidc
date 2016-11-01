import copy
import logging
import requests

import six.moves.http_cookiejar as cookielib
from six.moves.http_cookies import SimpleCookie, CookieError
from oic.oauth2.exception import NonFatalException
from oic.oauth2.util import set_cookie
from oic.utils.keyio import KeyJar
from oic.utils.sanitize import sanitize

__author__ = 'roland'

logger = logging.getLogger(__name__)


class PBase(object):
    def __init__(self, ca_certs=None, verify_ssl=True, keyjar=None):

        if keyjar:
            self.keyjar = keyjar
        else:
            self.keyjar = KeyJar(verify_ssl=verify_ssl)

        self.request_args = {"allow_redirects": False}
        # self.cookies = {}
        self.cookiejar = cookielib.FileCookieJar()
        self.ca_certs = ca_certs

        if ca_certs:
            if verify_ssl is False:
                raise ValueError(
                    'conflict: ca_certs defined, but verify_ssl is False')

            # Instruct requests to verify certificate against the CA cert
            # bundle located at the path given by `ca_certs`.
            self.request_args["verify"] = ca_certs

        elif verify_ssl:
            # Instruct requests to verify server certificates against the
            # default CA bundle provided by 'certifi'. See
            # http://docs.python-requests.org/en/master/user/advanced/#ca-certificates
            self.request_args["verify"] = True

        else:
            # Instruct requests to n ot perform server cert verification.
            self.request_args["verify"] = False

        self.event_store = None
        self.req_callback = None

    def _cookies(self):
        cookie_dict = {}

        for _, a in list(self.cookiejar._cookies.items()):
            for _, b in list(a.items()):
                for cookie in list(b.values()):
                    # print cookie
                    cookie_dict[cookie.name] = cookie.value

        return cookie_dict

    def http_request(self, url, method="GET", **kwargs):
        _kwargs = copy.copy(self.request_args)
        if kwargs:
            _kwargs.update(kwargs)

        if self.cookiejar:
            _kwargs["cookies"] = self._cookies()
            logger.debug("SENT {} COOKIES".format(len(_kwargs["cookies"])))

        if self.req_callback is not None:
            _kwargs = self.req_callback(method, url, **_kwargs)

        try:
            r = requests.request(method, url, **_kwargs)
        except Exception as err:
            logger.error(
                "http_request failed: %s, url: %s, htargs: %s, method: %s" % (
                    err, url, sanitize(_kwargs), method))
            raise

        if self.event_store is not None:
            self.event_store.store('http response', r, ref=url)

        try:
            _cookie = r.headers["set-cookie"]
            # Telekom fix
            # set_cookie = set_cookie.replace(
            # "=;Path=/;Expires=Thu, 01-Jan-1970 00:00:01 GMT;HttpOnly,", "")
            logger.debug("RECEIVED COOKIE")
            try:
                set_cookie(self.cookiejar, SimpleCookie(_cookie))
            except CookieError as err:
                logger.error(err)
                raise NonFatalException(r, "{}".format(err))
        except (AttributeError, KeyError) as err:
            pass

        return r

    def send(self, url, method="GET", **kwargs):
        return self.http_request(url, method, **kwargs)

    def load_cookies_from_file(self, filename, ignore_discard=False,
                               ignore_expires=False):
        self.cookiejar.load(filename, ignore_discard, ignore_expires)

    def save_cookies_to_file(self, filename, ignore_discard=False,
                             ignore_expires=False):

        self.cookiejar.save(filename, ignore_discard, ignore_expires)
