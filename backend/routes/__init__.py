# Blueprint routes package
from .batches import batches_bp
from .video import video_bp
from .proxy import proxy_bp

__all__ = ["batches_bp", "video_bp", "proxy_bp"]
