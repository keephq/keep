import os
import tracemalloc

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

snapshots = []


def is_project_file(filename: str) -> bool:
    project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return filename.startswith(project_dir) and ".venv" not in filename


@router.get("")
async def get_memory_snapshot(onlykeep: bool = Query(False)):
    snapshot = tracemalloc.take_snapshot()
    stats = snapshot.statistics("lineno")

    if onlykeep:
        stats = [stat for stat in stats if is_project_file(stat.traceback[0].filename)]

    snapshots.append(snapshot)

    return {
        "pid": os.getpid(),
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


@router.get("/diff")
async def get_memory_diff(onlykeep: bool = Query(False)):
    if len(snapshots) < 2:
        raise HTTPException(
            status_code=400,
            detail="Need at least 2 snapshots to compare. Call the memory snapshot endpoint first.",
        )

    snapshot1 = snapshots[-2]
    snapshot2 = snapshots[-1]

    top_stats = snapshot2.compare_to(snapshot1, "lineno")

    if onlykeep:
        top_stats = [
            stat for stat in top_stats if is_project_file(stat.traceback[0].filename)
        ]

    return {
        "pid": os.getpid(),
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
