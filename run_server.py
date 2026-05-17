from overthinker.core.config import load_config

import uvicorn


if __name__ == "__main__":
    cfg = load_config()
    uvicorn.run("app:app", host=cfg.runtime.host, port=cfg.runtime.port, reload=False)
