import sys

import dotenv
import uvicorn

if __name__ == "__main__":
    dotenv.load_dotenv()
    uvicorn.run("skywalking_copilot.api:app", host="0.0.0.0", port=8000, reload=len(sys.argv) > 1)
