import gc
import os
import tracemalloc
from collections import Counter
from typing import Dict

import objgraph
from fastapi import APIRouter, Query

router = APIRouter()
snapshots = []


def is_project_file(filename: str) -> bool:
    project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return filename.startswith(project_dir) and ".venv" not in filename


def get_object_types() -> Dict[str, int]:
    type_counts = Counter(type(o).__name__ for o in gc.get_objects())
    return dict(type_counts.most_common(10))


def get_object_details():
    details = []
    for typename in objgraph.most_common_types(10):
        objects = objgraph.by_type(typename)
        sample_refs = []
        for obj in objects[:3]:  # Look at first 3 objects of each type
            refs = objgraph.find_backref_chain(
                obj, objgraph.is_proper_module, max_depth=3
            )
            if refs:
                ref_chain = " -> ".join(str(type(r).__name__) for r in refs)
                sample_refs.append(ref_chain)

        details.append(
            {"type": typename, "count": len(objects), "sample_referrers": sample_refs}
        )
    return details


@router.get("/clean")
async def clean_memory():
    gc.collect()
    return {"message": "Memory cleaned"}


@router.get("")
async def get_memory_snapshot(onlykeep: bool = Query(False)):
    snapshot = tracemalloc.take_snapshot()
    stats = snapshot.statistics("lineno")

    if onlykeep:
        stats = [stat for stat in stats if is_project_file(stat.traceback[0].filename)]

    snapshots.append(snapshot)
    current, peak = tracemalloc.get_traced_memory()

    return {
        "pid": os.getpid(),
        "current_memory": current,
        "peak_memory": peak,
        "object_types": get_object_types(),
        "top_memory_usage": [
            {
                "filename": (
                    os.path.relpath(stat.traceback[0].filename)
                    if onlykeep
                    else stat.traceback[0].filename
                ),
                "line": stat.traceback[0].lineno,
                "size": stat.size,
                "count": stat.count,
            }
            for stat in stats[:100]
        ],
    }


@router.get("/memory-full")
async def get_full_memory():
    import psutil

    process = psutil.Process()
    memory_info = process.memory_info()

    return {
        "rss": memory_info.rss,
        "vms": memory_info.vms,
        "shared": memory_info.shared,
        "text": memory_info.text,
        "lib": memory_info.lib,
        "data": memory_info.data,
        "dirty": memory_info.dirty,
        "tracemalloc": tracemalloc.get_traced_memory(),
        "python_objects": get_object_types(),
    }


@router.get("/memory-objects")
async def get_memory_objects():
    import gc
    import sys

    objects = gc.get_objects()
    stats = {}

    for obj in objects:
        obj_type = type(obj).__name__
        if obj_type not in stats:
            stats[obj_type] = {"count": 0, "size": 0}
        stats[obj_type]["count"] += 1
        stats[obj_type]["size"] += sys.getsizeof(obj)

    return {
        "object_stats": sorted(stats.items(), key=lambda x: x[1]["size"], reverse=True)[
            :50
        ]
    }


