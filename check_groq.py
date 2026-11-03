"""Check Groq credentials and structured outputs without ingesting a company."""
from pydantic import BaseModel
from config import AI_FAST_MODEL, cache_and_retry

class ConnectionCheck(BaseModel):
    ready: bool

if __name__ == '__main__':
    try:
        result = cache_and_retry(AI_FAST_MODEL, 'Return ready=true.', ConnectionCheck)
        if not result['ready']:
            raise ValueError('Groq did not confirm readiness.')
        print(f'Groq structured-output check passed ({AI_FAST_MODEL}; may use validated cache).')
    except Exception as error:
        raise SystemExit(str(error)) from None
