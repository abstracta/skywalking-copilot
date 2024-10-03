import sys

import dotenv
import uvicorn
from uvicorn.config import LOGGING_CONFIG


if __name__ == "__main__":
    dotenv.load_dotenv()
    LOGGING_CONFIG["formatters"]["default"]["fmt"] = "%(asctime)s [%(name)s] %(levelprefix)s %(message)s"
    LOGGING_CONFIG["formatters"]["access"]["fmt"] = "%(asctime)s [%(name)s] %(levelprefix)s %(client_addr)s - \"%(request_line)s\" %(status_code)s"
    LOGGING_CONFIG["loggers"]["skywalking_copilot"] = {"handlers": ["default"], "level": "INFO"}
    LOGGING_CONFIG["loggers"]["openai"] = {"handlers": ["default"], "level": "DEBUG"}
    uvicorn.run("skywalking_copilot.api:app", host="0.0.0.0", port=8000, reload=len(sys.argv) > 1)
