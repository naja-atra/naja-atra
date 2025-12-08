# -*- coding: utf-8 -*-

"""
Copyright (c) 2018 Keijack Wu

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import threading
import uuid
import time

from typing import Any, Dict, List, Tuple
from threading import RLock
from ..models import HttpSession, HttpSessionFactory
from ..utils.logger import get_logger

_logger = get_logger("naja_atra.request_handlers.http_session_local_impl")

_SESSION_TIME_CLEANING_INTERVAL = 60


def _get_from_dict(adict: Dict[str, Any], key: str) -> Any:
    if key not in adict:
        return None
    try:
        return adict[key]
    except KeyError:
        _logger.debug("key %s was deleted in other thread.")
        return None


class LocalSessionHolder:

    def __init__(self):
        self.__sessions: Dict[str, HttpSession] = {}
        self.__session_lock = RLock()
        self.__started = False
        self.__clearing_thread = threading.Thread(target=self._clear_time_out_session_in_bg, daemon=True)

    def _start_cleaning(self):
        if not self.__started:
            self.__started = True
            self.__clearing_thread.start()

    def _clear_time_out_session_in_bg(self):
        while True:
            time.sleep(_SESSION_TIME_CLEANING_INTERVAL)
            self._clear_time_out_session()

    def _clear_time_out_session(self):
        timeout_sessions: List[HttpSession] = []
        for v in self.__sessions.values():
            if not v.is_valid:
                timeout_sessions.append(v)
        for session in timeout_sessions:
            session.invalidate()

    def clean_session(self, session_id: str):
        if session_id in self.__sessions:
            try:
                _logger.debug("session[#%s] is being cleaned" % session_id)
                sess = self.__sessions[session_id]
                if not sess.is_valid:
                    del self.__sessions[session_id]
            except KeyError:
                _logger.debug("Session[#%s] in session cache is already deleted. " % session_id)

    def get_session(self, session_id: str) -> HttpSession:
        if not session_id:
            return None # NOSONAR
        sess: HttpSession = _get_from_dict(self.__sessions, session_id)
        if sess and sess.is_valid:
            return sess
        else:
            return None # NOSONAR

    def cache_session(self,  session: HttpSession):
        if not session:
            return None
        sess: HttpSession = _get_from_dict(self.__sessions, session.id)

        if sess:
            if session is sess:
                return
            sess.invalidate()
        with self.__session_lock:
            self.__sessions[session.id] = session
            self._start_cleaning()

            return session


class LocalSessionImpl(HttpSession):

    def __init__(self, id: str, creation_time: float, session_holder: LocalSessionHolder):
        super().__init__()
        self.__id = id
        self.__creation_time = creation_time
        self.__last_accessed_time = creation_time
        self.__is_new = True
        self.__attr_lock = RLock()
        self.__attrs = {}
        self.__session_holder = session_holder

    @property
    def id(self) -> str:
        return self.__id

    @property
    def creation_time(self) -> float:
        return self.__creation_time

    @property
    def last_accessed_time(self) -> float:
        return self.__last_accessed_time

    @property
    def is_new(self) -> bool:
        return self.__is_new

    def _set_last_accessed_time(self, last_acessed_time: float):
        self.__last_accessed_time = last_acessed_time
        self.__is_new = False

    @property
    def attribute_names(self) -> Tuple:
        return tuple(self.__attrs.keys())

    def get_attribute(self, name: str) -> Any:
        return _get_from_dict(self.__attrs, name)

    def set_attribute(self, name: str, value: Any) -> None:
        with self.__attr_lock:
            self.__attrs[name] = value

    def invalidate(self) -> None:
        self._set_last_accessed_time(0)
        self.__session_holder.clean_session(session_id=self.id)


class LocalSessionFactory(HttpSessionFactory):

    def __init__(self):
        self.__session_holder = LocalSessionHolder()
        self.__session_lock = RLock()

    def _create_local_session(self, session_id: str) -> HttpSession:
        if session_id:
            sid = session_id
        else:
            sid = uuid.uuid4().hex
        return LocalSessionImpl(sid, time.time(), self.__session_holder)

    def get_session(self, session_id: str, create: bool = False) -> HttpSession:
        sess: LocalSessionImpl = self.__session_holder.get_session(session_id)
        if sess:
            sess._set_last_accessed_time(time.time())
            return sess
        if not create:
            return None # NOSONAR
        with self.__session_lock:
            session = self._create_local_session(session_id)
            self.__session_holder.cache_session(session)
            return session