@router.get("/memory-detail")
async def get_memory_detail():
    import gc
    import inspect
    import sys
    from collections import deque
    from types import FrameType

    from pydantic.fields import ModelField

    MAX_OBJECTS_TO_PROCESS = 10000
    MAX_REFERRERS_TO_CHECK = 20

    def get_object_sample(obj, max_items=3):
        """Safely get a sample of the object's contents"""
        try:
            if isinstance(obj, (dict, set, list, deque)):
                items = list(obj)[:max_items]
                return [str(item)[:100] for item in items]
            return None
        except Exception:
            return None

    def get_detailed_info(obj):
        try:
            if isinstance(obj, ModelField):
                return {
                    "name": obj.name,
                    "model": obj.model.__name__ if hasattr(obj, "model") else "unknown",
                    "type": str(obj.type_) if hasattr(obj, "type_") else "unknown",
                }
            elif isinstance(obj, deque):
                return {
                    "length": len(obj),
                    "maxlen": obj.maxlen,
                    "sample": get_object_sample(obj),
                }
            elif isinstance(obj, dict):
                return {
                    "keys": get_object_sample(obj.keys()),
                    "value_types": [type(v).__name__ for v in list(obj.values())[:3]],
                }
            elif isinstance(obj, set):
                return {"sample": get_object_sample(obj)}
            elif isinstance(obj, type):
                return {
                    "name": obj.__name__,
                    "module": (
                        obj.__module__ if hasattr(obj, "__module__") else "unknown"
                    ),
                }
            elif inspect.isfunction(obj):
                return {
                    "name": obj.__name__,
                    "module": obj.__module__,
                    "file": obj.__code__.co_filename,
                    "line": obj.__code__.co_firstlineno,
                }
            return None
        except Exception as e:
            return f"Error: {str(e)}"

    def get_referrer_info(referrers, obj):
        locations = []
        for ref in referrers[:MAX_REFERRERS_TO_CHECK]:
            try:
                if isinstance(ref, dict):
                    # Try to get the actual key if the object is a value
                    for k, v in list(ref.items())[:5]:  # Check first 5 items
                        if v is obj:
                            locations.append(f"dict[{str(k)[:50]}]")
                        elif k is obj:
                            locations.append(f"dict_key[{str(v)[:50]}]")
                elif isinstance(ref, FrameType):
                    # Get more frame details
                    locations.append(
                        f"frame:{ref.f_code.co_name}:{os.path.basename(ref.f_code.co_filename)}"
                    )
                elif inspect.isclass(ref):
                    # Try to find the attribute name
                    for name, value in inspect.getmembers(ref):
                        if value is obj:
                            locations.append(f"class:{ref.__name__}.{name}")
                            break
                    else:
                        locations.append(f"class:{ref.__name__}")
                elif inspect.ismodule(ref):
                    locations.append(f"module:{ref.__name__}")
                elif isinstance(ref, (list, deque)):
                    # Try to get the index
                    try:
                        if isinstance(ref, list):
                            idx = ref.index(obj)
                            locations.append(f"list[{idx}]")
                        else:
                            locations.append(f"deque(len={len(ref)})")
                    except ValueError:
                        locations.append(
                            f"{'list' if isinstance(ref, list) else 'deque'}"
                        )
            except Exception:
                continue
            if len(locations) >= 5:
                break
        return locations

    # Get all objects and group by type
    type_stats = {}
    objects = gc.get_objects()[:MAX_OBJECTS_TO_PROCESS]

    for obj in objects:
        try:
            obj_type = type(obj).__name__
            if obj_type not in type_stats:
                type_stats[obj_type] = {"count": 0, "total_size": 0, "samples": []}

            size = sys.getsizeof(obj)
            type_stats[obj_type]["count"] += 1
            type_stats[obj_type]["total_size"] += size

            # Only get detailed info for large objects
            if size > 1000:
                info = {
                    "size": size,
                    "len": len(obj) if hasattr(obj, "__len__") else None,
                    "locations": get_referrer_info(gc.get_referrers(obj), obj),
                    "details": get_detailed_info(obj),
                }

                if len(type_stats[obj_type]["samples"]) < 5:
                    type_stats[obj_type]["samples"].append(info)
                else:
                    smallest = min(
                        type_stats[obj_type]["samples"], key=lambda x: x["size"]
                    )
                    if info["size"] > smallest["size"]:
                        type_stats[obj_type]["samples"].remove(smallest)
                        type_stats[obj_type]["samples"].append(info)
        except Exception:
            continue

    # Sort by total size and return top users
    sorted_stats = sorted(
        type_stats.items(), key=lambda x: x[1]["total_size"], reverse=True
    )

    return {
        "note": f"Limited to {MAX_OBJECTS_TO_PROCESS} objects for performance",
        "type_stats": [
            {
                "type": type_name,
                "count": stats["count"],
                "total_size": stats["total_size"],
                "largest_instances": sorted(
                    stats["samples"], key=lambda x: x["size"], reverse=True
                ),
            }
            for type_name, stats in sorted_stats[:20]
        ],
    }


