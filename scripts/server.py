import asyncio
from pathlib import Path
import logging
import argparse
import uvicorn
import json
from dpm.fastapi.server import DPMServer
from dpm.top_error import TopErrorHandler

logger = logging.getLogger("dpm fastapi server")

def main():
    parser = argparse.ArgumentParser(
        description="DPM Server",
    )

    default_config = Path(__file__).parent.parent / "example_dbs" / "config.json"
    parser.add_argument(
        '-c', '--config',
        type=Path,
        default=default_config,
        help=f'Path to config file (default: {default_config})'
    )
    args = parser.parse_args()
    server = DPMServer(args.config)
    config = uvicorn.Config(
        server.app,
        host='0.0.0.0',
        port=8080,
        log_level=logging.INFO
    )
    
    u_server = uvicorn.Server(config)

    handler = TopErrorHandler(top_level_callback=server.get_error_callback(), logger=logger)

    async def main_coroutine(u_server):
        await u_server.serve()
    handler.run(main_coroutine, u_server)
    
    if server.background_error_dict:
        from pprint import pprint
        pprint(server.background_error_dict)
        raise SystemExit(1)

if __name__ == "__main__":
    main()
