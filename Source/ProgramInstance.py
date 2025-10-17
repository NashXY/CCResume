import logging
import os
from Source.CCSqlite.CCSqlite import CCSqlite

logger = logging.getLogger(__name__)


class ProgramInstance:
    def BeginPlay(self):
        logger.info('BeginPlay called.')
        # ensure directory exists
        os.makedirs('Saved/DataBase', exist_ok=True)
        db = CCSqlite('Saved/DataBase/example.db')
        db.Execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)')
        db.Close()

    def EndPlay(self):
        logger.info('EndPlay called.')