@router.get("/memory-leaks")
async def get_memory_leaks():
    import gc
    import threading
    from types import FunctionType

    def get_function_info(func):
        try:
            return {
                "name": func.__name__,
                "module": func.__module__,
                "file": func.__code__.co_filename,
                "line": func.__code__.co_firstlineno,
                "closure": bool(func.__closure__),
                "defaults": bool(func.__defaults__),
            }
        except Exception as e:
            return f"Error: {str(e)}"

    # Track thread information
    thread_info = {}
    try:
        for thread in threading.enumerate():
            thread_info[thread.name] = {
                "alive": thread.is_alive(),
                "daemon": thread.daemon,
                "ident": thread.ident,
            }
    except Exception as e:
        thread_info["error"] = str(e)

    # Track pattern objects (regex)
    pattern_count = {}
    for obj in gc.get_objects():
        if type(obj).__name__ == "Pattern":
            try:
                pattern = str(obj.pattern)[:100]  # Limit pattern length
                if pattern not in pattern_count:
                    pattern_count[pattern] = 0
                pattern_count[pattern] += 1
            except Exception:
                continue

    # Track function creation points
    function_sources = {}
    for obj in gc.get_objects():
        if isinstance(obj, FunctionType):
            try:
                key = f"{obj.__code__.co_filename}:{obj.__code__.co_firstlineno}"
                if key not in function_sources:
                    function_sources[key] = {
                        "count": 0,
                        "sample": get_function_info(obj),
                    }
                function_sources[key]["count"] += 1
            except Exception:
                continue

    # Get the top entries by count
    top_patterns = dict(
        sorted(pattern_count.items(), key=lambda x: x[1], reverse=True)[:10]
    )

    top_functions = dict(
        sorted(function_sources.items(), key=lambda x: x[1]["count"], reverse=True)[:10]
    )

    return {
        "threads": {"active_count": threading.active_count(), "threads": thread_info},
        "patterns": {"total_count": len(pattern_count), "most_common": top_patterns},
        "functions": {"total_count": len(function_sources), "hotspots": top_functions},
    }


@router.get("/sqlalchemy-stats")
async def get_sqlalchemy_stats():
    import gc

    from sqlalchemy.engine import Connection
    from sqlalchemy.engine.base import Engine
    from sqlalchemy.orm import Session, sessionmaker
    from sqlalchemy.pool import _ConnectionFairy

    stats = {
        "engines": [],
        "active_connections": [],
        "sessions": [],
        "connection_pools": [],
    }

    # Track all engine instances
    for obj in gc.get_objects():
        try:
            if isinstance(obj, Engine):
                pool = obj.pool
                stats["engines"].append(
                    {
                        "name": str(obj.url),
                        "pool_size": pool.size(),
                        "checked_out": pool.checkedin(),
                        "overflow": pool.overflow(),
                        "checkedout": pool.checkedout(),
                    }
                )

                # Track pool status
                stats["connection_pools"].append(
                    {
                        "url": str(obj.url),
                        "size": pool.size(),
                        "checked_in": pool.checkedin(),
                        "checked_out": pool.checkedout(),
                        "overflow": pool.overflow(),
                    }
                )

            # Track active connections
            elif isinstance(obj, (_ConnectionFairy, Connection)):
                try:
                    info = {
                        "hash": id(obj),
                        "closed": obj.closed,
                    }
                    if hasattr(obj, "_connection_record"):
                        info["connection_record"] = id(obj._connection_record)
                    stats["active_connections"].append(info)
                except Exception:
                    continue

            # Track sessions
            elif isinstance(obj, Session):
                try:
                    info = {
                        "hash": id(obj),
                        "active": not obj.closed,
                        "dirty": len(obj.dirty),
                        "new": len(obj.new),
                        "deleted": len(obj.deleted),
                        "transaction_parent": bool(obj._transaction),
                    }
                    if hasattr(obj, "info"):
                        info["info"] = str(obj.info)
                    stats["sessions"].append(info)
                except Exception:
                    continue

            # Track sessionmaker factories
            elif isinstance(obj, sessionmaker):
                try:
                    stats["sessions"].append(
                        {"type": "sessionmaker", "hash": id(obj), "kw": str(obj.kw)}
                    )
                except Exception:
                    continue

        except Exception:
            continue

    # Add summary
    stats["summary"] = {
        "total_engines": len(stats["engines"]),
        "total_active_connections": len(stats["active_connections"]),
        "total_sessions": len(stats["sessions"]),
        "total_pools": len(stats["connection_pools"]),
    }

    return stats


@router.get("/debug/tracemalloc/snapshot", summary="Show top X memory allocations")
def tracemalloc_snapshot(count: int = Query(10)):
    import tracemalloc

    snapshot = tracemalloc.take_snapshot()

    # Ignore <frozen importlib._bootstrap> and <unknown> files
    snapshot = snapshot.filter_traces(
        (
            tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
            tracemalloc.Filter(False, "<unknown>"),
        )
    )
    top_stats = snapshot.statistics("lineno")
    return {"stats": [str(stat) for stat in top_stats[:count]]}


