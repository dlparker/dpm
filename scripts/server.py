import asyncio
from pathlib import Path
import logging
import argparse
import uvicorn
import json
from vboss.fastapi.server import VBossServer


async def main():
    parser = argparse.ArgumentParser(
        description="VBoss Server",
    )

    default_config = Path(__file__).parent.parent / "example_dbs" / "config.json"
    parser.add_argument(
        '-c', '--config',
        type=Path,
        default=default_config,
        help=f'Path to config file (default: {default_config})'
    )
    args = parser.parse_args()
    server = VBossServer(args.config)
    config = uvicorn.Config(
        server.app,
        host='0.0.0.0',
        port=8080,
        log_level=logging.WARNING
    )
    
    server = uvicorn.Server(config)
    await server.serve()
    

if __name__ == "__main__":
    asyncio.run(main())
