"""
Stratify Analysis Engine — Entry Point

Inicia todos os analyzers como consumers independentes do Redis Streams.
Cada analyzer roda em sua própria task assíncrona (asyncio).
"""
import asyncio
import os
import structlog
import uvicorn
from fastapi import FastAPI

from analyzers.crosshair_coach.analyzer import CrosshairCoachAnalyzer
from analyzers.utility_coach.analyzer import UtilityCoachAnalyzer
from analyzers.anti_noob_detector.analyzer import AntiNoobDetectorAnalyzer
from analyzers.round_iq_analyzer.analyzer import RoundIQAnalyzer
from analyzers.clutch_analyzer.analyzer import ClutchAnalyzer

log = structlog.get_logger()

# FastAPI apenas para health check
app = FastAPI(title="Stratify Analysis Engine", version="0.1.0")

@app.get("/health")
async def health():
    return {"status": "ok"}


ANALYZERS = [
    CrosshairCoachAnalyzer,
    UtilityCoachAnalyzer,
    AntiNoobDetectorAnalyzer,
    RoundIQAnalyzer,
    ClutchAnalyzer,
]


async def main():
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    log.info("starting_analysis_engine", redis_url=redis_url, analyzers=len(ANALYZERS))

    tasks = []
    for AnalyzerClass in ANALYZERS:
        analyzer = AnalyzerClass(redis_url=redis_url)
        tasks.append(asyncio.create_task(analyzer.run(), name=AnalyzerClass.__name__))
        log.info("analyzer_started", name=AnalyzerClass.__name__)

    # Roda health server + todos os workers em paralelo
    config = uvicorn.Config(app, host="0.0.0.0", port=8080, log_level="warning")
    server = uvicorn.Server(config)
    tasks.append(asyncio.create_task(server.serve()))

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
