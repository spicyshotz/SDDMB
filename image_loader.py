"""
Asynchronous image loader and cache for game banner artwork.
Uses Qt's native QNetworkAccessManager for non-blocking, thread-safe network I/O
directly on the Qt event loop, completely eliminating thread-safety crashes with QPixmap.
"""

from typing import Dict, List, Tuple, Callable, Optional
from PyQt6.QtCore import QObject, QUrl
from PyQt6.QtGui import QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply


class ImageCache(QObject):
    """
    Singleton image cache and asynchronous downloader powered by QNetworkAccessManager.
    Guarantees all QPixmap operations remain on the main GUI thread.
    """
    _instance = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cache: Dict[str, QPixmap] = {}
        self._manager = QNetworkAccessManager(self)
        # url -> list of (success_callback, error_callback)
        self._subscribers: Dict[str, List[Tuple[Callable[[QPixmap], None], Optional[Callable[[], None]]]]] = {}
        # Track replies to avoid garbage collection
        self._active_replies: Dict[QNetworkReply, Tuple[str, Optional[str]]] = {}

    @classmethod
    def get_instance(cls) -> "ImageCache":
        if cls._instance is None:
            cls._instance = ImageCache()
        return cls._instance

    def get_cached(self, url: str) -> Optional[QPixmap]:
        return self._cache.get(url)

    def load_image(
        self,
        primary_url: str,
        fallback_url: Optional[str],
        callback: Callable[[QPixmap], None],
        err_callback: Optional[Callable[[], None]] = None,
    ):
        """Request an image. If cached, invokes callback immediately; otherwise downloads asynchronously."""
        if not primary_url:
            if err_callback:
                try:
                    err_callback()
                except RuntimeError:
                    pass
            return

        # Return cached pixmap immediately if available
        if primary_url in self._cache:
            try:
                callback(self._cache[primary_url])
            except RuntimeError:
                pass
            return

        # If already downloading this URL, register this subscriber
        if primary_url in self._subscribers:
            self._subscribers[primary_url].append((callback, err_callback))
            return

        self._subscribers[primary_url] = [(callback, err_callback)]
        self._start_download(primary_url, fallback_url)

    def _start_download(self, url: str, fallback_url: Optional[str]):
        req = QNetworkRequest(QUrl(url))
        req.setHeader(
            QNetworkRequest.KnownHeaders.UserAgentHeader,
            "SteamSearchDesktop/1.0 (Windows NT 10.0; Win64; x64)",
        )
        req.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy,
        )

        reply = self._manager.get(req)
        self._active_replies[reply] = (url, fallback_url)
        reply.finished.connect(lambda: self._on_reply_finished(reply))

    def _on_reply_finished(self, reply: QNetworkReply):
        if reply not in self._active_replies:
            reply.deleteLater()
            return

        primary_url, fallback_url = self._active_replies.pop(reply)
        error = reply.error()
        status_code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)

        data = reply.readAll()
        reply.deleteLater()

        success = False
        if error == QNetworkReply.NetworkError.NoError and (status_code is None or status_code == 200) and not data.isEmpty():
            pixmap = QPixmap()
            if pixmap.loadFromData(data) and not pixmap.isNull():
                self._cache[primary_url] = pixmap
                subscribers = self._subscribers.pop(primary_url, [])
                for cb, _ in subscribers:
                    try:
                        cb(pixmap)
                    except RuntimeError:
                        # Widget was destroyed while downloading
                        pass
                success = True

        if not success:
            # If primary URL failed and fallback URL exists and isn't tried yet
            if fallback_url and fallback_url != primary_url:
                self._start_download_fallback(primary_url, fallback_url)
            else:
                subscribers = self._subscribers.pop(primary_url, [])
                for _, err_cb in subscribers:
                    if err_cb:
                        try:
                            err_cb()
                        except RuntimeError:
                            pass

    def _start_download_fallback(self, original_key: str, fallback_url: str):
        req = QNetworkRequest(QUrl(fallback_url))
        req.setHeader(
            QNetworkRequest.KnownHeaders.UserAgentHeader,
            "SteamSearchDesktop/1.0 (Windows NT 10.0; Win64; x64)",
        )
        req.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy,
        )

        reply = self._manager.get(req)

        def on_fallback_finished():
            data = reply.readAll()
            status_code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            err = reply.error()
            reply.deleteLater()

            pixmap = QPixmap()
            if err == QNetworkReply.NetworkError.NoError and (status_code is None or status_code == 200) and not data.isEmpty() and pixmap.loadFromData(data):
                self._cache[original_key] = pixmap
                subscribers = self._subscribers.pop(original_key, [])
                for cb, _ in subscribers:
                    try:
                        cb(pixmap)
                    except RuntimeError:
                        pass
            else:
                subscribers = self._subscribers.pop(original_key, [])
                for _, err_cb in subscribers:
                    if err_cb:
                        try:
                            err_cb()
                        except RuntimeError:
                            pass

        reply.finished.connect(on_fallback_finished)
