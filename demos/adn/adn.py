#!/usr/bin/env python
#
# Copyright 2009 Facebook
# Copyright 2013 Johnnie Pittman
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import os.path
import tornado.auth
import tornado.escape
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web

from tornado.options import define, options

from pdb import set_trace as st
import logging

define("config", help="File for configuration options. For testing.",
      default="adn.conf")
define("port", default=8888, help="run on the given port", type=int)
define("adn_api_key", help="your App.Net application API client id key",
      default="__TODO:_ADD_YOUR_APP_NET_CLIENT_ID_HERE__")
define("adn_secret", help="your App.Net application secret",
      default="__TODO:_ADD_YOUR_APP_NET_CLIENT_SECRET_HERE__")


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler),
            (r"/auth/login", AuthLoginHandler),
            (r"/auth/logout", AuthLogoutHandler),
        ]
        settings = dict(
            cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
            login_url="/auth/login",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
            adn_api_key=options.adn_api_key,
            adn_secret=options.adn_secret,
            ui_modules={"Post": PostModule},
            debug=True,
            autoescape=None,
        )
        tornado.web.Application.__init__(self, handlers, **settings)


class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        user_json = self.get_secure_cookie("user")
        if not user_json: return None
        return tornado.escape.json_decode(user_json)


class MainHandler(BaseHandler, tornado.auth.ADNMixin):
    @tornado.web.authenticated
    @tornado.web.asynchronous
    def get(self):
        self.adn_request("/stream/0/posts/stream/global", self._on_stream,
                         access_token=self.current_user["access_token"])

    def _on_stream(self, stream):
        if stream is None:
            # Session may have expired
            self.redirect("/auth/login")
            return
        self.render("stream.html", stream=stream)


class AuthLoginHandler(BaseHandler, tornado.auth.ADNMixin):
    @tornado.web.asynchronous
    def get(self):
        my_url = (self.request.protocol + "://" + self.request.host +
                  "/auth/login?next=" +
                  tornado.escape.url_escape(self.get_argument("next", "/")))
        if self.get_argument("code", False):
            logging.warning("got code.")
            self.get_authenticated_user(
                redirect_uri=my_url,
                client_id=self.settings["adn_api_key"],
                client_secret=self.settings["adn_secret"],
                code=self.get_argument("code"),
                callback=self._on_auth)
            return
        logging.warning("auth redirect")
        self.authorize_redirect(redirect_uri=my_url,
                                client_id=self.settings["adn_api_key"],
                                extra_params={"scope": "basic,stream"})
    
    def _on_auth(self, user):
        if not user:
            raise tornado.web.HTTPError(500, "App.Net auth failed")
        self.set_secure_cookie("user", tornado.escape.json_encode(user))
        self.redirect(self.get_argument("next", "/"))


class AuthLogoutHandler(BaseHandler, tornado.auth.ADNMixin):
    def get(self):
        self.clear_cookie("user")
        self.redirect(self.get_argument("next", "/"))


class PostModule(tornado.web.UIModule):
    def render(self, post):
        return self.render_string("modules/post.html", post=post)


def main():
    tornado.options.parse_config_file(options.config)
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