@router.get("/memory-all")
async def get_all_memory():
    import gc
    import os
    import sys
    import tracemalloc
    from collections import defaultdict

    import psutil

    def format_size(size):
        """Format size in bytes to human readable format"""
        for unit in ["B", "KB", "MB", "GB"]:
            if abs(size) < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} GB"

    def parse_size(size_str):
        """Convert size string back to bytes for sorting"""
        value, unit = size_str.split()
        value = float(value)
        if unit == "KB":
            return value * 1024
        elif unit == "MB":
            return value * 1024 * 1024
        elif unit == "GB":
            return value * 1024 * 1024 * 1024
        return value

    def get_size_of_objects(objs):
        """Recursively get size of objects and their contents"""
        seen = set()

        def inner(obj):
            obj_id = id(obj)
            if obj_id in seen:
                return 0
            seen.add(obj_id)
            size = sys.getsizeof(obj)

            if isinstance(obj, dict):
                size += sum(inner(k) + inner(v) for k, v in obj.items())
            elif isinstance(obj, (list, tuple, set, frozenset)):
                size += sum(inner(i) for i in obj)
            return size

        return sum(inner(obj) for obj in objs)

    # Get process memory info
    process = psutil.Process()
    memory_info = process.memory_info()

    # Get tracemalloc statistics
    snapshot = tracemalloc.take_snapshot()
    stats_by_file = defaultdict(
        lambda: {
            "size": 0,
            "count": 0,
            "lines": defaultdict(lambda: {"size": 0, "count": 0}),
        }
    )

    for stat in snapshot.statistics("lineno"):
        frame = stat.traceback[0]
        filename = frame.filename
        lineno = frame.lineno

        stats_by_file[filename]["size"] += stat.size
        stats_by_file[filename]["count"] += stat.count
        stats_by_file[filename]["lines"][lineno]["size"] += stat.size
        stats_by_file[filename]["lines"][lineno]["count"] += stat.count

    # Get object statistics by type
    type_stats = defaultdict(
        lambda: {"count": 0, "size": 0, "total_size": 0, "examples": []}
    )
    for obj in gc.get_objects():
        try:
            obj_type = type(obj).__name__
            size = sys.getsizeof(obj)
            total_size = get_size_of_objects([obj])

            type_stats[obj_type]["count"] += 1
            type_stats[obj_type]["size"] += size
            type_stats[obj_type]["total_size"] += total_size

            # Store examples of large objects
            if total_size > 1000000:  # Objects larger than 1MB
                try:
                    if (
                        len(type_stats[obj_type]["examples"]) < 3
                    ):  # Keep up to 3 examples
                        sample = {
                            "size": format_size(total_size),
                            "referrers": [
                                type(r).__name__ for r in gc.get_referrers(obj)[:5]
                            ],
                        }
                        if hasattr(obj, "__len__"):
                            sample["length"] = len(obj)
                        if isinstance(obj, dict):
                            sample["sample_keys"] = list(obj.keys())[:5]
                        type_stats[obj_type]["examples"].append(sample)
                except Exception:
                    pass

        except Exception:
            continue

    # Get memory maps for external libraries
    maps = []
    try:
        with open(f"/proc/{os.getpid()}/maps") as f:
            for line in f:
                fields = line.split()
                if len(fields) >= 6:
                    start, end = fields[0].split("-")
                    size = int(end, 16) - int(start, 16)
                    if size > 1000000:  # Only show segments larger than 1MB
                        maps.append(
                            {
                                "address": fields[0],
                                "perms": fields[1],
                                "size": format_size(size),
                                "path": fields[-1] if len(fields) > 5 else "anonymous",
                            }
                        )
    except Exception:
        pass

    return {
        "process": {
            "rss": format_size(memory_info.rss),
            "vms": format_size(memory_info.vms),
            "data": format_size(memory_info.data),
            "text": (
                format_size(memory_info.text) if hasattr(memory_info, "text") else "N/A"
            ),
            "python_tracked": format_size(tracemalloc.get_traced_memory()[0]),
            "python_peak": format_size(tracemalloc.get_traced_memory()[1]),
        },
        "tracemalloc": {
            "top_files": sorted(
                [
                    {
                        "file": filename,
                        "size": format_size(stats["size"]),
                        "count": stats["count"],
                        "top_lines": sorted(
                            [
                                {
                                    "line": lineno,
                                    "size": format_size(line_stat["size"]),
                                    "count": line_stat["count"],
                                }
                                for lineno, line_stat in stats["lines"].items()
                            ],
                            key=lambda x: parse_size(x["size"]),
                            reverse=True,
                        )[
                            :5
                        ],  # Top 5 lines per file
                    }
                    for filename, stats in stats_by_file.items()
                ],
                key=lambda x: parse_size(x["size"]),
                reverse=True,
            )[
                :20
            ]  # Top 20 files
        },
        "objects": {
            "by_type": sorted(
                [
                    {
                        "type": type_name,
                        "count": stats["count"],
                        "size": format_size(stats["size"]),
                        "total_size": format_size(stats["total_size"]),
                        "examples": stats["examples"],
                    }
                    for type_name, stats in type_stats.items()
                    if stats["total_size"]
                    > 1000000  # Only show types using more than 1MB
                ],
                key=lambda x: parse_size(x["total_size"]),
                reverse=True,
            )
        },
        "memory_maps": maps,
    }


