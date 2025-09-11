"""
Health check endpoints for Fly.io monitoring and deployment validation.
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import psutil
import os
from pathlib import Path

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Comprehensive health check for Fly.io monitoring.

    Returns:
        JSONResponse: Health status with detailed service information
    """

    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "environment": {
            "fly_app": os.getenv("FLY_APP_NAME", "local"),
            "fly_region": os.getenv("FLY_REGION", "local"),
            "fly_machine_id": os.getenv("FLY_MACHINE_ID", "local"),
            "python_version": f"{psutil.sys.version_info.major}.{psutil.sys.version_info.minor}.{psutil.sys.version_info.micro}",
        },
        "services": {
            "api": True,
            "face_detection": False,
            "chroma_db": False,
            "file_system": False,
        },
        "storage": {
            "videos_volume": False,
            "embeddings_volume": False,
            "metadata_volume": False,
            "chromadb_volume": False,
        },
        "system": {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": {},
        },
        "critical_files": {
            "contestant_info_csv": False,
            "config_json": False,
            "embeddings_count": 0,
        },
    }

    try:
        # Check file system volumes
        volumes = [
            "/data/videos",
            "/data/embeddings",
            "/data/metadata",
            "/data/chroma_db",
        ]
        for volume in volumes:
            volume_name = f"{volume.split('/')[-1]}_volume"
            if Path(volume).exists():
                health_status["storage"][volume_name] = True
                # Get disk usage
                try:
                    usage = psutil.disk_usage(volume)
                    health_status["system"]["disk_usage"][volume] = {
                        "total_gb": round(usage.total / (1024**3), 2),
                        "used_gb": round(usage.used / (1024**3), 2),
                        "free_gb": round(usage.free / (1024**3), 2),
                        "usage_percent": round((usage.used / usage.total) * 100, 1),
                    }
                except Exception:
                    health_status["system"]["disk_usage"][volume] = {
                        "error": "Cannot access"
                    }

        # Check critical files (respecting CLAUDE.md constraints)
        # Check contestant_info.csv (CRITICAL - must not be deleted)
        contestant_info_paths = [
            "/data/metadata/contestant_info.csv",  # Production path
            "/app/metadata/contestant_info.csv",  # Container fallback
            "../metadata/contestant_info.csv",  # Local development
        ]

        for path in contestant_info_paths:
            if Path(path).exists():
                health_status["critical_files"]["contestant_info_csv"] = True
                break

        # Check config.json
        config_paths = ["/app/config.json", "../config.json"]
        for path in config_paths:
            if Path(path).exists():
                health_status["critical_files"]["config_json"] = True
                break

        # Count contestant embeddings
        embeddings_paths = [
            "/data/embeddings/contestants",
            "/app/source/photo/contestants",
            "../source/photo/contestants",
        ]

        for emb_path in embeddings_paths:
            emb_dir = Path(emb_path)
            if emb_dir.exists():
                # Count directories (each represents a contestant)
                contestant_dirs = [d for d in emb_dir.iterdir() if d.is_dir()]
                health_status["critical_files"]["embeddings_count"] = len(
                    contestant_dirs
                )
                break

        # Check ChromaDB
        try:
            import chromadb

            chroma_paths = ["/data/chroma_db", "../data/chroma_db", ".chroma_db"]
            for chroma_path in chroma_paths:
                if Path(chroma_path).exists():
                    client = chromadb.PersistentClient(path=chroma_path)
                    collections = client.list_collections()
                    health_status["services"]["chroma_db"] = True
                    health_status["chroma_collections"] = len(collections)
                    break
        except Exception as e:
            health_status["services"]["chroma_db"] = False
            health_status["chroma_error"] = str(e)

        # Check face detection model (optional - may not be loaded yet)
        try:
            from src.core.face_detector import FaceDetector

            FaceDetector()
            health_status["services"]["face_detection"] = True
        except Exception as e:
            health_status["services"]["face_detection"] = False
            health_status["face_detection_error"] = str(e)

        # Overall file system health
        health_status["services"]["file_system"] = (
            health_status["critical_files"]["contestant_info_csv"]
            and health_status["critical_files"]["config_json"]
            and health_status["critical_files"]["embeddings_count"]
            > 90  # Expect 95+ contestants
        )

    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["error"] = str(e)
        return JSONResponse(content=health_status, status_code=503)

    # Determine overall health status
    critical_services = [
        health_status["services"]["file_system"],
        health_status["critical_files"]["contestant_info_csv"],
        health_status["critical_files"]["embeddings_count"] > 90,
    ]

    if not all(critical_services):
        health_status["status"] = "degraded"
        health_status["issues"] = []

        if not health_status["critical_files"]["contestant_info_csv"]:
            health_status["issues"].append("CRITICAL: contestant_info.csv not found")

        if health_status["critical_files"]["embeddings_count"] <= 90:
            health_status["issues"].append(
                f"WARNING: Only {health_status['critical_files']['embeddings_count']} contestant embeddings found (expected 95+)"
            )

        return JSONResponse(content=health_status, status_code=200)

    return JSONResponse(content=health_status, status_code=200)


@router.get("/ready")
async def readiness_probe():
    """
    Kubernetes/Fly.io readiness probe - simple check for essential services.

    Returns:
        dict: Simple ready/not ready status

    Raises:
        HTTPException: 503 if service is not ready
    """
    try:
        # Check if critical volumes are mounted (for production)
        if os.getenv("FLY_APP_NAME"):
            volumes_ready = all(
                [
                    Path("/data/videos").exists(),
                    Path("/data/embeddings").exists(),
                    Path("/data/metadata").exists(),
                ]
            )

            if not volumes_ready:
                raise HTTPException(status_code=503, detail="Storage volumes not ready")

        # Check if critical file exists (respecting CLAUDE.md constraints)
        contestant_info_exists = any(
            [
                Path("/data/metadata/contestant_info.csv").exists(),
                Path("/app/metadata/contestant_info.csv").exists(),
                Path("../metadata/contestant_info.csv").exists(),
            ]
        )

        if not contestant_info_exists:
            raise HTTPException(
                status_code=503, detail="CRITICAL: contestant_info.csv not found"
            )

        return {"status": "ready", "timestamp": datetime.now().isoformat()}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service not ready: {str(e)}")


@router.get("/live")
async def liveness_probe():
    """
    Simple liveness probe - just checks if the application is running.

    Returns:
        dict: Simple alive status
    """
    return {
        "status": "alive",
        "timestamp": datetime.now().isoformat(),
        "app": os.getenv("FLY_APP_NAME", "local"),
    }
