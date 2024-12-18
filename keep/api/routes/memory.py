import gc
import os
import subprocess
import sys
import tracemalloc
import uuid
from collections import Counter
from typing import Dict

import objgraph
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from keep.api.memory_tracker import memory_tracker

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
            for stat in stats[:10]
        ],
    }


"""
@router.get("/diff")
async def get_memory_diff(onlykeep: bool = Query(False)):
    if len(snapshots) < 2:
        raise HTTPException(
            status_code=400,
            detail="Need at least 2 snapshots to compare. Call the memory snapshot endpoint first.",
        )

    snapshot1 = snapshots[-2]
    snapshot2 = snapshots[-1]

    objects_before = Counter(type(o).__name__ for o in gc.get_objects())

    top_stats = snapshot2.compare_to(snapshot1, "lineno")

    if onlykeep:
        top_stats = [
            stat for stat in top_stats if is_project_file(stat.traceback[0].filename)
        ]

    current, peak = tracemalloc.get_traced_memory()

    return {
        "pid": os.getpid(),
        "current_memory": current,
        "peak_memory": peak,
        "object_types": get_object_types(),
        "memory_diff": [
            {
                "filename": (
                    os.path.relpath(stat.traceback[0].filename)
                    if onlykeep
                    else stat.traceback[0].filename
                ),
                "line": stat.traceback[0].lineno,
                "size_diff": stat.size_diff,
                "count_diff": stat.count_diff,
            }
            for stat in top_stats[:10]
        ],
    }
"""


@router.get("/objects")
async def get_object_stats():
    return {
        "pid": os.getpid(),
        "object_details": get_object_details(),
        "total_objects": len(gc.get_objects()),
    }


@router.get("/flamegraph")
async def get_flamegraph(profile: bool = Query(False)):
    """Get memory flamegraph for the entire FastAPI application"""
    if not profile:
        raise HTTPException(
            status_code=400, detail="Add ?profile=true to generate flamegraph"
        )

    tracking_file = memory_tracker.get_tracking_file()
    if not tracking_file:
        raise HTTPException(status_code=500, detail="Memory tracking not active")

    flamegraph_path = f"/tmp/memray_flamegraph_{uuid.uuid4()}.html"

    try:
        # Generate flamegraph from the tracking file
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "memray",
                "flamegraph",
                "--leaks",
                "-o",
                flamegraph_path,
                tracking_file,
            ]
        )

        # Read the content
        with open(flamegraph_path, "rb") as f:
            content = f.read()

        return Response(content=content, media_type="text/html")

    finally:
        # Cleanup flamegraph file
        try:
            if os.path.exists(flamegraph_path):
                os.unlink(flamegraph_path)
        except Exception as e:
            print(f"Cleanup error: {e}")
