import argparse
import os
import socket


def main() -> None:
    parser = argparse.ArgumentParser(description="Construction Coordination Agent")
    parser.add_argument(
        "command", choices=["serve", "schema", "migrate", "init-vector"], nargs="?", default="serve"
    )
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument(
        "--diagnostic-runtime",
        action="store_true",
        help="NON-DURABLE local test harness; not the default DBOS runtime",
    )
    args = parser.parse_args()
    if args.diagnostic_runtime:
        os.environ["CCA_DIAGNOSTIC_RUNTIME"] = "true"
    if args.host:
        os.environ["CCA_HOST"] = args.host
    if args.port is not None:
        os.environ["CCA_PORT"] = str(args.port)
    from app.settings import Settings

    settings = Settings()
    if args.command == "schema":
        import json

        from app.api.main import create_app

        print(json.dumps(create_app(settings).openapi(), indent=2))
        return
    if args.command in {"migrate", "init-vector"}:
        from app.adapters.persistence.database import make_engine, migrate

        settings.data_dir.mkdir(parents=True, exist_ok=True)
        engine = make_engine(settings.database_url)
        try:
            migrate(engine)
            if args.command == "init-vector":
                from app.adapters.retrieval_pgvector import migrate_vectors

                migrate_vectors(engine)
        finally:
            engine.dispose()
        return
    import uvicorn

    from app.api.main import create_app

    # Binding port 0 on the actual inherited socket avoids a reserve/release race in desktop.
    sock = socket.socket(
        socket.AF_INET6 if settings.host == "::1" else socket.AF_INET, socket.SOCK_STREAM
    )
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((settings.host, settings.port))
    sock.listen(128)
    port = sock.getsockname()[1]
    endpoint_host = "[::1]" if settings.host == "::1" else "127.0.0.1"
    print(f"CCA_ENDPOINT=http://{endpoint_host}:{port}", flush=True)
    application = create_app(settings)
    config = uvicorn.Config(
        application, host=settings.host, port=port, log_level="warning", access_log=False
    )
    server = uvicorn.Server(config)
    application.state.shutdown_hook = lambda: setattr(server, "should_exit", True)
    try:
        server.run(sockets=[sock])
    finally:
        sock.close()


if __name__ == "__main__":
    main()