@router.get("/db-stats")
async def get_db_stats():
    import gc

    from sqlalchemy.engine import Engine

    stats = {"connections": [], "sessions": [], "pools": []}

    for obj in gc.get_objects():
        if isinstance(obj, Engine):
            pool = obj.pool
            stats["pools"].append(
                {
                    "url": str(obj.url),
                    "size": pool.size(),
                    "overflow": pool.overflow(),
                    "checked_out": pool.checkedout(),
                }
            )
        elif str(type(obj).__name__) == "Session":
            try:
                stats["sessions"].append(
                    {
                        "active": not obj.closed,
                        "dirty": len(obj.dirty),
                        "new": len(obj.new),
                        "identity_map": len(obj._identity_map),
                    }
                )
            except Exception:
                continue

    return stats


@router.get("/collection-deep-analysis")
async def analyze_collections_deep():
    import gc
    import inspect
    import sys
    from types import ModuleType

    def get_type_with_module(obj):
        t = type(obj)
        return (
            f"{t.__module__}.{t.__name__}" if hasattr(t, "__module__") else t.__name__
        )

    def is_pydantic_related(obj):
        """Check if object is related to pydantic"""
        if isinstance(obj, ModuleType):
            return "pydantic" in obj.__name__
        t = type(obj)
        return "pydantic" in (t.__module__ or "")

    collections = {"large_dicts": [], "large_tuples": []}

    for obj in gc.get_objects():
        try:
            if not isinstance(obj, (dict, tuple)):
                continue

            size = sys.getsizeof(obj)
            if size < 100000:  # Skip small objects
                continue

            # Get the owners (referrers) with more detail
            referrers = gc.get_referrers(obj)
            referrer_info = []
            for ref in referrers[:5]:
                info = {
                    "type": get_type_with_module(ref),
                    "is_pydantic": is_pydantic_related(ref),
                }

                # For modules, get the name
                if isinstance(ref, ModuleType):
                    info["module_name"] = ref.__name__

                # For functions, get location
                if inspect.isfunction(ref):
                    info["function_name"] = ref.__name__
                    info["function_file"] = ref.__code__.co_filename

                # For classes, get the class name
                if inspect.isclass(ref):
                    info["class_name"] = ref.__name__

                referrer_info.append(info)

            # Get content samples with types
            content_info = None
            if isinstance(obj, dict):
                sample = []
                for k, v in list(obj.items())[:5]:
                    sample.append(
                        {
                            "key": str(k)[:50],
                            "key_type": get_type_with_module(k),
                            "value_type": get_type_with_module(v),
                            "is_pydantic_key": is_pydantic_related(k),
                            "is_pydantic_value": is_pydantic_related(v),
                        }
                    )
                content_info = sample
            elif isinstance(obj, tuple):
                sample = []
                for item in obj[:5]:
                    sample.append(
                        {
                            "type": get_type_with_module(item),
                            "is_pydantic": is_pydantic_related(item),
                        }
                    )
                content_info = sample

            info = {
                "size": size,
                "length": len(obj),
                "sample_content": content_info,
                "referrers": referrer_info,
            }

            if isinstance(obj, dict):
                collections["large_dicts"].append(info)
            else:
                collections["large_tuples"].append(info)

        except Exception:
            continue

    return {
        "large_dicts": sorted(
            collections["large_dicts"], key=lambda x: x["size"], reverse=True
        )[:20],
        "large_tuples": sorted(
            collections["large_tuples"], key=lambda x: x["size"], reverse=True
        )[:20],
    }
