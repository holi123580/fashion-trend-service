"""采集适配器包"""
from adapters.base import BaseAdapter, FetchResult
from adapters.rss import RSSAdapter
from adapters.apify import ApifyAdapter

__all__ = ["BaseAdapter", "FetchResult", "RSSAdapter", "ApifyAdapter"]
